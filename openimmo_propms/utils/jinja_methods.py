import frappe
from frappe.utils import cint, cstr, flt, getdate


def format_immowelt_date(date_value):
	"""Convert YYYY-MM-DD (or date/datetime object) to MM-YYYY for Immowelt.

	Examples:
		2029-05-01  -> 05-2029
		2024-12-31  -> 12-2024
	"""
	if not date_value:
		return ""

	try:
		if isinstance(date_value, str):
			date_obj = getdate(date_value)
		else:
			date_obj = date_value

		return date_obj.strftime("%m-%Y")
	except Exception:
		return cstr(date_value)


def format_decimal(value):
	"""Convert comma-decimal strings to dot-decimal format.

	Examples:
		189,0    -> 189.0
		1.200,5  -> 1200.5
	"""
	if value in (None, ""):
		return ""

	text = cstr(value).strip()
	# Remove thousand separators (dots or commas before the decimal part)
	# If pattern is like 1.200,5 or 1.200.500
	if "," in text and "." in text:
		# German style: 1.200,5 -> 1200.5
		text = text.replace(".", "").replace(",", ".")
	elif "," in text:
		# Could be 189,0 (decimal) or 1,200 (thousand)
		parts = text.split(",")
		if len(parts) == 2 and len(parts[1]) <= 2:
			# Likely decimal: 189,0 -> 189.0
			text = text.replace(",", ".")
		else:
			# Thousand separator: 1,200 -> 1200
			text = text.replace(",", "")

	try:
		return str(flt(text))
	except (ValueError, TypeError):
		return text


def get_document(doctype, name=None, filters=None):
	"""Fetch a Frappe document by name or filters. Accessible from Jinja templates.

	Usage in template:
		{% set cert = get_document("Energy Certificate", doc.custom_energy_certificate) %}
		{{ cert.some_field }}
	"""
	if not doctype:
		return None

	try:
		if name:
			return frappe.get_doc(doctype, name)
		elif filters:
			name = frappe.db.get_value(doctype, filters, "name")
			if name:
				return frappe.get_doc(doctype, name)
	except Exception:
		return None

	return None


def get_value(doctype, filters=None, fieldname="name", as_dict=False):
	"""Fetch field values from the database. Accessible from Jinja templates.

	Usage in template:
		{% set val = get_value("Energy Certificate", doc.custom_energy_certificate, "gültig_bis") %}
	"""
	if not doctype:
		return None

	if isinstance(filters, str):
		filters = {"name": filters}

	return frappe.db.get_value(doctype, filters=filters, fieldname=fieldname, as_dict=as_dict)
