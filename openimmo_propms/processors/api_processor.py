import json

# Parsing goes through defusedxml below, ET is only used to serialize nodes.
import xml.etree.ElementTree as ET  # nosemgrep

import defusedxml.ElementTree
import frappe
import requests
from defusedxml.common import DefusedXmlException
from frappe import _
from frappe.utils.file_manager import save_file

from openimmo_propms.processors.base_processor import BaseProcessor


class APIProcessor(BaseProcessor):
	"""Processor for API-based XML/JSON reception"""

	def receive_files(self):
		"""Fetch data from API, split into files, create jobs"""
		try:
			response = self._make_api_request()
			files = self._parse_api_response(response)
			received_files = []

			for file_data in files:
				file_url = self._save_api_file(file_data["content"], file_data["filename"])
				job_name = self.create_job(file_url, file_data["filename"])
				received_files.append(job_name)

			self.update_source_status("Success", len(files))
			return received_files

		except Exception as e:
			self.log_error(f"API Processor Error - {self.source}", str(e))
			self.update_source_status("Failed")
			raise

	def _make_api_request(self):
		"""Perform the actual API request using metadata"""
		if not self.source_doc.api_endpoint:
			frappe.throw(_("API Endpoint not configured for source {0}").format(self.source))

		headers = {}
		if self.source_doc.api_key:
			headers["Authorization"] = f"Bearer {self.source_doc.get_password('api_key')}"

		response = requests.get(self.source_doc.api_endpoint, headers=headers, timeout=30)
		response.raise_for_status()
		return response

	def _save_api_file(self, content, filename):
		"""Saves API content as a Frappe File"""
		if isinstance(content, dict):
			content = json.dumps(content)

		file_doc = save_file(filename, content, "Integration Source", self.source, is_private=1)
		return file_doc.file_url

	def _parse_api_response(self, response):
		"""Decide XML vs JSON and return list of {content, filename}"""
		content_type = (response.headers.get("content-type") or "").lower()
		text = response.text or ""

		if "xml" in content_type or text.strip().startswith("<"):
			return self._parse_xml(response.content)

		if "json" in content_type:
			return self._parse_json(response.json())

		return [
			{
				"content": text,
				"filename": "api_response.txt",
			}
		]

	def _parse_xml(self, content):
		"""Metadata-driven XML splitting"""
		files = []
		ns_url = self.source_doc.xml_namespace
		split_node = self.source_doc.data_split_node

		try:
			root = defusedxml.ElementTree.fromstring(content)

			# Metadata-driven lookup
			if ns_url and split_node:
				ns = {"ns": ns_url}
				items = root.findall(f".//ns:{split_node}", ns)
			elif split_node:
				items = root.findall(f".//{split_node}")
			else:
				# No split node defined, treat as single file
				items = []

			if not items:
				return [
					{
						"content": content.decode("utf-8"),
						"filename": "response_full.xml",
					}
				]

			for idx, item in enumerate(items):
				xml_str = ET.tostring(item, encoding="unicode")
				# Try to find an ID or use index
				obj_id = item.get("objectid") or item.get("id") or f"item_{idx}"
				files.append(
					{
						"content": xml_str,
						"filename": f"data_{obj_id}.xml",
					}
				)
		except (ET.ParseError, DefusedXmlException):
			files.append(
				{
					"content": content.decode("utf-8"),
					"filename": "invalid_format.xml",
				}
			)
		return files

	def _parse_json(self, data):
		"""Metadata-driven JSON splitting"""
		files = []
		split_node = self.source_doc.data_split_node

		# Use split_node as the key for items list
		items = []
		if split_node:
			# Simple path traversal for JSON
			temp_data = data
			for key in split_node.split("."):
				if isinstance(temp_data, dict):
					temp_data = temp_data.get(key)
				else:
					temp_data = None
					break
			if isinstance(temp_data, list):
				items = temp_data

		if not items:
			return [
				{
					"content": json.dumps(data),
					"filename": "api_response.json",
				}
			]

		for idx, item in enumerate(items):
			obj_id = item.get("id") or item.get("objectid") or f"item_{idx}"
			files.append(
				{
					"content": json.dumps(item),
					"filename": f"api_{obj_id}.json",
				}
			)

		return files
