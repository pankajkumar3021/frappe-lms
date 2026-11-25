// "Clear chat history" on the Raven Workspace and Raven Channel forms (lms.lms.raven_retention).
// Deletes every message, with its files, in the background. Raven Admins only.

function can_clear_chat() {
	return (
		frappe.user.has_role("System Manager") ||
		frappe.user.has_role("Raven Admin")
	);
}

frappe.ui.form.on("Raven Workspace", {
	refresh(frm) {
		if (frm.is_new() || !can_clear_chat()) return;
		frm.add_custom_button(__("Clear chat history"), () => {
			frappe.confirm(
				__(
					"Delete every message, with its photos and files, in all channels of {0}? Channels marked Keep chat history are left as they are. This cannot be undone.",
					[
						frappe.utils.escape_html(
							frm.doc.workspace_name || frm.doc.name
						),
					]
				),
				() =>
					frappe
						.call(
							"lms.lms.raven_retention.clear_workspace_history",
							{
								workspace: frm.doc.name,
							}
						)
						.then((r) => {
							const channels = r.message || [];
							frappe.msgprint(
								channels.length
									? __(
											"Clearing {0} channels in the background: {1}",
											[
												channels.length,
												channels
													.map((c) =>
														frappe.utils.escape_html(
															c
														)
													)
													.join(", "),
											]
									  )
									: __(
											"No channel in this workspace can be cleared."
									  )
							);
						})
			);
		});
	},
});

frappe.ui.form.on("Raven Channel", {
	refresh(frm) {
		if (frm.is_new() || frm.doc.is_thread || !can_clear_chat()) return;
		frm.add_custom_button(__("Clear chat history"), () => {
			frappe.confirm(
				__(
					"Delete every message, with its photos and files, in {0}? This cannot be undone.",
					[
						frappe.utils.escape_html(
							frm.doc.channel_name || frm.doc.name
						),
					]
				),
				() =>
					frappe
						.call("lms.lms.raven_retention.clear_channel_history", {
							channel: frm.doc.name,
						})
						.then(() =>
							frappe.show_alert(
								__(
									"Clearing the chat history in the background."
								)
							)
						)
			);
		});
	},
});
