# path/to/openimmo_propms/services/processor.py

import frappe
from frappe.utils import now_datetime

from openimmo_propms.services.mapper import DuplicateRecordError, map_external_data_to_doctype
from openimmo_propms.services.parser import get_dict_from_xml


@frappe.whitelist()
def run_integration_engine(job_name):
	"""
	Main orchestrator to process an Integration Job.
	"""
	job = frappe.get_doc("Integration Job", job_name)
	source = frappe.get_doc("Integration Source", job.source_name)

	try:
		job.db_set("status", "Processing")

		# 1. Parse
		data_dict = get_dict_from_xml(job.xml_file)

		# 2. Navigate to Root Node
		entries = navigate_to_root_node(data_dict, source.root_node)

		if not entries:
			raise Exception(frappe._("No records found at: {0}").format(source.root_node))

		if not isinstance(entries, list):
			entries = [entries]

		# 3. Process Mappings
		job.total_records = len(entries)
		job.successful_records = 0
		job.failed_records = 0
		job.skipped_records = 0
		job.processing_details = []

		for entry in entries:
			try:
				doc_id = map_external_data_to_doctype(source.name, entry)
				job.successful_records += 1
				job.append(
					"processing_details",
					{"record_type": source.target_doctype, "record_id": doc_id, "status": "Success"},
				)
			except DuplicateRecordError as e:
				# Records already existing are marked as skipped with a clear message
				job.skipped_records += 1
				job.append(
					"processing_details",
					{
						"record_type": source.target_doctype,
						"record_id": e.record_id,
						"status": "Skipped",
						"error_message": frappe._("Already exists: {0}").format(e.record_id),
					},
				)
			except Exception as e:
				job.failed_records += 1
				error_trace = frappe.get_traceback()
				job.append(
					"processing_details",
					{"record_type": source.target_doctype, "status": "Failed", "error_message": str(e)},
				)

				# Log the raw error dump for debugging
				if not job.error_log:
					job.error_log = ""
				job.error_log += f"\n--- Error for Entry ---\n{error_trace}\n"

				# Limit the title to 140 chars to avoid Frappe truncation error
				error_title = f"Integration record failed: {e!s}"[:135]
				frappe.log_error(error_trace, error_title)

		job.processed_at = now_datetime()
		job.log_message = frappe._("Processed {0} records. Success: {1}, Skipped: {2}, Failed: {3}").format(
			job.total_records, job.successful_records, job.skipped_records, job.failed_records
		)
		job.save()

	except Exception as e:
		frappe.log_error("Integration Engine Error", frappe.get_traceback())
		job.db_set({"status": "Failed", "error_log": str(e)})


def navigate_to_root_node(data, path):
	"""Helper to move to the starting data block. If path is missing, return all data."""
	if not path:
		return [data]  # Treat the whole dictionary as a single entry

	for key in path.split("."):
		if isinstance(data, dict):
			data = data.get(key)
		else:
			return None
	return data
