# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt


import frappe
from frappe import _
from frappe.utils import flt


def execute(filters=None):
	columns, data = [], []
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns():
	"""Define the columns for the report."""
	return [
		{
			"label": _("Cost Center"),
			"fieldname": "cost_center",
			"fieldtype": "Link",
			"options": "Cost Center",
			"width": 200,
		},
		{
			"label": _("Sales Invoice"),
			"fieldname": "sales_invoice",
			"fieldtype": "Link",
			"options": "Sales Invoice",
			"width": 150,
		},
		{"label": _("Posting Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 120},
		{
			"label": _("Customer"),
			"fieldname": "customer",
			"fieldtype": "Link",
			"options": "Customer",
			"width": 150,
		},
		{"label": _("Total Amount"), "fieldname": "total_amount", "fieldtype": "Currency", "width": 120},
		{
			"label": _("Company"),
			"fieldname": "company",
			"fieldtype": "Link",
			"options": "Company",
			"width": 120,
		},
	]


def get_data(filters):
	conditions = []
	if filters.get("from_date"):
		conditions.append("si.posting_date >= %(from_date)s")
	if filters.get("to_date"):
		conditions.append("si.posting_date <= %(to_date)s")
	if filters.get("cost_center"):
		conditions.append("sii.cost_center = %(cost_center)s")
	if filters.get("company"):
		conditions.append("si.company = %(company)s")

	where_clause = " AND ".join(conditions) if conditions else "1=1"

	query = f"""
        SELECT
            sii.cost_center,
            si.name AS sales_invoice,
            si.posting_date,
            si.customer,
            si.grand_total AS total_amount,
            si.company
        FROM
            `tabSales Invoice` si
        INNER JOIN
            `tabSales Invoice Item` sii ON si.name = sii.parent
        WHERE
            si.docstatus = 1 AND {where_clause}
        ORDER BY
            sii.cost_center, si.posting_date
    """

	data = frappe.db.sql(query, filters, as_dict=True)

	result = []
	current_cc = None
	subtotal = 0

	for row in data:
		if current_cc and row["cost_center"] != current_cc:
			# Add subtotal before switching cost center
			result.append({"cost_center": f"Total for {current_cc}", "total_amount": subtotal, "indent": 1})
			subtotal = 0

		current_cc = row["cost_center"]
		subtotal += flt(row["total_amount"])
		result.append(row)

	# Add last subtotal
	if current_cc:
		result.append({"cost_center": f"Total for {current_cc}", "total_amount": subtotal, "indent": 1})

	return result
