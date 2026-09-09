# Copyright (c) 2026, Talib sheikh and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class PropertyType(Document):
	def validate(self):
		# Strip whitespace from all string fields
		for field in [
			"property_type_name",
			"property_category",
			"openimmo_objektart",
			"openimmo_attribute",
			"openimmo_value",
			"immowelt_value",
		]:
			val = self.get(field)
			if val:
				self.set(field, val.strip())
