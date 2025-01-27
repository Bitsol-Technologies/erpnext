# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class ToolsandTechnologies(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		description: DF.SmallText | None
		service_company: DF.Literal["Amazon", "Google", "Microsoft", "Apple", "Unknown"]
		technology_name: DF.Data | None
		type: DF.Literal["Language", "Feature", "Framework", "Library", "Tool", "CloudService", "FileStorage", "DB", "CI/CD", "PaymentGateway", "Git"]
	# end: auto-generated types
	pass
