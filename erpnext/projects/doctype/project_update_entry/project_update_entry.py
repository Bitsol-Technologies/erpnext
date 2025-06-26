# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class ProjectUpdateEntry(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		date: DF.Date | None
		deadline: DF.Date | None
		deadline_desciption: DF.SmallText | None
		decision_support: DF.SmallText | None
		done_task: DF.SmallText | None
		next_milestones: DF.SmallText | None
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		previous_issues: DF.SmallText | None
		recources: DF.SmallText | None
		risks_red_flags: DF.SmallText | None
	# end: auto-generated types
	pass
