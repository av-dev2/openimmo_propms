# Copyright (c) 2025, Aakvatech and contributors
# For license information, please see license.txt

import os

import frappe
from frappe import _
from lxml import etree

try:
	import xmlschema
except ImportError:
	xmlschema = None


def validate_xml_file(file_path, xsd_name=None):
	"""Validate XML file structure and format"""
	try:
		# Check file exists
		absolute_path = _get_absolute_path(file_path)

		if not os.path.exists(absolute_path):
			return False, _("File not found: {0}").format(file_path)

		# Parse XML
		parser = etree.XMLParser(remove_blank_text=True)
		tree = etree.parse(absolute_path, parser)
		root = tree.getroot()

		# Check if it's OpenImmo XML
		if "openimmo" not in root.tag.lower() and "expose" not in root.tag.lower():
			return False, _("Not a valid OpenImmo/Immowelt XML file")

		# Additional validations
		if not _has_required_elements(root):
			return False, _("Missing required OpenImmo elements")

		# Optional XSD validation
		if xsd_name:
			valid, msg = validate_xml_against_xsd(absolute_path, xsd_name)
			if not valid:
				return False, msg

		return True, ""

	except etree.XMLSyntaxError as e:
		return False, _("Invalid XML format: {0}").format(str(e))
	except Exception as e:
		return False, _("Validation error: {0}").format(str(e))


def validate_xml_against_xsd(xml_content_or_path, xsd_name="openimmo_127c.xsd"):
	"""Strictly validate XML against an XSD schema"""
	if not xmlschema:
		return False, _(
			"Python library 'xmlschema' is not installed. Please run 'bench pip install xmlschema'."
		)

	try:
		xsd_path = frappe.get_app_path("openimmo_propms", "templates", "xsd", xsd_name)
		if not os.path.exists(xsd_path):
			return False, _("XSD file not found at: {0}").format(xsd_path)

		schema = xmlschema.XMLSchema(xsd_path)

		# If it's a string, we might need to encode it
		if isinstance(xml_content_or_path, str) and not os.path.exists(xml_content_or_path):
			xml_content_or_path = xml_content_or_path.encode("utf-8")

		schema.validate(xml_content_or_path)
		return True, ""
	except xmlschema.XMLSchemaValidationError as e:
		# Format the error message to be more readable
		error_msg = str(e)
		if hasattr(e, "reason") and e.reason:
			error_msg = f"{e.reason} at {e.path}"
		return False, _("XSD Validation Error: {0}").format(error_msg)
	except Exception as e:
		return False, _("XSD Validation System Error: {0}").format(str(e))


def _get_absolute_path(file_url):
	"""Convert Frappe file URL to absolute path"""
	if file_url.startswith("/private/files/"):
		return frappe.get_site_path("private", "files", os.path.basename(file_url))
	elif file_url.startswith("/files/"):
		return frappe.get_site_path("public", "files", os.path.basename(file_url))
	else:
		return frappe.get_site_path("public", file_url.lstrip("/"))


def _has_required_elements(root):
	"""Check for required OpenImmo elements"""
	# Check for basic structure
	# Use lxml xpath or find
	has_sender = root.find(".//anbieter") is not None
	has_object = root.find(".//immobilie") is not None or root.find(".//objekt") is not None

	return has_sender or has_object
