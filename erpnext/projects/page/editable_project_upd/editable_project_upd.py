import frappe


@frappe.whitelist()
def get_project_update_summary_data(filters=None):
	if isinstance(filters, str):
		filters = frappe.parse_json(filters)

	if not filters:
		filters = {}

	project = filters.get("project")
	from_date = filters.get("from_date")
	to_date = filters.get("to_date")

	data = frappe.db.sql(
		"""
		SELECT
			pue.name,
			pue.date,
			pue.parent,
			p.project_name,
			pue.done_task,
			pue.recources,
			pue.risks_red_flags,
			pue.decision_support,
			pue.previous_issues,
			pue.deadline,
			pue.deadline_desciption,
			pue.next_milestones
		FROM
			tabProject p
		JOIN
			`tabProject Update Entry` pue ON p.name = pue.parent
		WHERE
			(%(project)s IS NULL OR %(project)s = '' OR pue.parent = %(project)s)
			AND (%(from_date)s IS NULL OR pue.date >= %(from_date)s)
			AND (%(to_date)s IS NULL OR pue.date <= %(to_date)s)
		ORDER BY
			pue.date DESC
	""",
		{"project": project, "from_date": from_date, "to_date": to_date},
		as_dict=True,
	)

	return data


@frappe.whitelist()
def save_project_update_changes(updates):
	try:
		updates = frappe.parse_json(updates)

		for row in updates:
			if not row.get("name"):
				continue  # name is mandatory to identify the row

			frappe.db.set_value(
				"Project Update Entry",
				row["name"],
				{
					"date": row.get("date"),
					"done_task": row.get("done_task"),
					"recources": row.get("recources"),
					"risks_red_flags": row.get("risks_red_flags"),
					"decision_support": row.get("decision_support"),
					"previous_issues": row.get("previous_issues"),
					"deadline": row.get("deadline"),
					"deadline_desciption": row.get("deadline_desciption"),
					"next_milestones": row.get("next_milestones"),
				},
			)

		frappe.db.commit()
		return {"status": "success"}
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "Save Project Update Error")
		frappe.db.rollback()
		return {"status": "error", "message": str(e)}


@frappe.whitelist()
def delete_project_update(name):
	try:
		frappe.delete_doc("Project Update Entry", name, ignore_permissions=True)
		frappe.db.commit()
		return {"status": "success"}
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "Delete Project Update Error")
		return {"status": "error", "message": str(e)}


@frappe.whitelist()
def create_new_project_update(data):
	try:
		data = frappe.parse_json(data)

		project = frappe.get_doc("Project", data.get("project"))

		new_update = project.append(
			"project_daily_update",
			{
				"date": data.get("date"),
				"done_task": data.get("done_task"),
				"recources": data.get("recources"),
				"risks_red_flags": data.get("risks_red_flags"),
				"decision_support": data.get("decision_support"),
				"previous_issues": data.get("previous_issues"),
				"deadline": data.get("deadline"),
				"deadline_desciption": data.get("deadline_desciption"),
				"next_milestones": data.get("next_milestones"),
			},
		)

		project.save()
		frappe.db.commit()

		return new_update.as_dict()
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "Create Project Update Error")
		frappe.db.rollback()
		return {"status": "error", "message": str(e)}
