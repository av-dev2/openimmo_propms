# Copyright (c) 2026, Talib sheikh and Contributors
# See license.txt

"""
Quality Gate Service for OpenImmo Export Engine.

Provides dynamic script execution and validation mechanisms to evaluate property
records prior to export based on rules configured in Integration Source.
"""

import frappe
from frappe.utils import cint, flt, getdate, nowdate


def validate_quality_gate(source, record: dict) -> tuple[bool, list[str]]:
	"""
	Validates a property record against the Quality Gate script configured in Integration Source.

	Args:
	    source: Integration Source document or context dict containing quality_gate_script.
	    record: Property record dictionary to evaluate.

	Returns:
	    tuple[bool, list[str]]: Validation status (is_valid) and list of failure reasons.
	"""
	script = (
		getattr(source, "quality_gate_script", None)
		or (source.get("quality_gate_script") if isinstance(source, dict) else None)
		or ""
	).strip()

	if not script:
		return True, []

	reasons = []
	try:
		from frappe.utils.safe_exec import safe_exec

		exec_context = {
			"doc": record,
			"is_valid": True,
			"reasons": reasons,
			"getdate": getdate,
			"nowdate": nowdate,
			"flt": flt,
			"cint": cint,
			"frappe": frappe,
		}
		safe_exec(script, _globals=None, _locals=exec_context)
		is_valid = bool(exec_context.get("is_valid", True))
		if not is_valid and not reasons:
			reasons.append("Quality Gate Failed")
		return is_valid, reasons
	except Exception as exc:
		error_msg = f"Quality Gate script error: {str(exc)}"
		frappe.logger("openimmo_export").error(error_msg)
		return False, [error_msg]


def evaluate_quality_gate_for_export(source, records: list[dict]) -> list[dict]:
	"""
	Evaluates Quality Gate for a batch of export records, filters out blocked properties,
	logs an error summary, and stores per-record decisions for the Integration Job details.

	Args:
	    source: Integration Source document or context dict.
	    records: List of property record dictionaries.

	Returns:
	    list[dict]: Filtered list of valid property records eligible for export.
	"""
	valid_records = []
	blocked_summary = []
	processing_details = []

	source_name = getattr(source, "name", None) or (
		source.get("name") if isinstance(source, dict) else "Unknown"
	)
	record_type = getattr(source, "target_doctype", None) or (
		source.get("target_doctype") if isinstance(source, dict) else None
	)

	for record in records:
		is_valid, reasons = validate_quality_gate(source, record)
		rec_id = record.get("name") or record.get("title") or "Property"

		if is_valid:
			valid_records.append(record)
			processing_details.append(
				{
					"record_type": record_type,
					"record_id": rec_id,
					"status": "Success",
					"error_message": "",
				}
			)
		else:
			reasons_str = ", ".join(reasons) if reasons else "Failed Quality Gate"
			blocked_summary.append(f"- {rec_id}: {reasons_str}")
			processing_details.append(
				{
					"record_type": record_type,
					"record_id": rec_id,
					"status": "Skipped",
					"error_message": reasons_str,
				}
			)

	details_by_source = getattr(frappe.local, "openimmo_quality_gate_details", None) or {}
	details_by_source[source_name] = processing_details
	frappe.local.openimmo_quality_gate_details = details_by_source

	if blocked_summary:
		freq = getattr(source, "sync_frequency", None) or (
			source.get("sync_frequency") if isinstance(source, dict) else "Manual"
		)
		frappe.log_error(
			message=f"Export execution for {source_name}: {len(blocked_summary)} properties blocked by Quality Gate:\n"
			+ "\n".join(blocked_summary),
			title=f"[{freq}] Quality Gate Summary ({len(blocked_summary)} Blocked)",
		)

	return valid_records
