# Copyright (c) 2025, Aakvatech and contributors
# For license information, please see license.txt

import ftplib
import os

import frappe
from frappe import _

from openimmo_propms.processors.base_processor import BaseProcessor


class FTPProcessor(BaseProcessor):
	"""Processor for fetching XML files from FTP servers."""

	def receive_files(self):
		"""Connects to FTP, downloads XML files, and creates Integration Jobs."""
		if not self.source_doc.ftp_host:
			frappe.throw(_("FTP Host is not configured for {0}").format(self.source))

		try:
			ftp = self._connect()

			# Change to directory if specified
			if self.source_doc.ftp_directory:
				ftp.cwd(self.source_doc.ftp_directory)

			# List only XML files
			files = [f for f in ftp.nlst() if f.lower().endswith(".xml")]
			new_jobs = []

			for filename in files:
				# Skip if already processed (check by filename for simplicity in this version)
				if frappe.db.exists("Integration Job", {"file_name": filename, "source_name": self.source}):
					continue

				file_url = self._download_and_save(ftp, filename)
				job_name = self.create_job(file_url, filename)
				new_jobs.append(job_name)

			ftp.quit()

			self.update_source_status("Success")
			return new_jobs

		except Exception as e:
			self.log_error(f"FTP Sync Failed: {self.source}", frappe.get_traceback())
			self.update_source_status("Failed")
			raise e

	def test_connection(self):
		"""Attempts to connect and login to the FTP server to verify credentials."""
		try:
			ftp = self._connect()
			ftp.quit()
			return True, _("Connection Successful!")
		except ftplib.error_perm as e:
			return False, _("Login Failed: Please check your FTP Username and Password. (Error: {0})").format(
				str(e)
			)
		except Exception as e:
			return False, _("Connection Failed: {0}").format(str(e))

	def _connect(self):
		"""Establishes and returns an FTP connection, supporting TLS if available."""
		host = self.source_doc.ftp_host
		port = self.source_doc.ftp_port or 21
		user = self.source_doc.ftp_username
		password = self.source_doc.get_password("ftp_password")

		try:
			# Use FTP_TLS for secure connection (common for Immowelt)
			ftp = ftplib.FTP_TLS(timeout=60)
			ftp.encoding = "utf-8"  # Add UTF-8 support as per documentation
			ftp.connect(host, port)

			if user:
				ftp.login(user, password)
				# Secure the data connection
				ftp.prot_p()
			else:
				ftp.login()

			ftp.set_pasv(True)
			return ftp
		except Exception as e:
			# Fallback to plain FTP if TLS fails
			frappe.log_error(f"FTP TLS failed, trying plain FTP: {e!s}", "FTP Sync")
			ftp = ftplib.FTP(timeout=60)
			ftp.connect(host, port)
			ftp.login(user, password)
			ftp.set_pasv(True)
			return ftp

	def _download_and_save(self, ftp, filename):
		"""Downloads file from FTP and creates a Frappe File record."""
		# 1. Download to a temporary path
		temp_filename = f"ftp_{frappe.generate_hash(length=8)}_{filename}"
		local_path = os.path.join(frappe.get_site_path("private", "files"), temp_filename)

		with open(local_path, "wb") as f:
			ftp.retrbinary(f"RETR {filename}", f.write)

		# 2. Verify Integrity (Check for closing tag as per guide #6)
		with open(local_path, encoding="utf-8", errors="ignore") as f:
			content = f.read()
			if "</openimmo>" not in content.lower():
				os.remove(local_path)
				return None  # Skip incomplete file

		# 3. Create Frappe File document
		file_doc = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": filename,
				"content": None,  # Content is on disk
				"file_url": f"/private/files/{temp_filename}",
				"is_private": 1,
			}
		)
		file_doc.insert(ignore_permissions=True)

		return file_doc.file_url
