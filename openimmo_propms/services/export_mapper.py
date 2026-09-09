import math

import frappe
from frappe.utils import get_url

from openimmo_propms.services.mapper import apply_data_transformation


def build_property_data(source, record):
	"""Map one Frappe record into a flat XML-path-to-value dictionary."""
	record_data = dict(record)
	mapped_data = {}

	for mapping in source.field_mappings:
		xml_path = (mapping.source_field or "").strip()
		fieldname = (mapping.target_field or "").strip()
		source_value_type = (mapping.get("source_value_type") or "Field").strip()

		if not xml_path:
			continue

		if source_value_type == "Static":
			value = mapping.get("static_value")
		else:
			if not fieldname:
				continue

			# Check if fieldname involves child table
			if "." in fieldname:
				parent_table, child_field = fieldname.split(".", 1)
				if isinstance(record_data.get(parent_table), list):
					# It's a child table
					for i, row in enumerate(record_data[parent_table]):
						row_dict = row if isinstance(row, dict) else row.as_dict()
						val = row_dict.get(child_field)
						if val not in (None, ""):
							# Map to indexed XML path
							indexed_path = xml_path.replace("anhang", f"anhang.{i}")
							mapped_data[indexed_path] = _normalize_export_value(
								source,
								indexed_path,
								val,
							)
					continue

			value = _get_record_value(record_data, fieldname, source.target_doctype)

		if (value is None or value == "") and mapping.default_value:
			value = mapping.default_value

		if value is None or value == "":
			continue

		value = apply_data_transformation(value, mapping, record_data)
		value = _strip_prefix_for_export(value, mapping.get("export_strip_prefix"))
		value = _normalize_export_value(source, xml_path, value)
		mapped_data[xml_path] = value

	# Smart fallback for mandatory OpenImmo fields
	_ensure_mandatory_openimmo_fields(mapped_data, record_data, source)

	# 10b. Marketing Title Fallback Logic
	_apply_marketing_title_fallback(mapped_data, record_data)

	# Automatically set nutzungsart attributes from Property Type master
	_set_nutzungsart_attributes(mapped_data, record_data.get("custom_property_type"))

	# Manually collect images if not mapped via standard field_mappings
	image_gallery = record_data.get("custom_image_gallery")
	if image_gallery and isinstance(image_gallery, list):
		for i, row in enumerate(image_gallery):
			img_path = row.get("picture") if isinstance(row, dict) else getattr(row, "picture", None)
			if img_path:
				indexed_path = f"anhaenge.anhang.{i}.daten.pfad"
				mapped_data[indexed_path] = _normalize_export_value(source, indexed_path, img_path)

				# Attribute mappings remain (these are structural, not content)
				mapped_data[f"anhaenge.anhang.{i}@location"] = "EXTERN"
				mapped_data[f"anhaenge.anhang.{i}@gruppe"] = "TITELBILD"

				# Dynamic format extraction (strictly based on input data)
				ext = img_path.split(".")[-1].upper() if "." in img_path else None
				if not ext:
					frappe.throw(f"Mandatory image format missing for {img_path}")
				format_map = {"JPG": "JPEG", "JPEG": "JPEG", "PNG": "PNG", "GIF": "GIF"}
				mapped_data[f"anhaenge.anhang.{i}.format"] = format_map.get(ext, "JPEG")

	# Ensure mandatory fields have values from mapping
	if not mapped_data.get("kontaktperson.name"):
		mapped_data["kontaktperson.name"] = "N.A."

	return mapped_data


def _apply_marketing_title_fallback(mapped_data, record_data):
	"""Applies fallback chain: custom_marketing_title -> name1."""
	# 1. Primary: If already mapped from custom_marketing_title, do nothing
	if mapped_data.get("freitexte.objekttitel"):
		return

	# 2. Fallback: Try name1
	title = record_data.get("name1")

	# Only assign if a title was found
	if title:
		mapped_data["freitexte.objekttitel"] = title


