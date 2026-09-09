# Copyright (c) 2025, Aakvatech and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class IntegrationSource(Document):
	def before_save(self):
		self.status = "Active" if self.enabled else "Inactive"

	def validate(self):
		if self.operation_type == "Export":
			self._validate_export_config()
		else:
			self._validate_source_config()
		self._validate_target_doctype()
		if self.use_jinja_template and self.xml_template:
			self._validate_jinja_template()

	def on_update(self):
		if self.enabled and self._has_scheduler_changed():
			self._setup_scheduler()

	def _validate_source_config(self):
		"""Validate source-specific configurations"""
		if self.source_type == "Email" and not self.email_account:
			frappe.throw(_("Email Account is required for Email source type"))

		if self.source_type == "API" and not self.api_endpoint:
			frappe.throw(_("API Endpoint is required for API source type"))

		if self.source_type == "FTP" and not (self.ftp_host and self.ftp_username):
			frappe.throw(_("FTP Host and Username are required for FTP source type"))

	def _validate_export_config(self):
		"""Validate export-specific configuration"""
		if not self.export_format:
			frappe.throw(_("Export Format is required for Export operation type"))

		if not self.transfer_scope:
			self.transfer_scope = "VOLL"

		if not self.transfer_mode:
			self.transfer_mode = "NEW"

		if self.export_format == "OpenImmo" and not self.anbieter_id:
			frappe.throw(_("Anbieter ID is required for OpenImmo export"))

		if (
			self.source_type == "FTP"
			and self.ftp_transfer_enabled
			and not (self.ftp_host and self.ftp_username)
		):
			frappe.throw(_("FTP Host and Username are required for FTP export delivery"))

		if not getattr(self, "use_jinja_template", 0) and self._uses_delete_action():
			for xml_path in [
				"verwaltung_techn.objektnr_intern",
				"verwaltung_techn.objektnr_extern",
				"verwaltung_techn.openimmo_obid",
			]:
				self._require_export_mapping(
					xml_path,
					_("DELETE export requires a field mapping for {0}").format(xml_path),
				)
		self._validate_export_filters_json()

	def _validate_export_filters_json(self):
		filters_json = (self.export_filters_json or "").strip()
		if not filters_json:
			return

		try:
			parsed_filters = frappe.parse_json(filters_json)
		except Exception:
			frappe.throw(_("Export Filters (JSON) must be valid JSON"))

		if not isinstance(parsed_filters, (dict, list)):
			frappe.throw(_("Export Filters (JSON) must be a JSON object or list"))

	def _require_export_mapping(self, xml_path, message):
		if not any((row.source_field or "").strip() == xml_path for row in self.field_mappings):
			frappe.throw(message)

	def _uses_delete_action(self):
		if (self.transfer_mode or "").strip().upper() == "DELETE":
			return True

		for mapping in self.field_mappings:
			if (mapping.source_field or "").strip() != "verwaltung_techn.aktion":
				continue

			candidate_values = [
				mapping.get("static_value"),
				mapping.get("default_value"),
				mapping.get("value_mapping"),
				mapping.get("expression_pattern"),
			]
			if any("DELETE" in str(value or "").upper() for value in candidate_values):
				return True

		return False

	def _validate_target_doctype(self):
		"""Validate target doctype exists"""
		if self.target_doctype and not frappe.db.exists("DocType", self.target_doctype):
			frappe.throw(_("Target DocType {0} does not exist").format(self.target_doctype))

	def _validate_jinja_template(self):
		"""Validate Jinja syntax on save (same pattern as Notification DocType)"""
		from frappe.utils.jinja import validate_template

		validate_template(self.xml_template)

	def _has_scheduler_changed(self):
		"""Check if scheduler settings changed"""
		if self.is_new():
			return True

		old_doc = self.get_doc_before_save()
		if not old_doc:
			return True

		return old_doc.enabled != self.enabled or old_doc.sync_frequency != self.sync_frequency

	def _setup_scheduler(self):
		"""Setup background scheduler for auto-sync"""
		# This will be implemented with scheduler hooks
		pass

	@frappe.whitelist()
	def sync_now(self):
		"""Trigger manual sync"""
		if not self.enabled:
			frappe.throw(_("Source is disabled. Enable it first."))

		frappe.enqueue(
			"openimmo_propms.services.sync_engine.execute_sync",
			source_name=self.name,
			queue="short",
			timeout=300,
		)

		frappe.msgprint(_("Sync job queued successfully"), alert=True, indicator="green")
