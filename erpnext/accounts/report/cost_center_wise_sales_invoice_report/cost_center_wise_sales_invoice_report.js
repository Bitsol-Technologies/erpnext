// Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.query_reports["Cost Center Wise Sales Invoice Report"] = {
	filters: [
		{
			fieldname: "from_date",
			label: "Start Date",
			fieldtype: "Date",
		},
		{
			fieldname: "to_date",
			label: "End Date",
			fieldtype: "Date",
		},
		{
			fieldname: "cost_center",
			label: "Cost Center",
			fieldtype: "Link",
			options: "Cost Center",
		},
		{
			fieldname: "company",
			label: "Company",
			fieldtype: "Link",
			options: "Company",
		},
	],
};
