"""How long Raven chat keeps its messages, and clearing a chat's history by hand.

Raven itself keeps every message forever. This app adds:

- **Delete messages after (days)** on each Raven Workspace: every day, messages older
  than that are deleted from the workspace's channels. 0 or empty keeps them.
- **Delete direct messages after (days)** in Raven Settings, the same for direct
  messages, which belong to no workspace.
- **Keep chat history** on a Raven Channel: the channel is left out of both, and out of
  clearing a whole workspace.
- **Clear chat history** buttons on the Raven Workspace and Raven Channel forms (for
  the year-end change of batches): delete every message, whatever its age.

Messages are deleted the way Raven deletes them (Document.delete, delete_permanently),
so their reactions, pins, polls, mentions, search index entries and attached files
(the File records and the files on disk) go with them. A deleted message that started
a thread takes the whole thread with it; its replies are deleted one by one first,
because Raven removes a thread's channel with a raw delete that would leave their files
behind.

The fields are custom fields on Raven's doctypes, created on migrate where Raven is
installed (ensure_retention_fields). Nothing here runs on a site without Raven.
"""

import frappe
from frappe import _
from frappe.utils import add_days, cint, now_datetime

WORKSPACE_DAYS_FIELD = "lms_delete_messages_after_days"
DIRECT_MESSAGE_DAYS_FIELD = "lms_delete_direct_messages_after_days"
KEEP_HISTORY_FIELD = "lms_keep_chat_history"

# Roles that may clear a chat's history by hand.
CLEAR_ROLES = ("System Manager", "Raven Admin")

# Messages deleted per transaction: a failure loses at most one batch of work, and a
# long run does not hold one huge transaction open.
BATCH_SIZE = 200

RETENTION_FIELDS = {
	"Raven Workspace": [
		{
			"fieldname": WORKSPACE_DAYS_FIELD,
			"label": "Delete messages after (days)",
			"fieldtype": "Int",
			"non_negative": 1,
			"insert_after": "only_admins_can_create_channels",
			"description": "Messages older than this are deleted every day from this workspace's "
			"channels, with their files. 0 or empty keeps them. Channels marked Keep chat history "
			"are left out.",
		}
	],
	"Raven Channel": [
		{
			"fieldname": KEEP_HISTORY_FIELD,
			"label": "Keep chat history",
			"fieldtype": "Check",
			"insert_after": "is_archived",
			"description": "Never delete this channel's messages automatically or when the whole "
			"workspace is cleared.",
		}
	],
	"Raven Settings": [
		{
			"fieldname": DIRECT_MESSAGE_DAYS_FIELD,
			"label": "Delete direct messages after (days)",
			"fieldtype": "Int",
			"non_negative": 1,
			"description": "Direct messages older than this are deleted every day, with their "
			"files. 0 or empty keeps them.",
		}
	],
}


def raven_installed() -> bool:
	return "raven" in frappe.get_installed_apps()


def ensure_retention_fields():
	"""after_migrate: the retention settings exist on Raven's doctypes."""
	if not raven_installed():
		return
	from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

	missing = {
		doctype: fields
		for doctype, fields in RETENTION_FIELDS.items()
		if not all(
			frappe.db.exists("Custom Field", {"dt": doctype, "fieldname": f["fieldname"]}) for f in fields
		)
	}
	if missing:
		create_custom_fields(missing, update=True)


# ---- deleting --------------------------------------------------------------------------


def _delete(names: list[str]) -> int:
	"""Delete these messages as Raven's own bulk delete does, oldest first, so the
	channel's last-message summary is recomputed once. Returns how many went."""
	messages = frappe.get_all(
		"Raven Message",
		filters={"name": ("in", names)},
		fields=["name", "is_thread"],
		order_by="creation asc",
	)
	deleted = 0
	for index, message in enumerate(messages):
		if message.is_thread:
			deleted += _delete_all(
				frappe.get_all("Raven Message", {"channel_id": message.name}, pluck="name")
			)
		if not frappe.db.exists("Raven Message", message.name):
			continue
		doc = frappe.get_doc("Raven Message", message.name)
		if index < len(messages) - 1:
			doc.flags.skip_channel_summary = True
		doc.delete(ignore_permissions=True, delete_permanently=True)
		deleted += 1
	return deleted


def _delete_all(names: list[str]) -> int:
	deleted = 0
	for start in range(0, len(names), BATCH_SIZE):
		deleted += _delete(names[start : start + BATCH_SIZE])
		frappe.db.commit()
	return deleted


