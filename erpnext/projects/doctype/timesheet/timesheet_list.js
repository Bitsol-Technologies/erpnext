frappe.listview_settings["Timesheet"] = {
	add_fields: ["status", "total_hours", "start_date", "end_date"],
	get_indicator: function (doc) {
		if (doc.status == "Billed") {
			return [__("Billed"), "green", "status,=," + "Billed"];
		}

		if (doc.status == "Payslip") {
			return [__("Payslip"), "green", "status,=," + "Payslip"];
		}

		if (doc.status == "Completed") {
			return [__("Completed"), "green", "status,=," + "Completed"];
		}
	},
	onload: function(listview) {
		listview.page.add_button(__("Resync Clockify"), function() {
			let dialog = new frappe.ui.Dialog({
				title: __("Bulk Resync from Clockify"),
				fields: [
					{
						label: __("From Date"),
						fieldname: "from_date",
						fieldtype: "Date",
						reqd: 1,
						default: frappe.datetime.add_days(frappe.datetime.now_date(), -7)
					},
					{
						label: __("To Date"),
						fieldname: "to_date",
						fieldtype: "Date",
						reqd: 1,
						default: frappe.datetime.now_date()
					}
				],
				primary_action_label: __("Start Sync"),
				primary_action: function(values) {
					if (values.from_date > values.to_date) {
						frappe.msgprint(__("From Date cannot be after To Date."));
						return;
					}
					dialog.hide();
					frappe.call({
						method: "erpnext.projects.doctype.timesheet.timesheet.bulk_sync_clockify_timesheets",
						args: {
							from_date: values.from_date,
							to_date: values.to_date
						},
					});
				}
			});
			dialog.show();
		});
	}
};
