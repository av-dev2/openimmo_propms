import frappe
from frappe import _

from openimmo_propms.services.export_engine import run_export


@frappe.whitelist()
def run_openimmo_export(
	source_name,
	filter_publish=None,
	filter_status=None,
	filter_company=None,
	property_name=None,
	anbieter_id=None,
	save_file=None,
):
	"""Whitelisted wrapper for the minimal metadata-driven export flow."""
	return run_export(
		source_name=source_name,
		filter_publish=filter_publish,
		filter_status=filter_status,
		filter_company=filter_company,
		property_name=property_name,
		anbieter_id=anbieter_id,
		save_file=save_file,
	)


@frappe.whitelist()
def get_default_template(template_name):
	"""Return the content of the default Jinja XML template."""
	from openimmo_propms.services.default_templates import (
		OPENIMMO_JINJA_TEMPLATE,
	)

	templates = {
		"OpenImmo 1.2.7": OPENIMMO_JINJA_TEMPLATE,
	}

	if template_name not in templates:
		frappe.throw(_("Unknown template: {0}").format(template_name))

	return templates[template_name]


@frappe.whitelist()
def preview_jinja_xml(source_name):
	"""Preview Jinja XML template with the first matching property record.

	Same pattern as Auto Repeat's generate_message_preview().
	"""
	source = frappe.get_doc("Integration Source", source_name)

	if not source.use_jinja_template or not source.xml_template:
		frappe.throw(_("Jinja template is not enabled for this source."))

	# Fetch first matching record for preview
	from openimmo_propms.services.export_engine import _get_records_for_export

	records = _get_records_for_export(source, {})
	if not records:
		frappe.throw(_("No records found matching the configured export filters."))

	record = records[0]

	# Build mapped data for the single record
	from openimmo_propms.services.export_mapper import build_property_data

	mapped_record = build_property_data(source, record)

	context = {
		"doc": record,
		"mapped": mapped_record,
		"all_records": [{"doc": record, "mapped": mapped_record}],
		"source": source,
		"frappe": frappe,
	}

	# xml_template is an administrator-only Integration Source field.
	# nosemgrep
	return frappe.render_template(source.xml_template, context)