def _ensure_mandatory_openimmo_fields(mapped_data, record_data, source):
	"""Ensure Immowelt doesn't reject due to missing type or category tags."""

	# 1. Resolve Usage (nutzungsart) - Explicitly set all to avoid 'null' errors
	usage_fields = ["WOHNEN", "GEWERBE", "ANLAGE", "WAZ"]
	usage_detected = False
	for field in usage_fields:
		path = f"objektkategorie.nutzungsart@{field}"
		if mapped_data.get(path) in (True, "true", 1, "1"):
			mapped_data[path] = True
			usage_detected = True
		elif path not in mapped_data:
			mapped_data[path] = False

	if not usage_detected:
		# Default logic if nothing mapped
		is_commercial = "buero" in str(mapped_data).lower() or "laden" in str(mapped_data).lower()
		if is_commercial:
			mapped_data["objektkategorie.nutzungsart@GEWERBE"] = True
		else:
			mapped_data["objektkategorie.nutzungsart@WOHNEN"] = True

	# 2. Resolve Marketing (vermarktungsart) - Explicitly set all
	market_fields = ["KAUF", "MIETE_PACHT", "ERBPACHT", "LEASING"]
	market_detected = False
	for field in market_fields:
		path = f"objektkategorie.vermarktungsart@{field}"
		if mapped_data.get(path) in (True, "true", 1, "1"):
			mapped_data[path] = True
			market_detected = True
		elif path not in mapped_data:
			mapped_data[path] = False

	if not market_detected:
		if mapped_data.get("preise.kaltmiete") or mapped_data.get("preise.warmmiete"):
			mapped_data["objektkategorie.vermarktungsart@MIETE_PACHT"] = True
		else:
			mapped_data["objektkategorie.vermarktungsart@KAUF"] = True

	# 3. Resolve Object Type (e.g., <wohnung />)
	_resolve_property_type_from_record(mapped_data, record_data, source)

	# Verify that an object type was mapped
	has_type_tag = any(key.startswith("objektkategorie.objektart.") for key in mapped_data)

	if not has_type_tag:
		frappe.log_error(
			f"Missing Property Type mapping for property: {record_data.get('name')}. Please configure the Property Type Master."
		)

	# 4. Ensure some optional but helpful 'proper' tags exist
	if "objektkategorie.user_defined_simplefield@feldname" not in mapped_data:
		mapped_data["objektkategorie.user_defined_simplefield@feldname"] = ""


def _resolve_property_type_from_record(mapped_data, record_data, source):
	"""Fetch Property Type details and map to OpenImmo objektart."""
	# Use erpnext_id from mapping if available, otherwise record name or custom_unit_id
	erpnext_id = mapped_data.get("erpnext_id") or record_data.get("name") or record_data.get("custom_unit_id")

	property_type_name = record_data.get("custom_property_type")

	if not property_type_name and erpnext_id and source.target_doctype:
		# Try fetching from the actual record in the target doctype
		property_type_name = frappe.db.get_value(source.target_doctype, erpnext_id, "custom_property_type")

		# Fallback: maybe the ID is custom_unit_id as in user's example
		if not property_type_name:
			property_type_name = frappe.db.get_value(
				source.target_doctype, {"custom_unit_id": erpnext_id}, "custom_property_type"
			)

	if not property_type_name:
		return

	try:
		prop_type = frappe.get_cached_doc("Property Type", property_type_name)
	except Exception:
		# If it's a string name but doc doesn't exist by name, try getting by property_type_name field
		prop_type_name = frappe.db.get_value(
			"Property Type", {"property_type_name": property_type_name}, "name"
		)
		if prop_type_name:
			prop_type = frappe.get_cached_doc("Property Type", prop_type_name)
		else:
			return

	objektart = prop_type.get("openimmo_objektart")
	attribute = prop_type.get("openimmo_attribute")
	value = prop_type.get("openimmo_value")

	if objektart:
		# Clear any existing text mapping to objektart to avoid validation errors
		if "objektkategorie.objektart" in mapped_data:
			del mapped_data["objektkategorie.objektart"]

		path = f"objektkategorie.objektart.{objektart}"
		if attribute and value:
			# Ensure value is uppercase for OpenImmo standards
			mapped_data[f"{path}@{attribute}"] = str(value).upper()
		else:
			# Force tag creation (e.g. <wohnung />)
			mapped_data[path] = ""

	# 4. Ensure some optional but helpful 'proper' tags exist
	if "objektkategorie.user_defined_simplefield@feldname" not in mapped_data:
		mapped_data["objektkategorie.user_defined_simplefield@feldname"] = ""


def _strip_prefix_for_export(value, prefix_to_strip):
	prefix = (prefix_to_strip or "").strip()
	if not prefix:
		return value

	if isinstance(value, str):
		if "\n" in value:
			return "\n".join(_strip_prefix_for_export(line, prefix) for line in value.splitlines())
		if value.lower().startswith(prefix.lower()):
			return value[len(prefix) :]
	return value


def _get_record_value(record_data, fieldname, root_doctype=None):
	"""Backward compatible wrapper."""
	return _resolve_value(record_data, fieldname, root_doctype)


def _resolve_value(record_data, fieldname, root_doctype):
	current = record_data
	current_doctype = root_doctype
	parts = fieldname.split(".")

	for index, part in enumerate(parts):
		remaining = parts[index + 1 :]

		if isinstance(current, dict):
			value = current.get(part)
			if not remaining:
				return _normalize_value(value)

			if isinstance(value, list):
				return _resolve_list_values(value, remaining, current_doctype, part)

			if isinstance(value, dict):
				current = value
				current_doctype = None
				continue

			link_meta = _get_link_meta(current_doctype, part)
			if link_meta and value:
				current = frappe.get_doc(link_meta.options, value).as_dict()
				current_doctype = link_meta.options
				continue

			current = value
			continue

		return None

	return _normalize_value(current)


