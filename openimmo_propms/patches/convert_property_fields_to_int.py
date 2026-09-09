import frappe


def execute():
	fields = ["custom_level_in_the_building", "custom_garage_spaces"]

	for fieldname in fields:
		if frappe.db.has_column("Property", fieldname):
			frappe.db.sql(
				f"""
				UPDATE `tabProperty`
				SET `{fieldname}` = NULL
				WHERE `{fieldname}` IS NOT NULL
				AND `{fieldname}` NOT REGEXP '^-?[0-9]+$'
				"""
			)

		frappe.db.set_value(
			"Custom Field",
			{"dt": "Property", "fieldname": fieldname},
			"fieldtype",
			"Int",
			update_modified=False,
		)
