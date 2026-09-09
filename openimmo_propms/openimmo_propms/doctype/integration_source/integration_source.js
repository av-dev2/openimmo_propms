frappe.ui.form.on("Integration Source", {
	onload(frm) {
		toggle_credential_fields(frm);
		update_ftp_intro(frm);
	},

	refresh(frm) {
		toggle_credential_fields(frm);
		update_ftp_intro(frm);

		// Load Default Template button
		if (frm.doc.use_jinja_template && frm.doc.operation_type === "Export") {
			frm.add_custom_button(
				__("Load Default Template"),
				() => {
					frappe.call({
						method: "openimmo_propms.api.export.get_default_template",
						args: { template_name: "OpenImmo 1.2.7" },
						freeze: true,
						freeze_message: __("Loading template..."),
						callback: (r) => {
							if (r.message) {
								frm.set_value("xml_template", r.message);
								frappe.show_alert({
									message: __("Default template loaded: OpenImmo 1.2.7"),
									indicator: "green",
								});
							}
						},
					});
				},
				__("Tools")
			);
		}

		// Preview Jinja XML button (same pattern as Notification/Auto Repeat preview)
		if (
			frm.doc.use_jinja_template &&
			frm.doc.xml_template &&
			frm.doc.operation_type === "Export"
		) {
			frm.add_custom_button(
				__("Preview XML"),
				() => {
					frappe.call({
						method: "openimmo_propms.api.export.preview_jinja_xml",
						args: { source_name: frm.doc.name },
						freeze: true,
						freeze_message: __("Rendering Jinja template..."),
						callback: (r) => {
							if (r.message) {
								let d = new frappe.ui.Dialog({
									title: __("Preview XML"),
									size: "extra-large",
									fields: [
										{
											fieldname: "xml_preview",
											fieldtype: "Code",
											options: "XML",
											label: "",
											read_only: 1,
											default: r.message,
										},
									],
								});
								d.show();
							}
						},
					});
				},
				__("Tools")
			);
		}

		if (frm.doc.source_type === "FTP") {
			// 1. Connection Test Button
			frm.add_custom_button(__("FTP Test Connection"), () => {
				frm.call({
					method: "openimmo_propms.services.sync_engine.test_integration_connection",
					args: {
						source_name: frm.doc.name,
					},
					freeze: true,
					freeze_message: __("Testing Connection to {0}...", [frm.doc.ftp_host]),
					callback: (r) => {
						if (r.message && r.message.status === "success") {
							frappe.msgprint({
								title: __("Connection Test Passed"),
								message: r.message.message,
								indicator: "green",
							});
						} else if (r.message) {
							frappe.msgprint({
								title: __("Connection Test Failed"),
								message: r.message.message,
								indicator: "red",
							});
						}
					},
				});
			});

			if (frm.doc.operation_type === "Export" && frm.doc.enabled) {
				frm.add_custom_button(__("Run Export Now"), () => {
					frm.call({
						method: "openimmo_propms.api.export.run_openimmo_export",
						args: {
							source_name: frm.doc.name,
							save_file: 1,
						},
						freeze: true,
						freeze_message: __("Generating and uploading OpenImmo XML..."),
						callback: (r) => {
							if (!r.exc && r.message) {
								let file_link = r.message.file_url
									? `<a href="${r.message.file_url}" target="_blank">${r.message.file_url}</a>`
									: __("Not saved");

								frappe.msgprint({
									title: __("Export Completed"),
									message: __(
										"Records: {0}<br>Delivery: {1}<br>Channel: {2}<br>File: {3}",
										[
											r.message.record_count || 0,
											r.message.delivery_status || __("Generated"),
											r.message.delivery_channel || __("Manual"),
											file_link,
										]
									),
									indicator: "green",
								});
								frm.reload_doc();
							}
						},
					});
				});
			}

			// 2. Manual Sync Button
			if (
				frm.doc.operation_type === "Import" &&
				frm.doc.enabled &&
				frm.doc.sync_frequency === "Manual"
			) {
				frm.add_custom_button(__("FTP Sync Now"), () => {
					frappe.confirm(
						__("Are you sure you want to fetch and process files from FTP now?"),
						() => {
							// State: Start Syncing in UI
							frm.set_df_property("last_sync_status", "value", "Syncing...");

							frm.call({
								method: "openimmo_propms.services.sync_engine.execute_sync",
								args: {
									source_name: frm.doc.name,
								},
								freeze: true,
								freeze_message: __("Connecting to {0}...", [
									frm.doc.ftp_host || "FTP Server",
								]),
								callback: (r) => {
									if (!r.exc && r.message) {
										if (r.message.status === "success") {
											frappe.show_alert({
												message: r.message.message,
												indicator: "green",
											});
										} else {
											frappe.msgprint({
												title: __("Sync Error"),
												message: r.message.message,
												indicator: "red",
											});
										}
									}
									frm.reload_doc();
								},
								error: (r) => {
									frm.reload_doc();
								},
							});
						}
					);
				});
			}
		}
	},

	ftp_transfer_enabled(frm) {
		update_ftp_intro(frm);
	},

	source_type(frm) {
		toggle_credential_fields(frm);
	},

	operation_type(frm) {
		toggle_credential_fields(frm);
	},
});

function update_ftp_intro(frm) {
	if (frm.doc.source_type !== "FTP") {
		frm.set_intro(""); // Clear intro if not FTP
		return;
	}

	// Clear existing intro first to avoid duplication
	frm.set_intro("");

	if (frm.doc.ftp_transfer_enabled) {
		frm.set_intro(__("Exporting will trigger FTP Transfer."), "green");
	} else {
		frm.set_intro(
			__("FTP Transfer is Disabled. Files will only be generated locally."),
			"red"
		);
	}
}

function toggle_credential_fields(frm) {
	const is_import = frm.doc.operation_type === "Import";
	const is_export = frm.doc.operation_type === "Export";
	const is_ftp = frm.doc.source_type === "FTP";
	const is_email = frm.doc.source_type === "Email";
	const is_api = frm.doc.source_type === "API";
	const show_credentials = (is_import && frm.doc.source_type !== "Manual Upload") || is_ftp;

	frm.toggle_display("section_break_creds", show_credentials);
	frm.toggle_display("email_account", is_import && is_email);
	frm.toggle_display("email_folder", is_import && is_email);
	frm.toggle_display("api_endpoint", is_import && is_api);
	frm.toggle_display("api_key", is_import && is_api);
	frm.toggle_display("api_secret", is_import && is_api);

	["ftp_host", "ftp_port", "ftp_username", "ftp_password", "ftp_directory"].forEach(
		(fieldname) => {
			frm.toggle_display(fieldname, is_ftp);
		}
	);

	frm.toggle_display("ftp_transfer_enabled", is_export && is_ftp);
}
