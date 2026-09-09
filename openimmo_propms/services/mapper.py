# path/to/openimmo_propms/services/mapper.py

import frappe
from frappe.utils import cint, flt


class DuplicateRecordError(Exception):
	def __init__(self, message, record_id=None):
		super().__init__(message)
		self.record_id = record_id


def map_external_data_to_doctype(source_name, entry_data):
	"""
	Core mapping engine that creates a DocType based on metadata rules.
	"""
	source = frappe.get_doc("Integration Source", source_name)
	target_meta = frappe.get_meta(source.target_doctype)
	target_doc = frappe.new_doc(source.target_doctype)

	for mapping in source.field_mappings:
		# 1. Validate Target Field Exists in Meta
		if not target_meta.has_field(mapping.target_field):
			continue

		value = get_value_by_json_path(entry_data, mapping.source_field)

		# Metadata Fallback
		if (value is None or value == "") and mapping.default_value:
			value = mapping.default_value

		df = target_meta.get_field(mapping.target_field)

		# Validation: Check if mandatory field is missing in source
		if df.reqd and (value is None or value == ""):
			raise Exception(
				frappe._("Mandatory field {0} ({1}) is missing in the XML data").format(
					df.label, mapping.source_field
				)
			)

		if value is not None and value != "":
			value = apply_data_transformation(value, mapping, entry_data)

			# 2. Type Casting and Special Handling for Link Fields
			value = cast_value_to_fieldtype(value, df, mapping.auto_create_link, mapping.link_target_doctype)

			if value:
				target_doc.set(mapping.target_field, value)
			elif df.reqd:
				raise Exception(
					frappe._("Link validation failed for mandatory field {0}: '{1}' not found").format(
						df.label, get_value_by_json_path(entry_data, mapping.source_field)
					)
				)

	# Handle Idempotency (Unique Field Constraint)
	duplicate_id = get_duplicate_record_id(target_doc, source)
	if duplicate_id:
		raise DuplicateRecordError(frappe._("Record already exists"), duplicate_id)

	target_doc.insert(ignore_permissions=True)
	return target_doc.name


def get_duplicate_record_id(doc, source):
	"""Checks if a record with unique mapping already exists and returns its ID."""
	unique_field = next((m.target_field for m in source.field_mappings if m.is_unique), None)
	if unique_field and doc.get(unique_field):
		return frappe.db.exists(source.target_doctype, {unique_field: doc.get(unique_field)})
	return None


def get_value_by_json_path(data, path):
	"""Traverses dictionary keys using dot-notation or performs a recursive search for single keys."""
	if not path:
		return None

	# 1. Try Exact Path Traversal (e.g. interessent.email)
	current_data = data
	for key in path.split("."):
		if isinstance(current_data, dict):
			current_data = current_data.get(key)
		else:
			current_data = None
			break

	if current_data is not None:
		return current_data

	# 2. Smart Search: If not found by path and is a single key, search recursively
	if "." not in path:
		return find_recursively(data, path)

	return None


def find_recursively(data, target_key):
	"""Recursive search for a key in a nested dictionary."""
	if not isinstance(data, dict):
		return None

	if target_key in data:
		return data[target_key]

	for key, value in data.items():
		if isinstance(value, dict):
			result = find_recursively(value, target_key)
			if result is not None:
				return result
		elif isinstance(value, list):
			for item in value:
				result = find_recursively(item, target_key)
				if result is not None:
					return result
	return None


def apply_data_transformation(value, mapping, entry_data=None):
	"""Applies standard string transformations or custom expressions."""
	if not value:
		return value

	transform_type = mapping.transformation

	if transform_type == "Upper Case":
		return str(value).upper()
	if transform_type == "Lower Case":
		return str(value).lower()
	if transform_type == "Title Case":
		return str(value).title()
	if transform_type == "Integer":
		return cint(value)
	if transform_type == "Float":
		return flt(value)
	if transform_type == "Expression" and mapping.get("expression_pattern"):
		value = evaluate_expression(mapping.expression_pattern, value, entry_data)

	return apply_value_mapping(value, mapping.get("value_mapping"))


def apply_value_mapping(value, value_mapping):
	"""Map values using KEY=VALUE lines."""
	if value is None or value == "" or not value_mapping:
		return value

	value_str = str(value).strip()
	for row in str(value_mapping).splitlines():
		row = row.strip()
		if not row or "=" not in row:
			continue
		source_value, mapped_value = row.split("=", 1)
		if value_str == source_value.strip():
			return mapped_value.strip()

	return value


def evaluate_expression(pattern, value, entry_data):
	"""
	Replaces placeholders in the pattern with actual values.
	{value} is the current field value.
	{path.to.field} is an XML path relative to entry_data.
	Supports date placeholders: {DD}, {MM}, {YY}, {YYYY}
	"""
	import re

	from frappe.utils import now_datetime

	now = now_datetime()

	def replace_placeholder(match):
		placeholder = match.group(1)

		# Current value (xml_field or value as fallback)
		if placeholder in ["xml_field", "value"]:
			return str(value)

		# Date placeholders
		date_map = {
			"DD": now.strftime("%d"),
			"MM": now.strftime("%m"),
			"YY": now.strftime("%y"),
			"YYYY": now.strftime("%Y"),
		}
		if placeholder in date_map:
			return date_map[placeholder]

		# If it's another field reference
		if entry_data:
			ref_value = get_value_by_json_path(entry_data, placeholder)
			return str(ref_value) if ref_value is not None else ""

		return ""

	# Match content inside curly braces
	result = re.sub(r"\{([^}]+)\}", replace_placeholder, pattern)
	return result


def cast_value_to_fieldtype(value, df, auto_create_link=False, link_target_doctype=None):
	"""
	Ensures the value matches the target DocType field type.
	Handles Link fields by checking/creating the linked record.
	"""
	fieldtype = df.fieldtype
	if not value:
		return value

	if fieldtype in ["Int", "Check"]:
		return cint(value)
	elif fieldtype in ["Float", "Currency", "Percent"]:
		return flt(value)
	elif fieldtype in ["Small Text", "Text", "Long Text"]:
		return str(value)
	elif fieldtype == "Link":
		return handle_link_field(value, link_target_doctype or df.options, auto_create_link)

	return value


def handle_link_field(value, link_doctype, auto_create=False):
	"""
	Checks if a value exists in the linked DocType.
	Creates it if missing and 'auto_create' is enabled.
	"""
	if not value or not link_doctype:
		return None

	# Check if record exists
	if frappe.db.exists(link_doctype, value):
		return value

	# Create new record if auto_create is enabled
	if auto_create:
		try:
			# Get the name field dynamically based on autoname
			meta = frappe.get_meta(link_doctype)
			field_to_set = "name"

			if meta.autoname and meta.autoname.startswith("field:"):
				field_to_set = meta.autoname.split(":")[1]
			elif meta.get_field("title"):
				field_to_set = "title"

			new_doc = frappe.get_doc({"doctype": link_doctype, field_to_set: value})
			new_doc.insert(ignore_permissions=True)
			return new_doc.name
		except Exception:
			# Fallback to avoid breaking the main process
			return None

	return None  # Don't return value if it doesn't exist to avoid validation errors
