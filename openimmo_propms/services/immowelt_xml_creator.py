import re
import xml.etree.ElementTree as ET

SALESTYPE_MAP = {
	"kauf": "1",
	"buy": "1",
	"sale": "1",
	"miete": "2",
	"mieten": "2",
	"rent": "2",
	"lease": "2",
}


ESTATE_TYPE_MAP = {
	"wohnung": ("1", "Wohnungen"),
	"appartement": ("1", "Wohnungen"),
	"apartment": ("1", "Wohnungen"),
	"haus": ("2", "Häuser"),
	"grundstück": ("3", "Grundstücke"),
	"grundstueck": ("3", "Grundstücke"),
	"büro": ("4", "Büro-/Praxisflächen"),
	"buero": ("4", "Büro-/Praxisflächen"),
	"praxis": ("4", "Büro-/Praxisflächen"),
	"laden": ("5", "Ladenflächen"),
	"ladengeschäft": ("5", "Ladenflächen"),
	"ladengeschaeft": ("5", "Ladenflächen"),
	"halle": ("6", "Hallen/Industrieflächen"),
	"industrie": ("6", "Hallen/Industrieflächen"),
	"rendite": ("8", "Renditeobjekte"),
	"garage": ("13", "Garage/Stellplatz"),
	"stellplatz": ("13", "Garage/Stellplatz"),
	"garagenstellplatz": ("13", "Garage/Stellplatz"),
	"ferienimmobilie": ("12", "Ferienimmobilien"),
	"wohnen auf zeit": ("15", "Wohnen auf Zeit"),
}


CATEGORY_MAP = {
	"außen-stellplatz": ("11", "Außen-Stellplatz"),
	"aussen-stellplatz": ("11", "Außen-Stellplatz"),
	"stellplatz": ("11", "Außen-Stellplatz"),
	"tiefgarage": ("12", "Tiefgarage"),
	"garage": ("13", "Garage"),
	"einzelgarage": ("13", "Garage"),
	"carport": ("14", "Carport"),
	"wohnung": ("19", "Wohnung"),
	"appartement": ("20", "Appartement"),
	"apartment": ("20", "Appartement"),
	"haus": ("21", "Haus"),
	"loft": ("22", "Loft"),
	"maisonette": ("23", "Maisonette"),
	"penthouse": ("25", "Penthouse"),
	"terrassenwohnung": ("26", "Terrassenwohnung"),
	"etagenwohnung": ("27", "Etagenwohnung"),
	"büro": ("29", "Bürofläche"),
	"buero": ("29", "Bürofläche"),
	"praxis": ("30", "Praxis"),
	"laden": ("17", "Gewerbeflächen"),
	"ladengeschäft": ("17", "Gewerbeflächen"),
	"ladengeschaeft": ("17", "Gewerbeflächen"),
	"gewerbe": ("17", "Gewerbeflächen"),
	"gewerbeinheit": ("17", "Gewerbeflächen"),
	"lager": ("17", "Gewerbeflächen"),
	"lagerraum": ("17", "Gewerbeflächen"),
	"keller": ("17", "Gewerbeflächen"),
	"archiv": ("17", "Gewerbeflächen"),
}


ITEM_FIELD_MAP = (
	("ReferenceNumber", "verwaltung_techn.objektnr_intern"),
	("OnlineID", "verwaltung_techn.objektnr_extern"),
	("Description", "freitexte.objekttitel"),
	("LocationStreet", "geo.strasse"),
	("LocationZip", "geo.plz"),
	("LocationCity", "geo.ort"),
	("LocationCountry", "geo.land"),
	("Price", "preise.kaltmiete"),
	("PriceNettoKaltmiete", "preise.kaltmiete"),
	("AdditionalCosts", "preise.nebenkosten"),
	("PriceWarmmiete", "preise.warmmiete"),
	("ParkingPrice", "preise.stellplatzmiete"),
	("CommonCharge", "preise.hausgeld"),
	("Kaution", "preise.kaution"),
	("Provision", "preise.aussen_courtage"),
	("Baujahr", "zustand_angaben.baujahr"),
	("Bezugsfrei", "verwaltung_techn.verfuegbar_ab"),
	("AreaLiving", "flaechen.wohnflaeche"),
	("AreaLand", "flaechen.grundstuecksflaeche"),
	("Rooms", "flaechen.anzahl_zimmer"),
	("Ausstattung", "ausstattung.ausstattungsmerkmale"),
	("Info1", "freitexte.objektbeschreibung"),
	("Info2", "freitexte.lage"),
	("Info3", "freitexte.ausstatt_beschr"),
	("Info4", "freitexte.nebenkosten"),
	("Info5", "freitexte.sonstige_angaben"),
	("Moeblierung", "ausstattung.moebliert"),
	("ParkingSlots", "flaechen.anzahl_stellplaetze"),
	("Stockwerk", "geo.etage"),
)


