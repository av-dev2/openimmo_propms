# path/to/openimmo_propms/services/parser.py

import os

import frappe
import xmltodict


def get_dict_from_xml(file_url):
	"""
	Converts XML file content to a Python dictionary.
	Handles multiple encodings and cleans common browser-copy issues.
	"""
	abs_path = get_absolute_path(file_url)

	if not os.path.exists(abs_path):
		frappe.throw(frappe._("File not found: {0}").format(abs_path))

	try:
		# Read as binary first to handle encoding issues
		with open(abs_path, "rb") as f:
			raw_data = f.read()

		# Try UTF-8 first
		try:
			xml_content = raw_data.decode("utf-8")
		except UnicodeDecodeError:
			# Fallback to Latin-1 if UTF-8 fails (common for European XMLs)
			xml_content = raw_data.decode("latin-1")

		xml_content = xml_content.strip()

		# Remove browser warning if user copied it from a browser view
		if "This XML file does not appear to have any style information" in xml_content:
			# Find the actual start of XML
			start_index = xml_content.find("<")
			if start_index != -1:
				xml_content = xml_content[start_index:]

		return xmltodict.parse(xml_content, dict_constructor=dict)

	except Exception as e:
		frappe.log_error("XML Parsing Error", frappe.get_traceback())
		frappe.throw(frappe._("Failed to parse XML file: {0}").format(str(e)))


def get_absolute_path(file_url):
	"""Resolves Frappe file URL to local system path."""
	if file_url.startswith("/private/files/"):
		return frappe.get_site_path("private", "files", os.path.basename(file_url))
	return frappe.get_site_path("public", file_url.lstrip("/"))
