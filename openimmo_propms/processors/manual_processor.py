# path/to/openimmo_propms/processors/manual_processor.py

import frappe

from openimmo_propms.processors.base_processor import BaseProcessor
from openimmo_propms.services.processor import run_integration_engine


class ManualProcessor(BaseProcessor):
	def receive_files(self):
		"""
		Finds 'Pending' manual jobs and triggers the dynamic engine.
		"""
		pending_jobs = frappe.get_all(
			"Integration Job", filters={"source_name": self.source, "status": "Pending"}, fields=["name"]
		)

		for job in pending_jobs:
			run_integration_engine(job.name)

		self.update_source_status("Success", count=len(pending_jobs))
		return [j.name for j in pending_jobs]