def build_immowelt_document(records, mapped_records=None, source=None):
	"""Build Immowelt-style expose XML."""
	mapped_records = mapped_records or records

	expose_nodes = [
		build_immowelt_expose(record, mapped_record, source=source)
		for record, mapped_record in zip(records, mapped_records)
	]

	if len(expose_nodes) == 1:
		root = expose_nodes[0]
	else:
		root = ET.Element("exposes")
		for expose_node in expose_nodes:
			root.append(expose_node)

	return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(
		root,
		encoding="unicode",
	)


def build_immowelt_expose(record, mapped_data, source=None):
	"""Build one <expose> node from mapped export data."""
	mapped_data = dict(mapped_data or {})

	expose = ET.Element("expose")

	_append_address(expose, mapped_data)
	_append_estate(expose, mapped_data)
	_append_images(expose, mapped_data, record, source)
	_append_attachments(expose, mapped_data)
	_append_extensions(expose, mapped_data)
	_append_geo_data(expose, mapped_data)

	return expose


def _append_address(expose, mapped_data):
	address = ET.SubElement(expose, "address")

	adr_guid = _first_value(
		mapped_data,
		"address.AdrGuid",
		"kontaktperson.adr_guid",
		"anbieter.adr_guid",
	)
	if adr_guid:
		address.set("AdrGuid", str(adr_guid))

	address_fields = (
		("mobil", "kontaktperson.mobil"),
		("fax", "kontaktperson.fax"),
		("phone", "kontaktperson.tel_zentrale"),
		("email", "kontaktperson.email_zentrale"),
		("city", "kontaktperson.ort"),
		("zip", "kontaktperson.plz"),
		("street", "kontaktperson.strasse"),
		("name", "kontaktperson.name"),
		("salutation", "kontaktperson.anrede"),
		("company", "anbieter.firma"),
		("linktopartnerpage", "anbieter.homepage"),
	)

	for tag, path in address_fields:
		_set_child_text(address, tag, mapped_data.get(path))


def _append_estate(expose, mapped_data):
	estate_attrs = _build_estate_attributes(mapped_data)
	estate = ET.SubElement(expose, "estate", estate_attrs)

	for item_id, path in ITEM_FIELD_MAP:
		value = mapped_data.get(path)
		if value not in (None, ""):
			_append_item(estate, item_id, _item_title(item_id), value)

	return estate


def _build_estate_attributes(mapped_data):
	object_label = _first_value(
		mapped_data,
		"objektkategorie.objektart",
		"objektart",
		"freitexte.objekttitel",
		"verwaltung_techn.objektnr_extern",
	)

	category_label = _first_value(
		mapped_data,
		"objektkategorie.kategorie",
		"objektkategorie.objektart",
		"freitexte.objekttitel",
		"verwaltung_techn.objektnr_extern",
	)

	type_id, type_description = _resolve_estate_type(object_label)
	category_id, category_description = _resolve_category(category_label)
	salestype = _resolve_salestype(mapped_data)

	return _clean_attrs(
		{
			"id": _first_value(
				mapped_data,
				"estate.id",
				"verwaltung_techn.objektnr_intern",
			),
			"guid": _first_value(
				mapped_data,
				"estate.guid",
				"verwaltung_techn.guid",
				"verwaltung_techn.objektnr_intern",
			),
			"onlineid": _first_value(
				mapped_data,
				"estate.onlineid",
				"verwaltung_techn.objektnr_extern",
			),
			"type-id": type_id,
			"type-description": type_description,
			"salestype": salestype,
			"category-id": category_id,
			"category-description": category_description,
		}
	)


def _append_item(estate, item_id, title, value):
	item = ET.SubElement(estate, "item", {"id": item_id})
	_set_child_text(item, "title", title)
	_set_child_text(item, "description", value)


import re
import xml.etree.ElementTree as ET

import frappe

# ... (keep existing mappings and other functions)


