"""Rules for students in Raven chat (the Raven app, when it is installed on the site).

Raven shows every Public or Open channel of a workspace to all its members, and lets
any member share files and images. For students (Website Users, see
`lms.lms.permissions.is_chat_student`) this app narrows both:

1. A student sees only the channels they are a member of. Raven shows a Private
   channel to its members alone, so a student may only belong to a workspace whose
   channels are all Private, that people join by invitation, and where only admins
   create channels:
   - a student joins only a Private workspace, never as its admin; the other two
     settings are switched on when the first student joins;
   - a workspace with students keeps those settings;
   - a channel in a workspace with students is Private.
   Direct messages and threads are left to Raven: a thread follows its channel.
2. A student shares no media: no file or image upload, no image, file or embedded
   media in a message. Custom emoji (inline images Raven marks as such) stay allowed.

3. A person given a Raven profile also gets the Raven User role, which Raven's app
   checks. raven_integration creates the profile alone; without the role a student
   would be shown "You cannot access Raven".
4. A person given the site's Admin role (created on migrate, no desk access) is chat
   staff: they get a Raven profile and join every workspace, so they can be picked for
   any channel, including the class channels.

The hooks are registered in `lms/hooks.py` under doc_events; they never fire on a site
without Raven, because its doctypes do not exist there.
"""

import frappe
from bs4 import BeautifulSoup
from frappe import _
from pypika.terms import ExistsCriterion

from lms.lms.permissions import CHAT_ADMIN_ROLE, CHAT_STAFF_ROLES, is_chat_student

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
	"""Whether any member of `workspace` is a student (is_chat_student, in one query),
	leaving out the member row named."""
	member = frappe.qb.DocType("Raven Workspace Member")
	user = frappe.qb.DocType("User")
	has_role = frappe.qb.DocType("Has Role")
	staff = (
		frappe.qb.from_(has_role)
		.select(has_role.name)
		.where((has_role.parent == member.user) & has_role.role.isin(CHAT_STAFF_ROLES))
	)
	query = (
		frappe.qb.from_(member)
		.join(user)
		.on(user.name == member.user)
		.select(member.name)
		.where(
			(member.workspace == workspace)
			& (user.user_type == "Website User")
			& ExistsCriterion(staff).negate()
		)
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
	"""Raven Workspace Member: a student joins only a Private workspace, never as its admin.

	A Private workspace without the other two settings (as raven_integration creates one)
	is made student-ready here, when its first student arrives, rather than refused: the
	admin who chose Private meant it for them. A Public workspace is refused."""
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
	if not workspace or workspace.type != "Private":
		frappe.throw(_("Students can only be added to a private chat workspace."), frappe.PermissionError)
	if not is_student_ready(workspace):
		frappe.db.set_value(
			"Raven Workspace",
			doc.workspace,
			{"can_only_join_via_invite": 1, "only_admins_can_create_channels": 1},
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


def give_chat_role(doc, method=None):
	"""Raven User after_insert: the person also gets the Raven User role, which Raven's app
	and permissions check. raven_integration provisions the profile without it. The role
	has no desk access here (keep_raven_user_role_off_desk), so a student stays a Website
	User."""
	if doc.get("type") not in (None, "", "User") or not doc.user or doc.user == "Administrator":
		return
	if frappe.db.exists("Has Role", {"parent": doc.user, "parenttype": "User", "role": "Raven User"}):
		return
	user = frappe.get_doc("User", doc.user)
	user.flags.ignore_permissions = True
	user.add_roles("Raven User")


def ensure_chat_admin_role():
	"""after_migrate: the Admin role exists, without desk access, so its holders stay
	Website Users and use the LMS and chat rather than the desk."""
	if not frappe.db.exists("Role", CHAT_ADMIN_ROLE):
		frappe.get_doc(
			{"doctype": "Role", "role_name": CHAT_ADMIN_ROLE, "desk_access": 0, "is_custom": 1}
		).insert(ignore_permissions=True)


def give_chat_admin_the_raven_role(doc, method=None):
	"""User validate: the Admin role brings the Raven User role in the same save, so the
	profile made in provision_chat_admin does not save this user again (give_chat_role)."""
	if "raven" not in frappe.get_installed_apps() or doc.name in ("Administrator", "Guest"):
		return
	roles = {row.role for row in doc.get("roles", [])}
	if CHAT_ADMIN_ROLE in roles and "Raven User" not in roles:
		doc.append("roles", {"role": "Raven User"})


def provision_chat_admin(doc, method=None):
	"""User on_update: someone holding the Admin role gets a Raven profile (and with it
	the Raven User role, see give_chat_role) and joins every Raven workspace. Raven offers
	only profiles in its pickers, and a channel's picker only the workspace's members.
	Taking the role away later leaves chat as it is."""
	if "raven" not in frappe.get_installed_apps() or doc.name in ("Administrator", "Guest"):
		return
	if CHAT_ADMIN_ROLE not in {row.role for row in doc.get("roles", [])}:
		return
	if not frappe.db.exists("Raven User", {"user": doc.name}):
		frappe.get_doc({"doctype": "Raven User", "user": doc.name, "type": "User"}).insert(
			ignore_permissions=True
		)
	for workspace in frappe.get_all("Raven Workspace", pluck="name"):
		if not frappe.db.exists("Raven Workspace Member", {"workspace": workspace, "user": doc.name}):
			frappe.get_doc(
				{"doctype": "Raven Workspace Member", "workspace": workspace, "user": doc.name}
			).insert(ignore_permissions=True)
