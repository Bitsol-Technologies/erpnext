import frappe
from frappe import _


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns():
	return [
		{
			"label": _("Cost Center"),
			"fieldname": "cost_center",
			"fieldtype": "Link",
			"options": "Cost Center",
			"width": 200,
		},
		{
			"label": _("Project"),
			"fieldname": "project",
			"fieldtype": "Link",
			"options": "Project",
			"width": 150,
		},
		{"label": _("Project Name"), "fieldname": "project_name", "fieldtype": "Data", "width": 180},
		{"label": _("Start Date"), "fieldname": "actual_start_date", "fieldtype": "Date", "width": 120},
		{"label": _("End Date"), "fieldname": "actual_end_date", "fieldtype": "Date", "width": 120},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 100},
		{
			"label": _("Customer"),
			"fieldname": "customer",
			"fieldtype": "Link",
			"options": "Customer",
			"width": 150,
		},
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
		conditions.append("p.actual_start_date >= %(from_date)s")
	if filters.get("to_date"):
		conditions.append("p.actual_end_date <= %(to_date)s")
	if filters.get("cost_center"):
		conditions.append("p.cost_center = %(cost_center)s")
	if filters.get("company"):
		conditions.append("p.company = %(company)s")

	where_clause = " AND ".join(conditions) if conditions else "1=1"

	query = f"""
        SELECT
            p.cost_center,
            p.name AS project,
            p.project_name,
            p.actual_start_date,
            p.actual_end_date,
            p.status,
            p.customer,
            p.company
        FROM
            `tabProject` p
        WHERE
            {where_clause}
        ORDER BY
            COALESCE(p.cost_center, 'ZZZ_No_Cost_Center'), p.actual_start_date
    """

	data = frappe.db.sql(query, filters, as_dict=True)

	result = []
	current_cc = "__start__"
	project_count = 0

	for row in data:
		# Use a consistent placeholder for nulls
		row_cc = row["cost_center"] or "No Cost Center"

		if current_cc != "__start__" and row_cc != current_cc:
			result.append(
				{
					"cost_center": f"Total Projects for {current_cc}",
					"project_name": f"{project_count} project(s)",
					"indent": 1,
				}
			)
			project_count = 0

		current_cc = row_cc
		project_count += 1

		row["cost_center"] = row_cc  # normalize nulls
		result.append(row)

	# Final group total
	if current_cc != "__start__":
		result.append(
			{
				"cost_center": f"Total Projects for {current_cc}",
				"project_name": f"{project_count} project(s)",
				"indent": 1,
			}
		)

	return result
