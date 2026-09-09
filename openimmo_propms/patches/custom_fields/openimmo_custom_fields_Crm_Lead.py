# Copyright (c) 2025, Aakvatech and contributors
# For license information, please see license.txt

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	"""
	Add custom fields for OpenImmo XML Import to Lead.
	"""
	# Identify the correct Lead DocType name (Lead vs CRM Lead)
	doctype = "CRM Lead"
	if not frappe.db.exists("DocType", doctype) and frappe.db.exists("DocType", "CRM Lead"):
		doctype = "CRM Lead"

	if not frappe.db.exists("DocType", doctype):
		return

	fields = {
		doctype: [
			{
				"fieldname": "openimmo_tab",
				"fieldtype": "Tab Break",
				"label": "OpenImmo",
				"insert_after": "facebook_form_id",
			},
			{
				"fieldname": "openimmo_inquiry_section",
				"fieldtype": "Section Break",
				"label": "Inquiry Metadata",
				"insert_after": "openimmo_tab",
				"collapsible": 1,
			},
			{
				"fieldname": "openimmo_id_key",
				"fieldtype": "Data",
				"label": "OpenImmo Unique ID",
				"insert_after": "openimmo_inquiry_section",
				"unique": 1,
				"read_only": 1,
				"description": "Used to prevent duplicate Lead creation (portal_obj_id)",
			},
			{
				"fieldname": "external_property_id",
				"fieldtype": "Data",
				"label": "External Property ID",
				"insert_after": "openimmo_id_key",
				"read_only": 1,
				"description": "The Property ID from the XML (oobj_id)",
			},
			{
				"fieldname": "portal_source",
				"fieldtype": "Data",
				"label": "Portal Source",
				"insert_after": "external_property_id",
				"description": "Portal name (e.g., Immowelt, ImmoScout24)",
			},
			{
				"fieldname": "column_break_inquiry",
				"fieldtype": "Column Break",
				"insert_after": "portal_source",
			},
			{
				"fieldname": "contact_preference",
				"fieldtype": "Select",
				"label": "Contact Preference",
				"insert_after": "column_break_inquiry",
				"options": "\nEMAIL\nTEL\nPOST",
			},
			{
				"fieldname": "inquiry_type",
				"fieldtype": "Select",
				"label": "Inquiry Type",
				"insert_after": "contact_preference",
				"options": "\nDETAIL\nEXPOSE\nBESICHTIGUNG\nVISIT",
			},
			{
				"fieldname": "inquiry_details_section",
				"fieldtype": "Section Break",
				"label": "Inquiry Message",
				"insert_after": "inquiry_type",
			},
		]
	}

	create_custom_fields(fields, update=True)
