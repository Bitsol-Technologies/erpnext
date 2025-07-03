frappe.pages["editable_project_upd"].on_page_load = function (wrapper) {
	let page_data = [];

	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Project Update Summary"),
		single_column: true,
	});

	// Filters
	const project_field = page.add_field({
		label: "Project",
		fieldtype: "Link",
		fieldname: "project",
		options: "Project",
		change: load_data,
	});

	const from_date_field = page.add_field({
		label: "From Date",
		fieldtype: "Date",
		fieldname: "from_date",
		change: load_data,
	});

	const to_date_field = page.add_field({
		label: "To Date",
		fieldtype: "Date",
		fieldname: "to_date",
		change: load_data,
	});

	// Refresh button
	page.add_button("Refresh", () => {
		load_data();
	});

	// Table container
	const table_container = $('<div id="table-container" style="margin-top: 20px;"></div>');
	const add_row_container = $('<div id="add-row-container" style="margin-top: 10px;"></div>');
	$(page.body).append(table_container, add_row_container);

	// Add custom styles for the date column
	const style = `
        <style>
            .date-cell {
                padding-left: 4px !important;
                padding-right: 4px !important;
                font-size: 13px !important;
                white-space: nowrap;
            }
            .action-cell {
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                gap: 4px;
            }
            .action-cell .btn {
                font-size: 12px !important;
                padding: 2px 8px !important;
                width: 60px;
            }
            .date-sort-arrows {
                font-size: 10px;
                color: #888;
                vertical-align: middle;
                margin-left: 2px;
                user-select: none;
            }
            .date-sort-arrows:hover {
                color: #333;
            }
        </style>
    `;
	$(style).appendTo("head");

	// The menu button is rendered by the framework after this script runs,
	// so we wait a moment and then hide it directly.
	setTimeout(() => {
		$(".page-actions .standard-actions .menu-btn-group").hide();
	}, 100);

	function show_add_new_dialog() {
		const dialog = new frappe.ui.Dialog({
			title: __("Add New Project Update"),
			fields: [
				{
					label: "Project",
					fieldname: "project",
					fieldtype: "Link",
					options: "Project",
					reqd: 1,
				},
				{
					label: "Date",
					fieldname: "date",
					fieldtype: "Date",
					reqd: 1,
					default: frappe.datetime.nowdate(),
				},
				{ label: "Done Task", fieldname: "done_task", fieldtype: "Text" },
				{ label: "Resources", fieldname: "recources", fieldtype: "Text" },
				{ label: "Risks / Red Flags", fieldname: "risks_red_flags", fieldtype: "Text" },
				{ label: "Decision / Support", fieldname: "decision_support", fieldtype: "Text" },
				{ label: "Previous Issues", fieldname: "previous_issues", fieldtype: "Text" },
				{ label: "Deadline", fieldname: "deadline", fieldtype: "Date" },
				{ label: "Deadline Description", fieldname: "deadline_desciption", fieldtype: "Text" },
				{ label: "Next Milestones", fieldname: "next_milestones", fieldtype: "Text" },
			],
			primary_action_label: __("Save"),
			primary_action(values) {
				frappe.call({
					method: "erpnext.projects.page.editable_project_upd.editable_project_upd.create_new_project_update",
					args: {
						data: values,
					},
					callback: function (r) {
						if (!r.exc) {
							frappe.show_alert({
								message: __("New update created successfully"),
								indicator: "green",
							});
							dialog.hide();
							load_data();
						}
					},
				});
			},
		});
		dialog.show();
	}

	function show_edit_dialog(row_data) {
		const dialog = new frappe.ui.Dialog({
			title: __("Edit Project Update"),
			fields: [
				{ label: "Date", fieldname: "date", fieldtype: "Date", default: row_data.date, reqd: 1 },
				{
					label: "Done Task",
					fieldname: "done_task",
					fieldtype: "Text",
					default: row_data.done_task,
				},
				{
					label: "Resources",
					fieldname: "recources",
					fieldtype: "Text",
					default: row_data.recources,
				},
				{
					label: "Risks / Red Flags",
					fieldname: "risks_red_flags",
					fieldtype: "Text",
					default: row_data.risks_red_flags,
				},
				{
					label: "Decision / Support",
					fieldname: "decision_support",
					fieldtype: "Text",
					default: row_data.decision_support,
				},
				{
					label: "Previous Issues",
					fieldname: "previous_issues",
					fieldtype: "Text",
					default: row_data.previous_issues,
				},
				{ label: "Deadline", fieldname: "deadline", fieldtype: "Date", default: row_data.deadline },
				{
					label: "Deadline Description",
					fieldname: "deadline_desciption",
					fieldtype: "Text",
					default: row_data.deadline_desciption,
				},
				{
					label: "Next Milestones",
					fieldname: "next_milestones",
					fieldtype: "Text",
					default: row_data.next_milestones,
				},
			],
			primary_action_label: __("Save"),
			primary_action(values) {
				const update_payload = { ...values, name: row_data.name };

				frappe.call({
					method: "erpnext.projects.page.editable_project_upd.editable_project_upd.save_project_update_changes",
					args: {
						updates: [update_payload],
					},
					callback: function (r) {
						if (r.message && r.message.status === "success") {
							frappe.show_alert({
								message: __("Update saved successfully"),
								indicator: "green",
							});
							dialog.hide();
							load_data();
						} else {
							frappe.msgprint(__("Save failed. Please refresh and try again."));
						}
					},
				});
			},
		});
		dialog.show();
	}

	function load_data() {
		frappe.call({
			method: "erpnext.projects.page.editable_project_upd.editable_project_upd.get_project_update_summary_data",
			args: {
				filters: {
					project: project_field.get_value(),
					from_date: from_date_field.get_value(),
					to_date: to_date_field.get_value(),
				},
			},
			callback: function (r) {
				page_data = r.message || [];
				render_table();
			},
		});
	}

	function render_table() {
		table_container.empty();
		if (page_data.length === 0) {
			table_container.html("<p>No project updates found.</p>");
			return;
		}

		// Sorting state
		if (typeof window.dateSortOrder === 'undefined') window.dateSortOrder = 'desc';

		const columns = [
			{ id: "date", label: `Date <span class='date-sort-arrows' style='cursor:pointer;'>${window.dateSortOrder === 'asc' ? '▲' : '▼'}</span>`, format: (v) => (v ? frappe.datetime.str_to_user(v) : "") },
			{
				id: "project_name",
				label: "Project",
				format: (v, row) => `<a href="/app/project/${row.parent}" target="_blank">${v}</a>`,
			},
			{ id: "done_task", label: "Done Task" },
			{ id: "previous_issues", label: "Previous Issues" },
			{ id: "risks_red_flags", label: "Risks" },
			{ id: "recources", label: "Resources" },
			{ id: "decision_support", label: "Decisions / Support" },
			{ id: "deadline", label: "Next Deadline", format: (v) => (v ? frappe.datetime.str_to_user(v) : "") },
			{ id: "next_milestones", label: "Next Milestones" },
			{ id: "action", label: "Action" },
		];

		// Sort page_data by date
		page_data.sort((a, b) => {
			const dateA = a.date || '';
			const dateB = b.date || '';
			if (window.dateSortOrder === 'asc') {
				return dateA.localeCompare(dateB);
			} else {
				return dateB.localeCompare(dateA);
			}
		});

		let table_html = `<table class="table table-bordered"><thead><tr>`;
		columns.forEach((col) => {
			const class_attr = col.id === "date" || col.id === "deadline" ? 'class="date-cell"' : "";
			table_html += `<th ${class_attr}>${col.label}</th>`;
		});
		table_html += `</tr></thead><tbody>`;

		page_data.forEach((row) => {
			table_html += `<tr>`;
			columns.forEach((col) => {
				let value = row[col.id];
				if (col.id === "action") {
					table_html += `<td class="action-cell">
                        <button class="btn btn-primary btn-edit" data-row-name="${row.name}">Edit</button>
                        <button class="btn btn-danger btn-delete" data-row-name="${row.name}">Delete</button>
                    </td>`;
				} else {
					const class_attr = col.id === "date" || col.id === "deadline" ? 'class="date-cell"' : "";
					let formatted_value = col.format ? col.format(value, row) : value || "";
					table_html += `<td ${class_attr}>${formatted_value}</td>`;
				}
			});
			table_html += `</tr>`;
		});

		table_html += `</tbody></table>`;
		table_container.html(table_html);

		// Add the "Add Row" button below the table
		add_row_container.html(`
            <button class="btn btn-primary btn-add-row">Add Row</button>
        `);

		// Add click event for date sort arrows
		table_container.find('.date-sort-arrows').on('click', function() {
			window.dateSortOrder = window.dateSortOrder === 'asc' ? 'desc' : 'asc';
			render_table();
		});
	}

	// Delegated event listeners
	table_container.on("click", ".btn-edit", function () {
		const row_name = $(this).attr("data-row-name");
		const row_data = page_data.find((row) => row.name === row_name);
		if (row_data) {
			show_edit_dialog(row_data);
		}
	});

	table_container.on("click", ".btn-delete", function () {
		const row_name = $(this).attr("data-row-name");
		frappe.confirm(__("Are you sure you want to delete this project update?"), () => {
			frappe.call({
				method: "erpnext.projects.page.editable_project_upd.editable_project_upd.delete_project_update",
				args: {
					name: row_name,
				},
				callback: function (r) {
					if (!r.exc) {
						frappe.show_alert({ message: __("Update deleted successfully"), indicator: "green" });
						load_data();
					}
				},
			});
		});
	});

	add_row_container.on("click", ".btn-add-row", function () {
		show_add_new_dialog();
	});

	// Initial data load
	load_data();
};