def _append_images(expose, mapped_data, record, source):
	"""Fetch images from mapped data or direct child table record."""
	image_urls = _collect_image_urls(mapped_data)

	# If not found in mapping, try to fetch from raw record object
	if not image_urls and record:
		# Check if it's a dict (as passed from export_engine) or a Frappe Document object
		child_table = record.get("custom_image_gallery")

		if child_table and isinstance(child_table, list):
			for row in child_table:
				# Handle both dict-like and object-like access
				img_path = row.get("picture") if isinstance(row, dict) else getattr(row, "picture", None)
				if img_path:
					base_url = (source.base_media_url or "").strip() or frappe.utils.get_url()
					full_url = f"{base_url.rstrip('/')}/{img_path.lstrip('/')}"
					image_urls.append(full_url)

	image_urls = _deduplicate(image_urls)

	if not image_urls:
		return

	images = ET.SubElement(expose, "images")
	_set_child_text(images, "thumbnail", image_urls[0])

	for index, image_url in enumerate(image_urls):
		image = ET.SubElement(images, "image", {"id": str(index)})
		_set_child_text(image, "source", image_url)
		_set_child_text(image, "description", f"Bild {index + 1}")
		_set_child_text(image, "source_thumbnail", image_url)
		_set_child_text(image, "source_XXL", image_url)


def _append_attachments(expose, mapped_data):
	attachment_urls = _split_multi_value(
		_first_value(
			mapped_data,
			"attachments.documents",
			"anhaenge.dokumente",
			"documents",
		)
	)

	if not attachment_urls:
		return

	attachments = ET.SubElement(expose, "attachments")
	for index, attachment_url in enumerate(attachment_urls):
		document = ET.SubElement(attachments, "Document", {"id": str(index)})
		_set_child_text(document, "source", attachment_url)
		_set_child_text(document, "description", f"Dokument {index + 1}")


def _append_extensions(expose, mapped_data):
	extensions = ET.SubElement(expose, "extensions")

	ET.SubElement(
		extensions,
		"environmentmap",
		{"visible": _bool_attr(mapped_data.get("extensions.environmentmap.visible"))},
	)
	ET.SubElement(
		extensions,
		"financecalculator",
		{"visible": _bool_attr(mapped_data.get("extensions.financecalculator.visible"))},
	)
	ET.SubElement(
		extensions,
		"contactformular",
		{"visible": _bool_attr(mapped_data.get("extensions.contactformular.visible"), default=True)},
	)

	energy_value = _first_value(
		mapped_data,
		"zustand_angaben.energiepass_kennwert",
		"extensions.energyperformance.EnergiePassWert",
	)
	energy_attrs = {
		"visible": _bool_attr(bool(energy_value)),
	}

	if energy_value:
		energy_attrs.update(
			_clean_attrs(
				{
					"EnergiePassArt": _first_value(
						mapped_data,
						"zustand_angaben.energiepass_art",
						"extensions.energyperformance.EnergiePassArt",
					),
					"EnergiePassWert": energy_value,
					"EnergiePassWertKlasse": _first_value(
						mapped_data,
						"zustand_angaben.energieeffizienzklasse",
						"extensions.energyperformance.EnergiePassWertKlasse",
					),
					"EnergiePassInclWasser": _first_value(
						mapped_data,
						"zustand_angaben.mitwarmwasser",
						"extensions.energyperformance.EnergiePassInclWasser",
					),
				}
			)
		)

	ET.SubElement(extensions, "energyperformance", energy_attrs)
	ET.SubElement(extensions, "slideshow", {"visible": "false"})


def _append_geo_data(expose, mapped_data):
	geo_id = _first_value(mapped_data, "GeoData.GeoID", "geo.geo_id")
	longitude = _first_value(
		mapped_data,
		"GeoData.laengengrad",
		"geo.laengengrad",
		"geo.longitude",
	)
	latitude = _first_value(
		mapped_data,
		"GeoData.breitengrad",
		"geo.breitengrad",
		"geo.latitude",
	)

	if not any([geo_id, longitude, latitude]):
		return

	geo_data = ET.SubElement(expose, "GeoData")
	_set_child_text(geo_data, "GeoID", geo_id)
	_set_child_text(geo_data, "laengengrad", longitude)
	_set_child_text(geo_data, "breitengrad", latitude)


