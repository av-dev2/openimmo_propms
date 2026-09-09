from abc import ABC, abstractmethod

import frappe
from frappe import _


class BaseProcessor(ABC):
	def __init__(self, source_name):
		self.source = source_name
		self.source_doc = frappe.get_doc("Integration Source", source_name)

	@abstractmethod
	def receive_files(self):
		raise NotImplementedError("Subclass must implement receive_files()")

	def create_job(self, file_url, filename):
		"""
		Creates an Integration Job record.
		Metadata Driven: Uses 'source_name' and 'xml_file'.
		"""
		job = frappe.new_doc("Integration Job")
		job.update(
			{"source_name": self.source, "xml_file": file_url, "file_name": filename, "status": "Pending"}
		)
		job.insert(ignore_permissions=True)
		frappe.db.commit()
		return job.name

	def update_source_status(self, status, count=None):
		self.source_doc.db_set("last_sync_status", status)
		self.source_doc.db_set("last_sync_at", frappe.utils.now())
		if count is not None:
			self.source_doc.db_set("last_sync_count", count)

	def log_error(self, title, message):
		frappe.log_error(message, title)
