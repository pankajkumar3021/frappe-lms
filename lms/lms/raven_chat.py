"""Rules for students in Raven chat (the Raven app, when it is installed on the site).

Raven shows every Public or Open channel of a workspace to all its members, and lets
any member share files and images. For students (Website Users, see
`lms.lms.permissions.is_chat_student`) this app narrows both:

1. A student sees only the channels they are a member of. Raven shows a Private
   channel to its members alone, so a student may only belong to a workspace whose
   channels are all Private, that people join by invitation, and where only admins
   create channels:
   - a student joins only such a workspace, and never as its admin;
   - a workspace with students keeps those settings;
   - a channel in a workspace with students is Private.
   Direct messages and threads are left to Raven: a thread follows its channel.
2. A student shares no media: no file or image upload, no image, file or embedded
   media in a message. Custom emoji (inline images Raven marks as such) stay allowed.

The hooks are registered in `lms/hooks.py` under doc_events; they never fire on a site
without Raven, because its doctypes do not exist there.
"""

import frappe
from bs4 import BeautifulSoup
from frappe import _

from lms.lms.permissions import is_chat_student

# Tags that carry media into a message body. A custom emoji is an <img> Raven marks
# with data-type="customEmoji"; every other <img> (a pasted image, a GIF) is media.
MEDIA_TAGS = ("img", "video", "audio", "iframe", "object", "embed", "source", "picture")
MEDIA_MESSAGE_TYPES = ("Image", "File")


def is_student_ready(workspace) -> bool:
	"""Whether a workspace (a doc or a dict of its values) may have students in it."""
	return (
		workspace.get("type") == "Private"
		and bool(workspace.get("can_only_join_via_invite"))
		and bool(workspace.get("only_admins_can_create_channels"))
	)


def workspace_has_students(workspace: str, exclude_member: str | None = None) -> bool:
	"""Whether any member of `workspace` is a student, leaving out the member row named."""
	member = frappe.qb.DocType("Raven Workspace Member")
	user = frappe.qb.DocType("User")
	query = (
		frappe.qb.from_(member)
		.join(user)
		.on(user.name == member.user)
		.select(member.name)
		.where((member.workspace == workspace) & (user.user_type == "Website User"))
		.limit(1)
	)
	if exclude_member:
		query = query.where(member.name != exclude_member)
	return bool(query.run())


def _non_private_channels(workspace: str) -> list[str]:
	return frappe.get_all(
		"Raven Channel",
		filters={
			"workspace": workspace,
			"type": ["!=", "Private"],
			"is_direct_message": 0,
			"is_self_message": 0,
			"is_thread": 0,
		},
		pluck="channel_name",
	)


def validate_workspace_member(doc, method=None):
	"""Raven Workspace Member: a student joins only a student-ready workspace, not as admin."""
	if not is_chat_student(doc.user):
		return

	if doc.is_admin:
		frappe.throw(_("A student cannot be an admin of a chat workspace."), frappe.PermissionError)

	workspace = frappe.db.get_value(
		"Raven Workspace",
		doc.workspace,
		["type", "can_only_join_via_invite", "only_admins_can_create_channels"],
		as_dict=True,
	)
	if not workspace or not is_student_ready(workspace):
		frappe.throw(
			_(
				"Students can only be added to a private chat workspace that people join by"
				" invitation and where only admins create channels."
			),
			frappe.PermissionError,
		)

	open_channels = _non_private_channels(doc.workspace)
	if open_channels:
		frappe.throw(
			_("Make these channels private before adding students to this workspace: {0}").format(
				", ".join(open_channels)
			),
			frappe.PermissionError,
		)


def validate_workspace(doc, method=None):
	"""Raven Workspace: a workspace with students keeps the settings that keep them out of
	channels they are not in."""
	if doc.is_new() or is_student_ready(doc):
		return
	if workspace_has_students(doc.name):
		frappe.throw(
			_(
				"This workspace has students, so it must stay private, joined by invitation,"
				" with only admins creating channels."
			),
			frappe.PermissionError,
		)


def validate_channel(doc, method=None):
	"""Raven Channel: a channel in a workspace with students is Private."""
	if doc.is_direct_message or doc.is_self_message or doc.is_thread or not doc.workspace:
		return
	if doc.type != "Private" and workspace_has_students(doc.workspace):
		frappe.throw(_("Channels in a workspace with students must be private."), frappe.PermissionError)


def has_media(html: str | None) -> bool:
	"""Whether a message body embeds media: any media tag other than a custom emoji."""
	if not html or "<" not in html:
		return False
	for tag in BeautifulSoup(html, "html.parser").find_all(MEDIA_TAGS):
		if tag.name == "img" and tag.get("data-type") == "customEmoji":
			continue
		return True
	return False


def _refuse_media():
	frappe.throw(_("Students cannot share files, images or media in chat."), frappe.PermissionError)


def validate_message(doc, method=None):
	"""Raven Message: a student's message carries no file, image or embedded media.

	Checked on the message itself, so every way of sending one (upload with a caption,
	send with attachments, forward) is covered."""
	if doc.is_bot_message or doc.message_type == "System" or not is_chat_student():
		return
	if doc.message_type in MEDIA_MESSAGE_TYPES or doc.file or has_media(doc.text):
		_refuse_media()


def validate_file(doc, method=None):
	"""File: a student cannot upload a file for a chat message. Refused at upload, so a
	refused send leaves no orphan file behind.

	Raven's web app uploads with `doctype=Raven Message` and no docname (the message does
	not exist yet), and File.before_insert drops an attached_to_doctype that has no name.
	So the upload request is checked too, not only the File row."""
	for_chat = doc.attached_to_doctype == "Raven Message" or (
		frappe.form_dict.get("doctype") == "Raven Message"
	)
	if for_chat and is_chat_student():
		_refuse_media()


def keep_raven_user_role_off_desk():
	"""after_migrate: the Raven User role grants no desk access on this site.

	Frappe makes anyone holding a role with desk access a System User, so with Raven's
	default a student given chat would get the desk too, and these rules (which tell
	students apart as Website Users) would no longer see them as students. Staff keep
	the desk through their other roles. Runs on every migrate so a Raven upgrade, or
	Raven installed later, cannot turn it back on."""
	if frappe.db.get_value("Role", "Raven User", "desk_access"):
		frappe.db.set_value("Role", "Raven User", "desk_access", 0)