def _resolve_estate_type(value):
	normalized = _normalize_lookup(value)
	for key, result in ESTATE_TYPE_MAP.items():
		if key in normalized:
			return result

	return "9", "Sonstiges"


def _resolve_category(value):
	normalized = _normalize_lookup(value)
	for key, result in CATEGORY_MAP.items():
		if key in normalized:
			return result

	if "wohnung" in normalized or "zkb" in normalized or "app" in normalized:
		return "19", "Wohnung"
	if "garage" in normalized:
		return "13", "Garage"
	if "stellplatz" in normalized:
		return "11", "Außen-Stellplatz"
	if "büro" in normalized or "buero" in normalized:
		return "29", "Bürofläche"
	if "laden" in normalized:
		return "17", "Gewerbeflächen"

	return "", ""


def _resolve_salestype(mapped_data):
	value = _first_value(
		mapped_data,
		"estate.salestype",
		"vermarktungsart",
		"objektkategorie.vermarktungsart",
	)
	normalized = _normalize_lookup(value)

	for key, salestype in SALESTYPE_MAP.items():
		if key in normalized:
			return salestype

	if mapped_data.get("preise.kaltmiete") not in (None, ""):
		return "2"

	return "0"


def _collect_image_urls(mapped_data):
	image_values = []

	for path in (
		"images",
		"images.urls",
		"anhaenge.bilder",
		"anhaenge.anhang.daten",
		"image_urls",
		"custom_image_gallery.picture",
		"custom_image_gallery",
	):
		image_values.extend(_split_multi_value(mapped_data.get(path)))

	return _deduplicate([value for value in image_values if _is_url(value)])


def _split_multi_value(value):
	if value in (None, ""):
		return []

	if isinstance(value, (list, tuple, set)):
		values = []
		for item in value:
			values.extend(_split_multi_value(item))
		return values

	return [part.strip() for part in str(value).splitlines() if part and part.strip()]


def _set_child_text(parent, tag, value):
	if value in (None, ""):
		return None

	child = ET.SubElement(parent, tag)
	child.text = str(value)
	return child


def _first_value(mapped_data, *paths):
	for path in paths:
		value = mapped_data.get(path)
		if value not in (None, ""):
			return value
	return ""


def _clean_attrs(attrs):
	return {key: str(value) for key, value in attrs.items() if value not in (None, "")}


def _bool_attr(value, default=False):
	if value in (None, ""):
		value = default

	if isinstance(value, str):
		return "true" if value.strip().lower() in {"1", "true", "yes", "ja"} else "false"

	return "true" if bool(value) else "false"


def _normalize_lookup(value):
	value = "" if value is None else str(value)
	value = value.lower().strip()
	value = value.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue")
	value = value.replace("ß", "ss")
	value = re.sub(r"[_,./-]+", " ", value)
	value = re.sub(r"\s+", " ", value)
	return value


def _is_url(value):
	return str(value).startswith(("http://", "https://"))


def _deduplicate(values):
	seen = set()
	result = []

	for value in values:
		if value in seen:
			continue
		result.append(value)
		seen.add(value)

	return result


def _item_title(item_id):
	titles = {
		"ReferenceNumber": "Referenznummer",
		"OnlineID": "Online-ID",
		"Description": "Überschrift",
		"LocationStreet": "Straße",
		"LocationZip": "PLZ",
		"LocationCity": "Ort",
		"LocationCountry": "Land",
		"Price": "Preis / Kaltmiete",
		"PriceNettoKaltmiete": "Kaltmiete",
		"AdditionalCosts": "Nebenkosten",
		"PriceWarmmiete": "Warmmiete",
		"ParkingPrice": "Stellplatzpreis",
		"CommonCharge": "Hausgeld",
		"Kaution": "Kaution",
		"Provision": "Makler-Provision",
		"Baujahr": "Baujahr",
		"Bezugsfrei": "Bezugsfrei",
		"AreaLiving": "Wohnfläche",
		"AreaLand": "Grundstücksfläche",
		"Rooms": "Zimmer",
		"Ausstattung": "Ausstattung",
		"Info1": "Objektbeschreibung",
		"Info2": "Lagebeschreibung",
		"Info3": "Ausstattung",
		"Info4": "Nebenkosten/Wohngeld",
		"Info5": "Sonstiges",
		"Moeblierung": "Möblierung",
		"ParkingSlots": "Stellplatzanzahl",
		"Stockwerk": "Stockwerk",
	}
	return titles.get(item_id, item_id)
