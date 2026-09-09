# Copyright (c) 2025, Aakvatech and contributors
# For license information, please see license.txt

import os

import frappe
from frappe import _

from openimmo_propms.processors.base_processor import BaseProcessor


class EmailProcessor(BaseProcessor):
	"""Processor for email-based file reception"""

	def receive_files(self):
		"""Fetch XML files from configured email account"""
		if not self.source_doc.email_account:
			frappe.throw(_("Email Account not configured"))

		email_account = frappe.get_doc("Email Account", self.source_doc.email_account)
		folder = self.source_doc.email_folder or "INBOX"

		try:
			# Connect to email
			emails = self._fetch_unread_emails(email_account, folder)
			received_files = []

			for email in emails:
				attachments = self._extract_xml_attachments(email)
				for attachment in attachments:
					file_path = self._save_attachment(attachment)
					job_name = self.create_job(file_path, attachment["filename"])
					received_files.append(job_name)

			self.update_source_status("Success", frappe.utils.now())
			return received_files

		except Exception as e:
			self.log_error(f"Email Processor Error - {self.source}", str(e))
			self.update_source_status("Failed", frappe.utils.now())
			raise

	def _fetch_unread_emails(self, email_account, folder):
		"""Fetch unread emails with XML attachments"""
		# Placeholder - implement email fetching logic
		# Use email_account.get_messages() or similar
		return []

	def _extract_xml_attachments(self, email):
		"""Extract XML attachments from email"""
		attachments = []
		# Implement XML attachment extraction
		return attachments

	def _save_attachment(self, attachment):
		"""Save attachment to file system"""
		file_doc = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": attachment["filename"],
				"content": attachment["content"],
				"is_private": 1,
			}
		)
		file_doc.save(ignore_permissions=True)
		return file_doc.file_url
