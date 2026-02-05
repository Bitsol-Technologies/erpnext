# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt


import json

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_to_date, flt, get_datetime, getdate, nowdate, time_diff_in_hours, today, time_diff_in_seconds
from hrms.hr.doctype.employee_checkin.employee_checkin import (
	get_clockify_report_result,
	get_clockify_report_task_id,
	get_employee_clockify_details,
	get_all_active_employees
)

from erpnext.controllers.queries import get_match_cond
from erpnext.setup.utils import get_exchange_rate


class OverlapError(frappe.ValidationError):
	pass


class OverWorkLoggedError(frappe.ValidationError):
	pass


class Timesheet(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		from erpnext.projects.doctype.timesheet_detail.timesheet_detail import TimesheetDetail

		amended_from: DF.Link | None
		base_total_billable_amount: DF.Currency
		base_total_billed_amount: DF.Currency
		base_total_costing_amount: DF.Currency
		company: DF.Link | None
		currency: DF.Link | None
		customer: DF.Link | None
		department: DF.Link | None
		employee: DF.Link | None
		employee_name: DF.Data | None
		end_date: DF.Date | None
		exchange_rate: DF.Float
		naming_series: DF.Literal["TS-.YYYY.-"]
		note: DF.TextEditor | None
		parent_project: DF.Link | None
		per_billed: DF.Percent
		sales_invoice: DF.Link | None
		start_date: DF.Date | None
		status: DF.Literal["Draft", "Submitted", "Billed", "Payslip", "Completed", "Cancelled"]
		time_logs: DF.Table[TimesheetDetail]
		title: DF.Data | None
		total_billable_amount: DF.Currency
		total_billable_hours: DF.Float
		total_billed_amount: DF.Currency
		total_billed_hours: DF.Float
		total_costing_amount: DF.Currency
		total_hours: DF.Float
		user: DF.Link | None
	# end: auto-generated types

	def validate(self):
		self.set_status()
		self.validate_dates()
		self.calculate_hours()
		self.validate_time_logs()
		self.update_cost()
		self.calculate_total_amounts()
		self.calculate_percentage_billed()
		self.set_dates()
		self._link_employee_compliance_report()

	def _link_employee_compliance_report(self):
		"""
		Finds and links an Employee Compliance Report to this Timesheet if:
		- The Timesheet has an employee and a start_date.
		- An Employee Compliance Report exists for the same employee and its report_date
		  matches the Timesheet's start_date.
		- Only links if a single, unique, submitted Employee Compliance Report is found.
		"""
		# IMPORTANT: Replace 'custom_employee_compliance_report' with your actual fieldname
		link_field_name = "employee_compliance_report"

		if not hasattr(self, link_field_name):
			# Field doesn't exist on the doctype, log an error or raise it.
			# This prevents errors if the custom field is not yet created or named differently.
			frappe.log_error(
				title="Timesheet Link Error",
				message=f"Custom field '{link_field_name}' not found in Timesheet doctype. Cannot link Employee Compliance Report.",
			)
			return

		if not self.employee or not self.start_date:
			setattr(self, link_field_name, None)
			return

		# Assuming Timesheets are daily, so start_date is the relevant date to match report_date
		report_date_to_match = self.start_date

		try:
			matching_reports = frappe.get_all(
				"Employee Compliance Report",
				filters={
					"employee": self.employee,
					"report_date": report_date_to_match,
				},
				fields=["name"],
				limit_page_length=2,  # Fetch max 2 to check for uniqueness
			)

			if len(matching_reports) == 1:
				setattr(self, link_field_name, matching_reports[0].name)
			else:
				setattr(self, link_field_name, None)
				if len(matching_reports) > 1:
					frappe.log_error(
						title="Multiple Employee Compliance Reports for Timesheet Link",
						message=f"Timesheet {self.name} found multiple Employee Compliance Reports for employee {self.employee} and date {report_date_to_match}.",
					)
		except Exception as e:
			setattr(self, link_field_name, None)
			frappe.log_error(
				title="Employee Compliance Report Link Exception",
				message=f"Error linking Employee Compliance Report for Timesheet {self.name}: {str(e)}",
			)

	def calculate_hours(self):
		for row in self.time_logs:
			if row.to_time and row.from_time:
				row.hours = time_diff_in_hours(row.to_time, row.from_time)

	def calculate_total_amounts(self):
		self.total_hours = 0.0
		self.total_billable_hours = 0.0
		self.total_billed_hours = 0.0
		self.total_billable_amount = self.base_total_billable_amount = 0.0
		self.total_costing_amount = self.base_total_costing_amount = 0.0
		self.total_billed_amount = self.base_total_billed_amount = 0.0

		for d in self.get("time_logs"):
			self.update_billing_hours(d)
			self.update_time_rates(d)

			self.total_hours += flt(d.hours)
			self.total_costing_amount += flt(d.costing_amount)
			self.base_total_costing_amount += flt(d.base_costing_amount)
			if d.is_billable:
				self.total_billable_hours += flt(d.billing_hours)
				self.total_billable_amount += flt(d.billing_amount)
				self.base_total_billable_amount += flt(d.base_billing_amount)
				self.total_billed_amount += flt(d.billing_amount) if d.sales_invoice else 0.0
				self.base_total_billed_amount += flt(d.base_billing_amount) if d.sales_invoice else 0.0
				self.total_billed_hours += flt(d.billing_hours) if d.sales_invoice else 0.0

	def calculate_percentage_billed(self):
		self.per_billed = 0
		if self.total_billed_amount > 0 and self.total_billable_amount > 0:
			self.per_billed = (self.total_billed_amount * 100) / self.total_billable_amount
		elif self.total_billed_hours > 0 and self.total_billable_hours > 0:
			self.per_billed = (self.total_billed_hours * 100) / self.total_billable_hours

	def update_billing_hours(self, args):
		if args.is_billable:
			if flt(args.billing_hours) == 0.0:
				args.billing_hours = args.hours
			elif flt(args.billing_hours) > flt(args.hours):
				frappe.msgprint(
					_("Warning - Row {0}: Billing Hours are more than Actual Hours").format(args.idx),
					indicator="orange",
					alert=True,
				)
		else:
			args.billing_hours = 0

	def set_status(self):
		self.status = {"0": "Draft", "1": "Submitted", "2": "Cancelled"}[str(self.docstatus or 0)]

		if flt(self.per_billed, self.precision("per_billed")) >= 100.0:
			self.status = "Billed"

		if self.sales_invoice:
			self.status = "Completed"

	def set_dates(self):
		if self.docstatus < 2 and self.time_logs:
			start_date = min(getdate(d.from_time) for d in self.time_logs)
			end_date = max(getdate(d.to_time) for d in self.time_logs)

			if start_date and end_date:
				self.start_date = getdate(start_date)
				self.end_date = getdate(end_date)

	def before_cancel(self):
		self.set_status()

	def on_cancel(self):
		self.update_task_and_project()

	def on_submit(self):
		self.validate_mandatory_fields()
		self.update_task_and_project()

	def validate_mandatory_fields(self):
		for data in self.time_logs:
			if not data.from_time and not data.to_time:
				frappe.throw(_("Row {0}: From Time and To Time is mandatory.").format(data.idx))

			if not data.activity_type and self.employee:
				frappe.throw(_("Row {0}: Activity Type is mandatory.").format(data.idx))

			if flt(data.hours) == 0.0:
				frappe.throw(_("Row {0}: Hours value must be greater than zero.").format(data.idx))

	def update_task_and_project(self):
		tasks, projects = [], []

		for data in self.time_logs:
			if data.task and data.task not in tasks:
				task = frappe.get_doc("Task", data.task)
				task.update_time_and_costing()
				task.save(ignore_permissions=True)
				tasks.append(data.task)

			if data.project and data.project not in projects:
				projects.append(data.project)

		for project in projects:
			project_doc = frappe.get_doc("Project", project)
			project_doc.update_project()
			project_doc.save(ignore_permissions=True)

	def validate_dates(self):
		for data in self.time_logs:
			if data.from_time and data.to_time and time_diff_in_hours(data.to_time, data.from_time) < 0:
				frappe.throw(_("To date cannot be before from date"))

	def validate_time_logs(self):
		for data in self.get("time_logs"):
			self.set_to_time(data)
			self.validate_overlap(data)
			self.set_project(data)
			self.validate_project(data)

	def set_to_time(self, data):
		if not (data.from_time and data.hours):
			return

		_to_time = get_datetime(add_to_date(data.from_time, hours=data.hours, as_datetime=True))
		if abs(time_diff_in_seconds(_to_time, data.to_time)) >= 1:
			data.to_time = _to_time

	def validate_overlap(self, data):
		settings = frappe.get_single("Projects Settings")
		self.validate_overlap_for("user", data, self.user, settings.ignore_user_time_overlap)
		self.validate_overlap_for("employee", data, self.employee, settings.ignore_employee_time_overlap)

	def set_project(self, data):
		data.project = data.project or frappe.db.get_value("Task", data.task, "project")

	def validate_project(self, data):
		if self.parent_project and self.parent_project != data.project:
			frappe.throw(
				_("Row {0}: Project must be same as the one set in the Timesheet: {1}.").format(
					data.idx, self.parent_project
				)
			)

	def validate_overlap_for(self, fieldname, args, value, ignore_validation=False):
		if not value or ignore_validation:
			return

		existing = self.get_overlap_for(fieldname, args, value)
		if existing:
			frappe.throw(
				_("Row {0}: From Time and To Time of {1} is overlapping with {2}").format(
					args.idx, self.name, existing.name
				),
				OverlapError,
			)

	def get_overlap_for(self, fieldname, args, value):
		timesheet = frappe.qb.DocType("Timesheet")
		timelog = frappe.qb.DocType("Timesheet Detail")

		from_time = get_datetime(args.from_time)
		to_time = get_datetime(args.to_time)

		existing = (
			frappe.qb.from_(timesheet)
			.join(timelog)
			.on(timelog.parent == timesheet.name)
			.select(
				timesheet.name.as_("name"), timelog.from_time.as_("from_time"), timelog.to_time.as_("to_time")
			)
			.where(
				(timelog.name != (args.name or "No Name"))
				& (timesheet.name != (args.parent or "No Name"))
				& (timesheet.docstatus < 2)
				& (timesheet[fieldname] == value)
				& (
					((from_time > timelog.from_time) & (from_time < timelog.to_time))
					| ((to_time > timelog.from_time) & (to_time < timelog.to_time))
					| ((from_time <= timelog.from_time) & (to_time >= timelog.to_time))
				)
			)
		).run(as_dict=True)

		if self.check_internal_overlap(fieldname, args):
			return self

		return existing[0] if existing else None

	def check_internal_overlap(self, fieldname, args):
		for time_log in self.time_logs:
			if not (time_log.from_time and time_log.to_time and args.from_time and args.to_time):
				continue

			from_time = get_datetime(time_log.from_time)
			to_time = get_datetime(time_log.to_time)
			args_from_time = get_datetime(args.from_time)
			args_to_time = get_datetime(args.to_time)

			if (
				(args.get(fieldname) == time_log.get(fieldname))
				and (args.idx != time_log.idx)
				and (
					(args_from_time > from_time and args_from_time < to_time)
					or (args_to_time > from_time and args_to_time < to_time)
					or (args_from_time <= from_time and args_to_time >= to_time)
				)
			):
				return True
		return False

	def update_cost(self):
		for data in self.time_logs:
			if data.activity_type or data.is_billable:
				rate = get_activity_cost(self.employee, data.activity_type)
				hours = data.billing_hours or 0
				costing_hours = data.hours or 0
				if rate:
					data.billing_rate = (
						flt(rate.get("billing_rate")) if flt(data.billing_rate) == 0 else data.billing_rate
					)
					data.costing_rate = (
						flt(rate.get("costing_rate")) if flt(data.costing_rate) == 0 else data.costing_rate
					)
					data.billing_amount = data.billing_rate * hours
					data.costing_amount = data.costing_rate * costing_hours

					exchange_rate = flt(self.get("exchange_rate")) or 1.0
					data.base_billing_rate = flt(
						data.billing_rate * exchange_rate, data.precision("base_billing_rate")
					)
					data.base_costing_rate = flt(
						data.costing_rate * exchange_rate, data.precision("base_costing_rate")
					)
					data.base_billing_amount = flt(
						data.billing_amount * exchange_rate, data.precision("base_billing_amount")
					)
					data.base_costing_amount = flt(
						data.costing_amount * exchange_rate, data.precision("base_costing_amount")
					)

	def update_time_rates(self, ts_detail):
		if not ts_detail.is_billable:
			ts_detail.billing_rate = 0.0


@frappe.whitelist()
def get_projectwise_timesheet_data(project=None, parent=None, from_time=None, to_time=None):
	condition = ""
	if project:
		condition += "AND tsd.project = %(project)s "
	if parent:
		condition += "AND tsd.parent = %(parent)s "
	if from_time and to_time:
		condition += "AND CAST(tsd.from_time as DATE) BETWEEN %(from_time)s AND %(to_time)s"

	query = f"""
		SELECT
			tsd.name as name,
			tsd.parent as time_sheet,
			tsd.from_time as from_time,
			tsd.to_time as to_time,
			tsd.billing_hours as billing_hours,
			tsd.billing_amount as billing_amount,
			tsd.activity_type as activity_type,
			tsd.description as description,
			ts.currency as currency,
			tsd.project_name as project_name
		FROM `tabTimesheet Detail` tsd
			INNER JOIN `tabTimesheet` ts
			ON ts.name = tsd.parent
		WHERE
			tsd.parenttype = 'Timesheet'
			AND tsd.docstatus = 1
			AND tsd.is_billable = 1
			AND tsd.sales_invoice is NULL
			{condition}
		ORDER BY tsd.from_time ASC
	"""

	filters = {"project": project, "parent": parent, "from_time": from_time, "to_time": to_time}

	return frappe.db.sql(query, filters, as_dict=1)


@frappe.whitelist()
def get_timesheet_detail_rate(timelog, currency):
	ts = frappe.qb.DocType("Timesheet")
	ts_detail = frappe.qb.DocType("Timesheet Detail")

	timelog_detail = (
		frappe.qb.from_(ts_detail)
		.inner_join(ts)
		.on(ts.name == ts_detail.parent)
		.select(ts_detail.billing_amount.as_("billing_amount"), ts.currency.as_("currency"))
		.where(ts_detail.name == timelog)
		.run(as_dict=1)
	)[0]

	if timelog_detail.currency:
		exchange_rate = get_exchange_rate(timelog_detail.currency, currency)

		return timelog_detail.billing_amount * exchange_rate
	return timelog_detail.billing_amount


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_timesheet(doctype, txt, searchfield, start, page_len, filters):
	if not filters:
		filters = {}

	condition = ""
	if filters.get("project"):
		condition = "and tsd.project = %(project)s"

	return frappe.db.sql(
		f"""select distinct tsd.parent from `tabTimesheet Detail` tsd,
			`tabTimesheet` ts where
			ts.status in ('Submitted', 'Payslip') and tsd.parent = ts.name and
			tsd.docstatus = 1 and ts.total_billable_amount > 0
			and tsd.parent LIKE %(txt)s {condition}
			order by tsd.parent limit %(page_len)s offset %(start)s""",
		{
			"txt": "%" + txt + "%",
			"start": start,
			"page_len": page_len,
			"project": filters.get("project"),
		},
	)


@frappe.whitelist()
def get_timesheet_data(name, project):
	data = None
	if project and project != "":
		data = get_projectwise_timesheet_data(project, name)
	else:
		data = frappe.get_all(
			"Timesheet",
			fields=[
				"(total_billable_amount - total_billed_amount) as billing_amt",
				"total_billable_hours as billing_hours",
			],
			filters={"name": name},
		)
	return {
		"billing_hours": data[0].billing_hours if data else None,
		"billing_amount": data[0].billing_amt if data else None,
		"timesheet_detail": data[0].name if data and project and project != "" else None,
	}


@frappe.whitelist()
def make_sales_invoice(source_name, item_code=None, customer=None, currency=None):
	target = frappe.new_doc("Sales Invoice")
	timesheet = frappe.get_doc("Timesheet", source_name)

	if not timesheet.total_billable_hours:
		frappe.throw(_("Invoice can't be made for zero billing hour"))

	if timesheet.total_billable_hours == timesheet.total_billed_hours:
		frappe.throw(_("Invoice already created for all billing hours"))

	hours = flt(timesheet.total_billable_hours) - flt(timesheet.total_billed_hours)
	billing_amount = flt(timesheet.total_billable_amount) - flt(timesheet.total_billed_amount)
	billing_rate = billing_amount / hours

	target.company = timesheet.company
	target.project = timesheet.parent_project
	if customer:
		target.customer = customer
		default_price_list = frappe.get_value("Customer", customer, "default_price_list")
		if default_price_list:
			target.selling_price_list = default_price_list

	if currency:
		target.currency = currency

	if item_code:
		target.append("items", {"item_code": item_code, "qty": hours, "rate": billing_rate})

	for time_log in timesheet.time_logs:
		if time_log.is_billable:
			target.append(
				"timesheets",
				{
					"time_sheet": timesheet.name,
					"project_name": time_log.project_name,
					"from_time": time_log.from_time,
					"to_time": time_log.to_time,
					"billing_hours": time_log.billing_hours,
					"billing_amount": time_log.billing_amount,
					"timesheet_detail": time_log.name,
					"activity_type": time_log.activity_type,
					"description": time_log.description,
				},
			)

	target.run_method("calculate_billing_amount_for_timesheet")
	target.run_method("set_missing_values")

	return target


@frappe.whitelist()
def get_activity_cost(employee=None, activity_type=None, currency=None):
	base_currency = frappe.defaults.get_global_default("currency")
	rate = frappe.db.get_values(
		"Activity Cost",
		{"employee": employee, "activity_type": activity_type},
		["costing_rate", "billing_rate"],
		as_dict=True,
	)
	if not rate:
		rate = frappe.db.get_values(
			"Activity Type",
			{"activity_type": activity_type},
			["costing_rate", "billing_rate"],
			as_dict=True,
		)
		if rate and currency and currency != base_currency:
			exchange_rate = get_exchange_rate(base_currency, currency)
			rate[0]["costing_rate"] = rate[0]["costing_rate"] * exchange_rate
			rate[0]["billing_rate"] = rate[0]["billing_rate"] * exchange_rate

	return rate[0] if rate else {}


@frappe.whitelist()
def get_events(start, end, filters=None):
	"""Returns events for Gantt / Calendar view rendering.
	:param start: Start date-time.
	:param end: End date-time.
	:param filters: Filters (JSON).
	"""
	filters = json.loads(filters)
	from frappe.desk.calendar import get_event_conditions

	conditions = get_event_conditions("Timesheet", filters)

	return frappe.db.sql(
		"""select `tabTimesheet Detail`.name as name,
			`tabTimesheet Detail`.docstatus as status, `tabTimesheet Detail`.parent as parent,
			from_time as start_date, hours, activity_type,
			`tabTimesheet Detail`.project, to_time as end_date,
			CONCAT(`tabTimesheet Detail`.parent, ' (', ROUND(hours,2),' hrs)') as title
		from `tabTimesheet Detail`, `tabTimesheet`
		where `tabTimesheet Detail`.parent = `tabTimesheet`.name
			and `tabTimesheet`.docstatus < 2
			and (from_time <= %(end)s and to_time >= %(start)s) {conditions} {match_cond}
		""".format(conditions=conditions, match_cond=get_match_cond("Timesheet")),
		{"start": start, "end": end},
		as_dict=True,
		update={"allDay": 0},
	)


def get_timesheets_list(doctype, txt, filters, limit_start, limit_page_length=20, order_by="modified"):
	user = frappe.session.user
	# find customer name from contact.
	customer = ""

	contact = frappe.db.exists("Contact", {"user": user})
	if contact:
		# find customer
		contact = frappe.get_doc("Contact", contact)
		customer = contact.get_link_for("Customer")

	if customer:
		sales_invoices = frappe.get_all("Sales Invoice", filters={"customer": customer}, pluck="name")
		projects = frappe.get_all("Project", filters={"customer": customer}, pluck="name")

		# Return timesheet related data to web portal.
		table = frappe.qb.DocType("Timesheet")
		child_table = frappe.qb.DocType("Timesheet Detail")
		query = (
			frappe.qb.from_(table)
			.join(child_table)
			.on(table.name == child_table.parent)
			.select(
				table.name,
				child_table.activity_type,
				table.status,
				child_table.billing_hours,
				(table.sales_invoice | child_table.sales_invoice).as_("sales_invoice"),
				child_table.project,
			)
			.orderby(table.end_date)
			.limit(limit_page_length)
			.offset(limit_start)
		)

		conditions = []
		if sales_invoices:
			conditions.extend(
				[table.sales_invoice.isin(sales_invoices), child_table.sales_invoice.isin(sales_invoices)]
			)
		if projects:
			conditions.append(child_table.project.isin(projects))

		if conditions:
			query = query.where(frappe.qb.terms.Criterion.any(conditions))

		return query.run(as_dict=True)
	else:
		return {}


def get_list_context(context=None):
	return {
		"show_sidebar": True,
		"show_search": True,
		"no_breadcrumbs": True,
		"title": _("Timesheets"),
		"get_list": get_timesheets_list,
		"row_template": "templates/includes/timesheet/timesheet_row.html",
	}


# --- Helper Functions for Clockify Sync ---


def _get_erpnext_project_map(clockify_project_api_ids: list) -> dict:
	"""Fetches ERPNext projects and maps their Clockify API ID to ERPNext project name."""
	erpnext_project_map = {}
	if not clockify_project_api_ids:
		return erpnext_project_map

	projects = frappe.get_all(
		"Project",
		filters={"clockify_project_id": ["in", list(set(clockify_project_api_ids))]},
		fields=["name", "clockify_project_id"],
	)
	for p in projects:
		if p.clockify_project_id:
			erpnext_project_map[p.clockify_project_id] = p.name
	return erpnext_project_map


def _get_active_timesheets_data(employee_id: str, date_to_sync_obj: object) -> tuple[set, dict]:
	"""Fetches active timesheets for the day for an employee.
	Returns:
			all_active_ts_names (set): Names of all active timesheets for the employee/day.
			project_to_ts_info_map (dict): Maps ERPNext project name to its active timesheet info (name, docstatus).
	"""
	filters = {
		"employee": employee_id,
		"start_date": date_to_sync_obj,
		"end_date": date_to_sync_obj,
		"docstatus": ["in", [0, 1]],
	}
	active_ts_docs = frappe.get_all(
		"Timesheet", filters=filters, fields=["name", "parent_project", "docstatus"]
	)

	all_active_ts_names = {ts.get("name") for ts in active_ts_docs}
	project_to_ts_info_map = {}
	for ts in active_ts_docs:
		if ts.get("parent_project"):
			project_to_ts_info_map[ts.get("parent_project")] = {
				"name": ts.get("name"),
				"docstatus": ts.get("docstatus"),
			}
	return all_active_ts_names, project_to_ts_info_map


def _get_or_create_task_map(
	clockify_time_entries: list, erpnext_project_name: str, company: str, script_log_title: str
) -> dict:
	"""Gets or creates ERPNext tasks for Clockify time entries of a project.
	Returns a map: (clockify_task_api_id, clockify_task_subject) -> erpnext_task_name.
	"""
	task_map = {}
	if not erpnext_project_name or not clockify_time_entries:
		return task_map

	unique_clockify_tasks = {}
	for entry in clockify_time_entries:
		api_id = entry.get("task_api_id")
		subject = entry.get("task_subject", "").strip()
		if api_id or subject:  # Only process if we have some identifier
			unique_clockify_tasks[(api_id, subject)] = None  # Value will be ERPNext task name

	if not unique_clockify_tasks:
		return task_map

	clockify_task_ids_to_fetch = [key[0] for key in unique_clockify_tasks if key[0]]
	if clockify_task_ids_to_fetch:
		existing_tasks_by_api_id = frappe.get_all(
			"Task",
			filters={
				"clockify_task_id": ["in", list(set(clockify_task_ids_to_fetch))],
				"project": erpnext_project_name,
			},
			fields=["name", "clockify_task_id", "subject"],
		)
		for task in existing_tasks_by_api_id:
			for key_api_id, key_subject in unique_clockify_tasks:
				if key_api_id == task.clockify_task_id:
					task_map[(key_api_id, key_subject)] = task.name

	for (api_id, subject), erpnext_name in unique_clockify_tasks.items():
		if (api_id, subject) in task_map:
			continue

		if subject and not api_id:
			task_name_by_subject = frappe.db.get_value(
				"Task", {"subject": subject, "project": erpnext_project_name}, "name"
			)
			if task_name_by_subject:
				task_map[(api_id, subject)] = task_name_by_subject
				if api_id and not frappe.db.get_value("Task", task_name_by_subject, "clockify_task_id"):
					try:
						frappe.db.set_value("Task", task_name_by_subject, "clockify_task_id", api_id)
					except Exception as e_set:
						frappe.log_error(
							message=f"Failed to set clockify_task_id on task {task_name_by_subject} found by subject: {e_set}",
							title=script_log_title,
						)
				continue

		if subject:
			try:
				task_doc = frappe.new_doc("Task")
				task_doc.subject = subject
				task_doc.project = erpnext_project_name
				task_doc.company = company
				task_doc.status = "Open"
				if api_id:
					task_doc.clockify_task_id = api_id
				task_doc.insert(ignore_permissions=True)
				task_map[(api_id, subject)] = task_doc.name
			except Exception as e_create:
				frappe.log_error(
					message=f"Task creation failed for subject '{subject}' (API ID: {api_id}) in project '{erpnext_project_name}': {e_create}",
					title=script_log_title,
				)
		elif api_id and not subject:
			frappe.log_error(
				message=f"Clockify Task API ID '{api_id}' provided without a subject/name for project '{erpnext_project_name}'. Cannot create task.",
				title=script_log_title,
			)
	return task_map


def _cancel_erpnext_timesheet(
	timesheet_name: str,
	employee_id: str,
	date_str_for_log: str,
	log_reason_prefix: str,
	script_log_title: str,
) -> bool:
	"""Cancels an ERPNext Timesheet (Draft or Submitted)."""
	try:
		ts_to_cancel_doc = frappe.get_doc("Timesheet", timesheet_name)
		ts_to_cancel_doc.flags.ignore_permissions = True

		if ts_to_cancel_doc.docstatus == 2:  # Already cancelled
			return True

		# If the document is already submitted, the standard .cancel() method is reliable.
		if ts_to_cancel_doc.docstatus == 1:
			ts_to_cancel_doc.cancel()

		# For a Draft document, the submit-then-cancel sequence within one transaction is
		# unreliable. We will perform the steps manually for robustness.
		elif ts_to_cancel_doc.docstatus == 0:
			ts_to_cancel_doc.submit()

			# Manually run the cancellation logic
			ts_to_cancel_doc.run_method("on_cancel")
			ts_to_cancel_doc.docstatus = 2
			ts_to_cancel_doc.save()

		frappe.logger(script_log_title).info(
			f"{log_reason_prefix}: Cancelled TS '{timesheet_name}' for Emp {employee_id}, Date {date_str_for_log}"
		)
		return True
	except Exception as e:
		frappe.log_error(
			message=f"Error during {log_reason_prefix.lower()} cancellation for TS '{timesheet_name}': {e}",
			title=script_log_title,
		)
		return False


def _populate_timesheet_details(
	timesheet_doc_to_populate: Document,
	time_entries_data: list,
	task_map: dict,
	erpnext_project_name: str,
	default_erpnext_activity_type: str,
	start_dt_for_report: object,
	script_log_title: str,
):
	"""Populates time_logs for the given timesheet document."""
	for entry_data in time_entries_data:
		clockify_task_key = (entry_data.get("task_api_id"), entry_data.get("task_subject", "").strip())
		erpnext_task_name = task_map.get(clockify_task_key)

		if not erpnext_task_name and entry_data.get("task_subject"):
			print(
				f"WARN: ERPNext task not mapped for Clockify task (ID: {entry_data.get('task_api_id')}, Subject: {entry_data.get('task_subject')}) for project {erpnext_project_name}. Skipping this time log entry."
			)
			continue

		timesheet_doc_to_populate.append(
			"time_logs",
			{
				"activity_type": default_erpnext_activity_type,
				"task": erpnext_task_name,
				"description": entry_data["description"],
				"hours": entry_data["hours"],
				"project": erpnext_project_name,
				"from_time": start_dt_for_report,
				"to_time": add_to_date(start_dt_for_report, hours=entry_data["hours"], as_datetime=True),
			},
		)


def _handle_positive_hours_project(
	employee_doc: Document,
	erpnext_project_name: str,
	date_to_sync_obj: object,
	start_dt_for_report: object,
	current_project_total_hours: float,
	time_entries_for_project: list,
	existing_ts_info: dict,  # { "name": str, "docstatus": int } or None
	task_map: dict,
	default_activity_type: str,
	script_log_title: str,
) -> str | None:
	"""Handles creation/update of timesheet when Clockify reports > 0 hours."""
	timesheet_to_process = None
	is_newly_created_ts = False
	existing_active_ts_name = existing_ts_info.get("name") if existing_ts_info else None
	existing_ts_docstatus = existing_ts_info.get("docstatus") if existing_ts_info else None

	if existing_active_ts_name:
		if existing_ts_docstatus == 1:  # Submitted: Cancel this one, new one will be created
			print(
				f"DEBUG: Existing TS {existing_active_ts_name} for Proj {erpnext_project_name} is Submitted. Cancelling before replacement."
			)
			try:
				original_ts_doc = frappe.get_doc("Timesheet", existing_active_ts_name)
				original_ts_doc.flags.ignore_permissions = True
				original_ts_doc.docstatus = 2
				original_ts_doc.save(ignore_permissions=True)
				frappe.logger(script_log_title).info(
					f"Cancelled submitted TS '{original_ts_doc.name}' for Emp {employee_doc.name}, Proj {erpnext_project_name} to be replaced."
				)
				# The name is added to processed_timesheet_names by the caller if this helper returns a new name
			except Exception as e_cancel:
				frappe.log_error(
					f"Failed to cancel submitted TS {existing_active_ts_name} for replacement: {e_cancel}",
					title=script_log_title,
				)
				# Proceed to create a new one anyway, orphan logic might catch the old one if cancellation failed badly.
		elif existing_ts_docstatus == 0:  # Draft: Update this one
			print(
				f"DEBUG: Updating existing Draft TS {existing_active_ts_name} for Proj {erpnext_project_name}."
			)
			try:
				timesheet_to_process = frappe.get_doc("Timesheet", existing_active_ts_name)
				timesheet_to_process.set("time_logs", [])
				is_newly_created_ts = False
			except Exception as e_get_draft:
				frappe.log_error(
					message=f"Failed to get draft TS {existing_active_ts_name} for update: {e_get_draft}. Will create new.",
					title=script_log_title,
				)
				timesheet_to_process = None  # Force new creation

	if not timesheet_to_process:  # Create new if no existing draft to update or submitted one was cancelled
		timesheet_to_process = frappe.new_doc("Timesheet")
		timesheet_to_process.employee = employee_doc.name
		timesheet_to_process.parent_project = erpnext_project_name
		timesheet_to_process.company = employee_doc.company
		timesheet_to_process.start_date = date_to_sync_obj
		timesheet_to_process.end_date = date_to_sync_obj
		is_newly_created_ts = True
		print(f"DEBUG: Prepared new TS for Proj: {erpnext_project_name}")

	if not timesheet_to_process:
		print(
			f"ERROR: Timesheet document could not be prepared for {erpnext_project_name} with positive hours."
		)
		return None

	_populate_timesheet_details(
		timesheet_to_process,
		time_entries_for_project,
		task_map,
		erpnext_project_name,
		default_activity_type,
		start_dt_for_report,
		script_log_title,
	)
	timesheet_to_process.total_hours = current_project_total_hours

	try:
		timesheet_to_process.flags.ignore_permissions = True
		timesheet_to_process.save()
		log_action = (
			"created (as Draft)"
			if is_newly_created_ts
			else f"updated (Status: {timesheet_to_process.status})"
		)
		frappe.logger(script_log_title).info(
			f"Timesheet '{timesheet_to_process.name}' {log_action} for Emp {employee_doc.name}, Proj {erpnext_project_name}, Date {date_to_sync_obj.strftime('%Y-%m-%d')} (TH: {timesheet_to_process.total_hours})"
		)
		return timesheet_to_process.name
	except Exception as e_save:
		frappe.log_error(
			message=f"Save failed for TS for Emp {employee_doc.name}, Proj '{erpnext_project_name}'. Error: {e_save}",
			title=script_log_title,
		)
		return None


def _handle_zero_hours_project(
	existing_active_ts_name: str | None,
	employee_id: str,
	erpnext_project_name: str,
	date_to_sync_str: str,
	script_log_title: str,
) -> str | None:
	"""Handles cancellation of existing timesheet if Clockify reports 0 hours."""
	if existing_active_ts_name:
		if _cancel_erpnext_timesheet(
			existing_active_ts_name,
			employee_id,
			date_to_sync_str,
			f"0 hrs for {erpnext_project_name}",
			script_log_title,
		):
			return existing_active_ts_name
	return None


# --- Main Sync Function ---
@frappe.whitelist()
def sync_single_employee_clockify_to_timesheet(employee_id, date_to_sync_str):
	"""
	Syncs Clockify time entries for a single employee for a specific date.
	Strategy:
	1. Fetch existing active (Draft/Submitted) ERPNext Timesheets for the employee/date.
	2. Fetch Clockify data for the employee/day.
	3. Process Clockify Projects:
	   - If Clockify project has hours > 0:
			 - If new TS: Create as Draft and save.
			 - If existing TS (Draft/Submitted): Update details and save (docstatus unchanged by this script).
	   - If Clockify project has 0 hours:
			 - If existing active TS found:
			   - If Draft: Submit, then set docstatus = 2 and Save.
			   - If Submitted: Set docstatus = 2 and Save.
			 - Else, do nothing.
	   - Mark TS name as processed.
	4. Reconcile: For orphaned active ERPNext Timesheets:
	   - If Draft: Submit, then set docstatus = 2 and Save.
	   - If Submitted: Set docstatus = 2 and Save.
	"""
	script_log_title = "Clockify Timesheet Sync"
	date_to_sync_obj = getdate(date_to_sync_str)

	try:
		all_active_ts_names_for_day, project_to_ts_info_map = _get_active_timesheets_data(
			employee_id, date_to_sync_obj
		)
	except Exception as e:
		frappe.log_error(
			message=f"Error fetching active timesheets for {employee_id} on {date_to_sync_str}: {e}",
			title=script_log_title,
		)
		return

	processed_timesheet_names = set()

	default_activity_type_name = "Task"
	default_erpnext_activity_type = frappe.db.get_value(
		"Activity Type", {"name": default_activity_type_name}, "name"
	)
	if not default_erpnext_activity_type:
		try:
			activity_type_doc = frappe.new_doc("Activity Type")
			activity_type_doc.name = default_activity_type_name
			activity_type_doc.activity_type = default_activity_type_name
			activity_type_doc.insert(ignore_permissions=True)
			default_erpnext_activity_type = activity_type_doc.name
			frappe.logger(script_log_title).info(
				f"Successfully created Activity Type: {default_erpnext_activity_type}"
			)
		except Exception as e:
			frappe.log_error(
				message=f"Failed to create Activity Type '{default_activity_type_name}'. Error: {e}. Please create it manually. Aborting sync for {employee_id}.",
				title=script_log_title,
			)
			return

	(
		custom_api_key,
		custom_user_id,
		workspace_ids,
		employee_doc,
		_user_id,
	) = get_employee_clockify_details(employee_id)

	if not custom_api_key or not workspace_ids:
		frappe.log_error(
			message=f"Clockify system settings are missing for Emp {employee_id}",
			title=script_log_title,
		)
		return

	if not custom_user_id:
		frappe.logger(script_log_title).info(
			f"Clockify user ID is missing for Emp {employee_id}"
		)
		return


	start_dt_for_report = get_datetime(f"{date_to_sync_str} 00:00:00")
	all_clockify_project_data_from_report = []
	if custom_api_key and workspace_ids and custom_user_id:
		for workspace_id in workspace_ids:
			report_task_id = get_clockify_report_task_id(
				workspace_id,
				start_dt_for_report,
				get_datetime(f"{date_to_sync_str} 23:59:59"),
				custom_user_id,
				custom_api_key,
			)
			if not report_task_id:
				continue
			report_result = get_clockify_report_result(workspace_id, report_task_id, custom_api_key)
			if report_result and report_result.get("groupOne"):
				all_clockify_project_data_from_report.extend(report_result["groupOne"])
			else:
				continue

	clockify_project_api_ids_from_report = [
		p.get("_id") for p in all_clockify_project_data_from_report if p.get("_id")
	]
	erpnext_project_map = _get_erpnext_project_map(clockify_project_api_ids_from_report)

	for clockify_project_entry in all_clockify_project_data_from_report:
		clockify_project_api_id = clockify_project_entry.get("_id")
		erpnext_project_name = erpnext_project_map.get(clockify_project_api_id)

		if not erpnext_project_name:
			continue

		current_project_total_hours_from_clockify = 0
		time_entries_for_this_project_list = []
		if clockify_project_entry.get("children"):
			for task_level_entry in clockify_project_entry["children"]:
				if task_level_entry.get("children"):
					for time_entry_record in task_level_entry["children"]:
						duration_seconds = time_entry_record.get("duration", 0)
						if duration_seconds > 0:
							hours = flt(duration_seconds / 3600.0, 2)
							if hours > 0:
								current_project_total_hours_from_clockify += hours
								time_entries_for_this_project_list.append(
									{
										"task_api_id": task_level_entry.get("_id"),
										"task_subject": task_level_entry.get("name", "").strip(),
										"description": time_entry_record.get("name", "").strip(),
										"hours": hours,
									}
								)

		company_for_tasks = (
			employee_doc.company if employee_doc else None
		)  # employee_doc should be valid if we are here

		task_map = _get_or_create_task_map(
			time_entries_for_this_project_list, erpnext_project_name, company_for_tasks, script_log_title
		)
		existing_ts_info = project_to_ts_info_map.get(erpnext_project_name)

		processed_ts_name_for_project = None
		if current_project_total_hours_from_clockify > 0:
			processed_ts_name_for_project = _handle_positive_hours_project(
				employee_doc,
				erpnext_project_name,
				date_to_sync_obj,
				start_dt_for_report,
				current_project_total_hours_from_clockify,
				time_entries_for_this_project_list,
				existing_ts_info,
				task_map,
				default_erpnext_activity_type,
				script_log_title,
			)
		else:  # 0 hours from Clockify for this project
			existing_ts_name_for_zero_hrs = existing_ts_info.get("name") if existing_ts_info else None
			processed_ts_name_for_project = _handle_zero_hours_project(
				existing_ts_name_for_zero_hrs,
				employee_id,
				erpnext_project_name,
				date_to_sync_str,
				script_log_title,
			)

		if processed_ts_name_for_project:
			processed_timesheet_names.add(processed_ts_name_for_project)
			if existing_ts_info and existing_ts_info.get("name") != processed_ts_name_for_project:
				# If a new timesheet replaced an old one (e.g. submitted was cancelled, new draft created)
				# Ensure the old one (if it was different) is also marked as processed (implicitly by being cancelled and replaced)
				processed_timesheet_names.add(existing_ts_info.get("name"))

	# Reconcile orphaned timesheets
	orphaned_timesheet_names = all_active_ts_names_for_day - processed_timesheet_names
	for orphaned_ts_name in orphaned_timesheet_names:
		_cancel_erpnext_timesheet(
			orphaned_ts_name, employee_id, date_to_sync_str, "Orphaned", script_log_title
		)


def _bulk_sync_clockify(from_date, to_date):
	"""
	Internal function to sync clockify data for all employees for a given date range.
	This is intended to be run in a background job.
	"""
	script_log_title = "Clockify Bulk Timesheet Sync"
	from_date_obj = getdate(from_date)
	to_date_obj = getdate(to_date)

	active_employees = get_all_active_employees()

	if not active_employees:
		frappe.logger(script_log_title).info(
			"No active employees found with 'custom_clockify_user_id' set. Exiting bulk sync."
		)
		return

	current_date = from_date_obj
	while current_date <= to_date_obj:
		date_to_process_str = current_date.strftime("%Y-%m-%d")
		for emp in active_employees:
			try:
				sync_single_employee_clockify_to_timesheet(emp["name"], date_to_process_str)
			except Exception as e:
				frappe.log_error(
					message=f"Error in bulk sync for Emp {emp['name']} on {date_to_process_str}: {e}",
					title=f"{script_log_title} - Employee Error",
				)

		current_date = add_to_date(current_date, days=1)

	frappe.db.commit()
	frappe.logger(script_log_title).info(
		f"Clockify bulk sync completed for date range: {from_date} to {to_date}"
	)


@frappe.whitelist()
def bulk_sync_clockify_timesheets(from_date, to_date):
	"""
	Enqueue a background job to sync Clockify timesheets for all active employees
	for a given date range.
	"""
	frappe.enqueue(
		_bulk_sync_clockify,
		queue="long",
		timeout=1800,
		from_date=from_date,
		to_date=to_date,
	)
	frappe.msgprint(
		_("Clockify sync has been queued for the date range. This will run in the background."),
		title="Sync Queued",
		indicator="green",
	)


# --- Scheduled Job Function ---
def run_daily_clockify_sync():
	"""
	Scheduled job to sync Clockify data for all active employees for today.
	"""
	script_log_title = "Clockify Daily Timesheet Sync - Main"
	# date_to_process_str = "2025-06-03"
	date_to_process_str = frappe.utils.add_days(frappe.utils.nowdate(), -1)  # Sync for yesterday

	frappe.logger(script_log_title).info(f"Starting Clockify daily sync for date: {date_to_process_str}")

	active_employees = get_all_active_employees()

	if not active_employees:
		frappe.logger(script_log_title).info(
			"No active employees found with 'custom_clockify_user_id' set. Exiting sync."
		)
		return

	for emp in active_employees:
		frappe.logger(script_log_title).info(f"Processing sync for employee: {emp['name']}")
		try:
			sync_single_employee_clockify_to_timesheet(emp["name"], date_to_process_str)
		except Exception as e:
			# Catching any unexpected errors during the processing for a single employee
			frappe.log_error(
				message=f"Unhandled error syncing Clockify for employee {emp['name']} on {date_to_process_str}: {e}",
				title=f"{script_log_title} - Employee Error for {emp['name']}",
			)

	try:
		frappe.db.commit()  # Commit all changes at the end of the batch
		frappe.logger(script_log_title).info(
			f"Clockify daily sync completed and committed for date: {date_to_process_str}"
		)
	except Exception as e:
		frappe.log_error(
			message=f"Error committing changes at the end of Clockify sync: {e}", title=script_log_title
		)
		frappe.db.rollback()