def _resolve_list_values(items, remaining_parts, current_doctype, fieldname):
	values = []
	child_doctype = _get_child_table_options(current_doctype, fieldname)
	subpath = ".".join(remaining_parts)

	for item in items:
		if isinstance(item, dict):
			resolved = _resolve_value(item, subpath, child_doctype)
			if resolved not in (None, ""):
				values.append(resolved)

	if not values:
		return None

	return "\n".join(str(value) for value in values)


def _get_link_meta(doctype_name, fieldname):
	if not doctype_name:
		return None

	meta = frappe.get_meta(doctype_name)
	field = meta.get_field(fieldname)
	if field and field.fieldtype == "Link":
		return field
	return None


def _get_child_table_options(doctype_name, fieldname):
	if not doctype_name:
		return None

	meta = frappe.get_meta(doctype_name)
	field = meta.get_field(fieldname)
	if field and field.fieldtype == "Table":
		return field.options
	return None


def _normalize_value(value):
	if isinstance(value, list):
		cleaned = [str(item) for item in value if item not in (None, "")]
		return "\n".join(cleaned) if cleaned else None
	return value


def _normalize_export_value(source, xml_path, value):
	# Fix for 'anzahl_stellplaetze' positive integer constraint
	if "anzahl_stellplaetze" in xml_path:
		try:
			val_int = int(float(value))
			if val_int <= 0:
				return None  # Omit tag if 0 or less to pass XSD
			return val_int
		except (ValueError, TypeError):
			return None

	# 31. Round all area fields up to next 5
	area_fields = [
		"wohnflaeche",
		"nutzflaeche",
		"gesamtflaeche",
		"ladenflaeche",
		"lagerflaeche",
		"verkaufsflaeche",
		"bueroflaeche",
		"kellerflaeche",
		"gartenflaeche",
		"balkon_terrasse_flaeche",
	]
	if any(field in xml_path for field in area_fields):
		try:
			val_float = float(value)
			return math.ceil(val_float / 5) * 5
		except (ValueError, TypeError):
			pass

	# Fix for 'haustiere' boolean mapping
	if "haustiere" in xml_path:
		val_str = str(value).strip().lower()
		if val_str in ["ja", "nach absprache", "1", "true", "yes"]:
			return True
		elif val_str in ["nein", "0", "false"]:
			return False
		else:
			return None  # Omit element if invalid

	# Fix for 'moebliert' enumeration mapping
	if "moebliert" in xml_path and "@moeb" in xml_path:
		val_str = str(value).strip().lower()
		if val_str in ["voll", "teil"]:
			return val_str.upper()
		elif val_str in ["1", "true", "yes", "checked", "on"]:
			return "VOLL"
		else:
			return None  # Omit element if '0', 'false', or invalid/unchecked

	# Fix for 'heizungsart' and 'befeuerung' attribute mapping
	if ("heizungsart" in xml_path or "befeuerung" in xml_path) and "@" in xml_path:
		# If the attribute exists and has a value, it should be 'true'
		val_str = str(value).strip().lower()
		if val_str not in ["0", "false", "none", "", "no"]:
			return "true"
		return None  # Omit attribute if false/0/no

	normalized = _normalize_value(value)
	if not _is_media_path_field(xml_path):
		return normalized
	return _build_absolute_media_url(source, normalized)


def _set_nutzungsart_attributes(mapped_data, property_type_name):
	"""Fetches usage attributes from Property Type master and maps to XML."""
	if not property_type_name:
		return

	try:
		# Fetch document from Property Type master
		prop_type = frappe.get_cached_doc("Property Type", property_type_name)

		# Map XML attributes
		mapped_data["objektkategorie.nutzungsart@WOHNEN"] = bool(prop_type.use_residential)
		mapped_data["objektkategorie.nutzungsart@GEWERBE"] = bool(prop_type.use_commercial)
		mapped_data["objektkategorie.nutzungsart@ANLAGE"] = bool(prop_type.use_investment)
		mapped_data["objektkategorie.nutzungsart@WAZ"] = bool(prop_type.use_mixed)

	except Exception:
		pass


def _is_media_path_field(xml_path):
	path = (xml_path or "").strip()
	return path == "pfad" or path.endswith(".pfad")


def _build_absolute_media_url(source, image_value):
	if not image_value:
		return image_value

	image_url = str(image_value).strip()
	if not image_url:
		return image_url

	if image_url.startswith(("http://", "https://")):
		return image_url

	base_url = (getattr(source, "base_media_url", "") or "").strip() or get_url()
	if not base_url:
		return image_url

	return "{}/{}".format(base_url.rstrip("/"), image_url.lstrip("/"))
