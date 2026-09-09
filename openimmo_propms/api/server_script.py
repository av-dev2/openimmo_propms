import frappe
from frappe.utils import now_datetime

from openimmo_propms.services.processor import run_integration_engine


@frappe.whitelist()
def import_lead_xml(file_url, source_name=None):
	"""
	Creates an Integration Job for the uploaded XML and processes it immediately.
	"""
	if not source_name:
		# Fallback to finding any Manual Upload source if not provided
		source_name = frappe.db.get_value(
			"Integration Source", {"source_type": "Manual Upload", "enabled": 1}, "name"
		)

	if not source_name:
		frappe.throw(
			frappe._("Please create an enabled Integration Source with Source Type 'Manual Upload' first.")
		)

	# Create Integration Job
	job = frappe.get_doc(
		{
			"doctype": "Integration Job",
			"source_name": source_name,
			"xml_file": file_url,
			"status": "Pending",
			"received_at": now_datetime(),
		}
	)
	job.insert(ignore_permissions=True)

	# Process immediately
	run_integration_engine(job.name)

	return job.name
