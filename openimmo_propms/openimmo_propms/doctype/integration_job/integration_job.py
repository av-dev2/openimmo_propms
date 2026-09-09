# Copyright (c) 2025, Aakvatech and contributors
# For license information, please see license.txt

import os

import frappe
from frappe import _
from frappe.model.document import Document


class IntegrationJob(Document):
	"""
	Controller for the Integration Job DocType.
	Adheres to Frappe's principle of 'Thin Controllers, Thick Services'.
	"""

	def validate(self):
		"""Standard validation hook."""
		self._validate_file_extension()
		self._set_file_name()
		self.set_status()

	def set_status(self):
		"""
		Derived status based on record counts.
		Only updates if not currently 'Processing' and processing has occurred.
		"""
		if self.status == "Processing":
			return

		if not (self.successful_records or self.failed_records or self.skipped_records):
			return

		if self.successful_records > 0 and self.failed_records == 0 and self.skipped_records == 0:
			self.status = "Success"
		elif self.failed_records > 0 and self.successful_records == 0:
			self.status = "Failed"
		else:
			self.status = "Partially Completed"

	def _validate_file_extension(self):
		"""Ensures only XML files are processed."""
		if self.xml_file:
			# Use splitext for robust extension checking
			_, extension = os.path.splitext(self.xml_file.lower())
			if extension != ".xml":
				frappe.throw(_("Invalid file format. Please upload an XML file."))

	def _set_file_name(self):
		"""Automatically sets file_name from the attached path."""
		if self.xml_file and not self.file_name:
			self.file_name = os.path.basename(self.xml_file)

	def update_status(self, status, error_msg=None):
		"""
		High-performance status update.
		Bypasses full document validation to avoid recursion.
		"""
		self.db_set("status", status)
		if error_msg:
			self.db_set("error_log", error_msg)

		if status in ["Success", "Failed", "Partially Completed"]:
			self.db_set("processed_at", frappe.utils.now())


# --- Whitelisted API Actions ---


@frappe.whitelist()
def process_now(name=None):
	"""
	Directly executes the integration job synchronously.
	No enqueue, no background task - immediate processing.
	"""
	# 1. Name Resolution
	job_name = name or frappe.form_dict.get("name")
	if not job_name and frappe.form_dict.get("doc"):
		import json

		doc = frappe.form_dict.get("doc")
		job_name = json.loads(doc).get("name") if isinstance(doc, str) else doc.get("name")

	if not job_name:
		frappe.throw(_("Integration Job name is required."))

	# 2. Document Loading
	job = frappe.get_doc("Integration Job", job_name)

	if not job.xml_file:
		frappe.throw(_("Please attach an XML file first."))

	if job.status == "Processing":
		frappe.msgprint(_("Job is already being processed."), alert=True)
		return

	# 3. Direct Execution Logic
	try:
		# Status update before starting
		job.update_status("Processing")
		frappe.db.commit()  # Save 'Processing' state immediately

		# Call the service directly
		from openimmo_propms.services.processor import run_integration_engine

		# This will run in the current request thread (Synchronous)
		run_integration_engine(job.name)

		# Reload to get updated stats for the response
		job.reload()

		# Return success message with summary
		return {
			"status": "Success",
			"message": _("Processing completed: {0} Success, {1} Failed").format(
				job.successful_records, job.failed_records
			),
		}

	except Exception as e:
		frappe.log_error(frappe.get_traceback(), f"Manual Direct Processing Failed - {job_name}")
		job.update_status("Failed", str(e))
		frappe.db.commit()
		frappe.throw(_("Processing failed: {0}").format(str(e)))
