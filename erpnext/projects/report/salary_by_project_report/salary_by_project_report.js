// Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.query_reports["Salary by Project Report"] = {
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
			fieldname: "employee",
			label: "Employee",
			fieldtype: "Link",
			options: "Employee",
		},
		{
			fieldname: "project",
			label: "Project",
			fieldtype: "Link",
			options: "Project",
		},
		{
			fieldname: "company",
			label: "Company",
			fieldtype: "Link",
			options: "Company",
		},
	],
};
