# Copyright (c) 2025, Aakvatech and contributors
# For license information, please see license.txt

import frappe
from frappe import _

from openimmo_propms.processors.api_processor import APIProcessor
from openimmo_propms.processors.email_processor import EmailProcessor
from openimmo_propms.processors.ftp_processor import FTPProcessor
from openimmo_propms.processors.manual_processor import ManualProcessor
from openimmo_propms.services.processor import run_integration_engine


@frappe.whitelist()
def test_integration_connection(source_name):
	"""Verifies the connection to the integration source without processing files."""
	source = frappe.get_doc("Integration Source", source_name)
	try:
		if source.operation_type == "Export" and source.source_type != "FTP":
			return {
				"status": "error",
				"message": _("Connection test is only available for FTP export sources."),
			}

		processor = _get_processor(source)
		if hasattr(processor, "test_connection"):
			success, message = processor.test_connection()
			return {"status": "success" if success else "error", "message": message}
		else:
			return {"status": "error", "message": _("Test Connection not implemented for this source type.")}
	except Exception as e:
		return {"status": "error", "message": str(e)}


@frappe.whitelist()
def execute_sync(source_name):
	"""Execute sync for a specific integration source"""
	source = frappe.get_doc("Integration Source", source_name)
	try:
		if source.operation_type == "Export":
			frappe.throw(_("Use the export API for Export sources"))

		if not source.enabled:
			frappe.throw(_("Integration Source is disabled"))

		source.db_set("last_sync_status", "Syncing...")
		frappe.db.commit()

		# Get appropriate processor based on source type
		processor = _get_processor(source)

		# 1. Fetch files
		job_names = processor.receive_files()

		if not job_names:
			source.db_set("last_sync_status", "Success (No new files)")
			return {"status": "success", "message": _("No new files found on FTP.")}

		# 2. Process each job
		processed_count = 0
		for job_name in job_names:
			try:
				run_integration_engine(job_name)
				processed_count += 1
			except Exception as e:
				frappe.log_error(f"Processing failed for {job_name}: {e!s}", "Sync Engine Process")

		source.db_set("last_sync_status", "Success")
		source.db_set("last_sync_at", frappe.utils.now())

		return {
			"status": "success",
			"message": _("Sync completed. Processed {0} of {1} job(s)").format(
				processed_count, len(job_names)
			),
		}

	except Exception as e:
		error_msg = str(e)
		frappe.log_error(frappe.get_traceback(), f"Sync Engine Error - {source_name}")
		source.db_set("last_sync_status", "Failed")
		source.db_set("last_sync_at", frappe.utils.now())
		return {"status": "error", "message": error_msg}


def execute_scheduled_sync():
	"""Execute sync/export for all enabled non-manual sources based on frequency."""
	sources = frappe.get_all(
		"Integration Source",
		filters={
			"enabled": 1,
			"sync_frequency": ["!=", "Manual"],
			"operation_type": ["in", ["Import", "Export"]],
		},
		fields=["name", "sync_frequency", "operation_type", "last_sync_at"],
	)

	frappe.log_error(
		message=f"Scheduled sync cron active. Found {len(sources)} enabled sources to check.",
		title="Integration Scheduler Cron Run",
	)

	for source in sources:
		freq = source.sync_frequency or "Manual"
		op = source.operation_type or "Sync"
		if _should_sync_now(source):
			frappe.log_error(
				message=f"Triggering scheduled {source.operation_type} for {source.name} (Frequency: {source.sync_frequency}, Last Sync At: {source.last_sync_at})",
				title=f"[{freq}] XML {op} Scheduler Trigger",
			)
			if source.operation_type == "Export":
				frappe.enqueue(
					"openimmo_propms.services.export_engine.run_export",
					source_name=source.name,
					queue="short",
					timeout=300,
				)
			else:
				frappe.enqueue(
					"openimmo_propms.services.sync_engine.execute_sync",
					source_name=source.name,
					queue="short",
					timeout=300,
				)


def _get_processor(source):
	"""Get appropriate processor instance based on source type"""
	processor_map = {
		"Email": EmailProcessor,
		"API": APIProcessor,
		"FTP": FTPProcessor,
		"Manual Upload": ManualProcessor,
	}

	processor_class = processor_map.get(source.source_type)

	if not processor_class:
		frappe.throw(_("Invalid source type: {0}").format(source.source_type))

	return processor_class(source.name)


def _should_sync_now(source):
	"""Check if source should sync based on frequency and last sync time"""
	if not source.get("sync_frequency") or source.sync_frequency == "Manual":
		return False

	if source.sync_frequency == "Hourly":
		return True

	source_doc = frappe.get_doc("Integration Source", source.name)
	last_sync = source_doc.last_sync_at

	if not last_sync:
		return True

	from frappe.utils import add_to_date, getdate, now_datetime

	current_time = now_datetime()

	if source.sync_frequency == "Daily":
		# Check if the calendar date has changed since the last sync.
		# Since the scheduler runs hourly, this will trigger on the first hourly run after midnight.
		return getdate(current_time) > getdate(last_sync)
	elif source.sync_frequency == "Weekly":
		next_sync = add_to_date(last_sync, weeks=1)
		return current_time >= next_sync
	else:
		return False
