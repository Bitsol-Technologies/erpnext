# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

# import frappe


import frappe
from frappe import _


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns():
	return [
		{
			"label": _("Employee"),
			"fieldname": "employee",
			"fieldtype": "Link",
			"options": "Employee",
			"width": 150,
		},
		{"label": _("Employee Name"), "fieldname": "employee_name", "fieldtype": "Data", "width": 150},
		{
			"label": _("Company"),
			"fieldname": "company",
			"fieldtype": "Link",
			"options": "Company",
			"width": 120,
		},
		{
			"label": _("Project"),
			"fieldname": "project",
			"fieldtype": "Link",
			"options": "Project",
			"width": 150,
		},
		{
			"label": _("Cost Center"),
			"fieldname": "cost_center",
			"fieldtype": "Link",
			"options": "Cost Center",
			"width": 150,
		},
		{"label": _("Start Time"), "fieldname": "from_time", "fieldtype": "Datetime", "width": 150},
		{"label": _("End Time"), "fieldname": "to_time", "fieldtype": "Datetime", "width": 150},
		{"label": _("Hours Worked"), "fieldname": "hours", "fieldtype": "Float", "width": 100},
		{"label": _("Hourly Rate"), "fieldname": "billing_rate", "fieldtype": "Currency", "width": 100},
		{"label": _("Total Amount"), "fieldname": "amount", "fieldtype": "Currency", "width": 120},
	]


def get_data(filters):
	conditions = []
	if filters.get("from_date"):
		conditions.append("td.from_time >= %(from_date)s")
	if filters.get("to_date"):
		conditions.append("td.to_time <= %(to_date)s")
	if filters.get("employee"):
		conditions.append("t.employee = %(employee)s")
	if filters.get("project"):
		conditions.append("td.project = %(project)s")
	if filters.get("company"):
		conditions.append("t.company = %(company)s")
	if filters.get("cost_center"):
		conditions.append("p.cost_center = %(cost_center)s")
	where_clause = " AND ".join(conditions) if conditions else "1=1"

	query = f"""
        SELECT
            t.employee,
            t.employee_name,
            t.company,
            td.project,
            p.cost_center,
            td.from_time,
            td.to_time,
            td.hours,
            td.billing_rate,
            td.hours * td.billing_rate AS amount
        FROM
            `tabTimesheet` t
        INNER JOIN
            `tabTimesheet Detail` td ON td.parent = t.name
        LEFT JOIN
            `tabProject` p ON td.project = p.name
        WHERE
            t.docstatus = 1 AND {where_clause}
        ORDER BY
            td.project, t.employee
    """

	return frappe.db.sql(query, filters, as_dict=True)