def _thread_channels(channels: list[str]) -> list[str]:
	"""The thread channels started in these channels (a thread channel is named after the
	message that started it)."""
	if not channels:
		return []
	return frappe.get_all(
		"Raven Message", filters={"channel_id": ("in", channels), "is_thread": 1}, pluck="name"
	)


def delete_messages_in(channels: list[str], before=None) -> int:
	"""Delete the messages of these channels and their threads, all of them or only those
	created before `before`. Thread replies go first, so a reply is never left in a
	thread whose start is gone."""
	if not channels:
		return 0
	filters = {"creation": ("<", before)} if before else {}
	deleted = 0
	threads = _thread_channels(channels)
	if threads:
		deleted += _delete_all(
			frappe.get_all("Raven Message", filters={"channel_id": ("in", threads), **filters}, pluck="name")
		)
	deleted += _delete_all(
		frappe.get_all("Raven Message", filters={"channel_id": ("in", channels), **filters}, pluck="name")
	)
	return deleted


def workspace_channels(workspace: str) -> list[str]:
	"""The channels of a workspace whose history may be deleted: not threads (they go
	with their channel), not direct messages, not marked Keep chat history."""
	return frappe.get_all(
		"Raven Channel",
		filters={
			"workspace": workspace,
			"is_thread": 0,
			"is_direct_message": 0,
			"is_self_message": 0,
			KEEP_HISTORY_FIELD: 0,
		},
		pluck="name",
	)


def direct_message_channels() -> list[str]:
	return frappe.get_all(
		"Raven Channel",
		filters={"is_direct_message": 1, "is_thread": 0, KEEP_HISTORY_FIELD: 0},
		pluck="name",
	)


# ---- the daily job ---------------------------------------------------------------------


def delete_old_messages():
	"""Daily: delete messages older than each workspace's setting, and direct messages
	older than the Raven Settings one."""
	if not raven_installed() or not frappe.get_meta("Raven Workspace").has_field(WORKSPACE_DAYS_FIELD):
		return
	now = now_datetime()
	for workspace in frappe.get_all(
		"Raven Workspace", filters={WORKSPACE_DAYS_FIELD: (">", 0)}, fields=["name", WORKSPACE_DAYS_FIELD]
	):
		before = add_days(now, -cint(workspace.get(WORKSPACE_DAYS_FIELD)))
		delete_messages_in(workspace_channels(workspace.name), before=before)

	days = cint(frappe.db.get_single_value("Raven Settings", DIRECT_MESSAGE_DAYS_FIELD))
	if days > 0:
		delete_messages_in(direct_message_channels(), before=add_days(now, -days))


# ---- clearing by hand ------------------------------------------------------------------


def _check_can_clear():
	if not set(CLEAR_ROLES) & set(frappe.get_roles()):
		frappe.throw(_("Only a Raven Admin can clear chat history."), frappe.PermissionError)


@frappe.whitelist(methods=["POST"])
def clear_channel_history(channel: str):
	"""Delete every message of a channel and its threads, now. Runs in the background."""
	_check_can_clear()
	if not frappe.db.exists("Raven Channel", {"name": channel, "is_thread": 0}):
		frappe.throw(_("Channel {0} not found.").format(channel), frappe.DoesNotExistError)
	frappe.enqueue(
		"lms.lms.raven_retention.delete_messages_in",
		queue="long",
		channels=[channel],
		job_id=f"lms-clear-chat::{channel}",
		deduplicate=True,
		enqueue_after_commit=True,
	)


@frappe.whitelist(methods=["POST"])
def clear_workspace_history(workspace: str) -> list[str]:
	"""Delete every message of a workspace's channels (not those marked Keep chat
	history), now. Runs in the background. Returns the channels that will be cleared."""
	_check_can_clear()
	if not frappe.db.exists("Raven Workspace", workspace):
		frappe.throw(_("Workspace {0} not found.").format(workspace), frappe.DoesNotExistError)
	channels = workspace_channels(workspace)
	frappe.enqueue(
		"lms.lms.raven_retention.delete_messages_in",
		queue="long",
		channels=channels,
		job_id=f"lms-clear-chat::{workspace}",
		deduplicate=True,
		enqueue_after_commit=True,
	)
	return frappe.get_all("Raven Channel", filters={"name": ("in", channels)}, pluck="channel_name")
