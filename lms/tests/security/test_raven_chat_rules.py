# Copyright (c) 2026, FOSS United and Contributors
# See license.txt
"""Students in Raven chat see only channels they are members of and share no media.

See lms.lms.raven_chat. Skipped where Raven is not installed (CI).
"""

import unittest

import frappe

from lms.lms import raven_chat
from lms.lms.test_helpers import BaseTestUtils


def raven_installed() -> bool:
	return "raven" in frappe.get_installed_apps()


@unittest.skipUnless(raven_installed(), "Raven is not installed on this site")
class TestRavenChatStudentRules(BaseTestUtils):
	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")
		self.hash = frappe.generate_hash(length=6)
		self.student = self._create_user(
			f"rc-student-{self.hash}@example.com", "Chat", "Student", ["LMS Student"]
		).name
		self.staff = self._create_user(
			f"rc-staff-{self.hash}@example.com",
			"Chat",
			"Staff",
			["Moderator", "Raven Admin"],
			user_type="System User",
		).name
		self.assertEqual(frappe.db.get_value("User", self.staff, "user_type"), "System User")
		self.assertEqual(frappe.db.get_value("User", self.student, "user_type"), "Website User")
		# Raven's member rows link to the Raven User profile, which the role normally creates.
		for user in (self.student, self.staff):
			if not frappe.db.exists("Raven User", {"user": user}):
				frappe.get_doc({"doctype": "Raven User", "user": user, "type": "User"}).insert(
					ignore_permissions=True
				)
		self.addCleanup(frappe.set_user, "Administrator")

	# ---- helpers ---------------------------------------------------------------------

	def _workspace(self, student_ready=True):
		ws = frappe.get_doc(
			{
				"doctype": "Raven Workspace",
				"workspace_name": f"rc-ws-{self.hash}-{frappe.generate_hash(length=4)}",
				"type": "Private" if student_ready else "Public",
				"can_only_join_via_invite": int(student_ready),
				"only_admins_can_create_channels": int(student_ready),
			}
		).insert(ignore_permissions=True)
		self.addCleanup(self._delete, "Raven Workspace", ws.name)
		return ws

	def _channel(self, workspace, channel_type="Private"):
		return frappe.get_doc(
			{
				"doctype": "Raven Channel",
				"channel_name": f"rc-{frappe.generate_hash(length=6)}",
				"type": channel_type,
				"workspace": workspace,
			}
		).insert(ignore_permissions=True)

	def _member(self, workspace, user, is_admin=0):
		return frappe.get_doc(
			{"doctype": "Raven Workspace Member", "workspace": workspace, "user": user, "is_admin": is_admin}
		).insert(ignore_permissions=True)

	def _delete(self, doctype, name):
		frappe.set_user("Administrator")
		if frappe.db.exists(doctype, name):
			frappe.delete_doc(doctype, name, ignore_permissions=True, force=True, delete_permanently=True)

	def _message(self, channel, **values):
		return frappe.get_doc({"doctype": "Raven Message", "channel_id": channel, **values})

	# ---- 1. students see only channels they are members of ---------------------------

	def test_student_cannot_join_a_public_workspace(self):
		ws = self._workspace(student_ready=False)
		with self.assertRaises(frappe.PermissionError):
			self._member(ws.name, self.student)

	def test_student_joins_a_student_ready_workspace(self):
		ws = self._workspace()
		self._channel(ws.name, "Private")
		self._member(ws.name, self.student)
		self.assertTrue(raven_chat.workspace_has_students(ws.name))

	def test_staff_can_join_a_public_workspace(self):
		ws = self._workspace(student_ready=False)
		self._member(ws.name, self.staff)

	def test_student_cannot_join_a_workspace_with_an_open_or_public_channel(self):
		for channel_type in ("Open", "Public"):
			ws = self._workspace()
			self._channel(ws.name, channel_type)
			with self.assertRaises(frappe.PermissionError):
				self._member(ws.name, self.student)

	def test_student_cannot_be_a_workspace_admin(self):
		ws = self._workspace()
		with self.assertRaises(frappe.PermissionError):
			self._member(ws.name, self.student, is_admin=1)

	def test_no_open_or_public_channel_in_a_workspace_with_students(self):
		ws = self._workspace()
		self._member(ws.name, self.student)
		for channel_type in ("Open", "Public"):
			with self.assertRaises(frappe.PermissionError):
				self._channel(ws.name, channel_type)
		self._channel(ws.name, "Private")

	def test_private_channel_cannot_be_made_public_once_students_are_in(self):
		ws = self._workspace()
		channel = self._channel(ws.name, "Private")
		self._member(ws.name, self.student)
		channel.type = "Open"
		with self.assertRaises(frappe.PermissionError):
			channel.save(ignore_permissions=True)

	def test_open_channel_allowed_in_a_staff_workspace(self):
		ws = self._workspace(student_ready=False)
		self._member(ws.name, self.staff)
		self._channel(ws.name, "Open")

	def test_workspace_with_students_stays_student_ready(self):
		ws = self._workspace()
		self._member(ws.name, self.student)
		for field, value in (
			("type", "Public"),
			("can_only_join_via_invite", 0),
			("only_admins_can_create_channels", 0),
		):
			ws.reload()
			ws.set(field, value)
			with self.assertRaises(frappe.PermissionError):
				ws.save(ignore_permissions=True)

	def test_workspace_without_students_can_be_opened(self):
		ws = self._workspace()
		ws.type = "Public"
		ws.save(ignore_permissions=True)

	# ---- 2. students share no media ---------------------------------------------------

	def test_has_media(self):
		self.assertFalse(raven_chat.has_media(None))
		self.assertFalse(raven_chat.has_media("<p>hello</p>"))
		self.assertFalse(
			raven_chat.has_media('<p>hi <img data-type="customEmoji" src="/files/party.png" alt="party"></p>')
		)
		self.assertTrue(raven_chat.has_media('<p><img src="https://media.example.com/cat.gif"></p>'))
		self.assertTrue(raven_chat.has_media('<video src="/files/v.mp4"></video>'))
		self.assertTrue(raven_chat.has_media('<iframe src="https://example.com"></iframe>'))

	def test_student_cannot_send_image_or_file_messages(self):
		frappe.set_user(self.student)
		for values in (
			{"message_type": "Image", "file": "/private/files/a.png"},
			{"message_type": "File", "file": "/private/files/a.pdf"},
			{"message_type": "Text", "text": '<p><img src="/private/files/a.png"></p>'},
		):
			with self.assertRaises(frappe.PermissionError):
				raven_chat.validate_message(self._message("any-channel", **values))

	def test_student_can_send_text_and_custom_emoji(self):
		frappe.set_user(self.student)
		raven_chat.validate_message(self._message("any-channel", message_type="Text", text="<p>hello</p>"))
		raven_chat.validate_message(
			self._message(
				"any-channel",
				message_type="Text",
				text='<p><img data-type="customEmoji" src="/files/party.png"></p>',
			)
		)

	def test_staff_can_send_media(self):
		frappe.set_user(self.staff)
		raven_chat.validate_message(
			self._message("any-channel", message_type="Image", file="/private/files/a.png")
		)

	def test_message_rule_is_wired_to_raven_message(self):
		"""Through a real insert, so the doc_events entry in hooks.py is what is tested."""
		ws = self._workspace()
		channel = self._channel(ws.name, "Private")
		self._member(ws.name, self.student)
		frappe.get_doc(
			{"doctype": "Raven Channel Member", "channel_id": channel.name, "user_id": self.student}
		).insert(ignore_permissions=True)
		frappe.set_user(self.student)
		self._message(channel.name, message_type="Text", text="<p>hello</p>").insert(ignore_permissions=True)
		with self.assertRaises(frappe.PermissionError):
			self._message(channel.name, message_type="Text", text='<p><img src="/files/x.gif"></p>').insert(
				ignore_permissions=True
			)

	def test_student_cannot_upload_a_chat_file(self):
		"""Both ways a chat upload names its target: on the File row (upload with a message
		name), and only on the request (Raven's web app: doctype without a docname, which
		File.before_insert drops)."""
		frappe.set_user(self.student)

		def chat_file(**values):
			return frappe.get_doc(
				{
					"doctype": "File",
					"file_name": f"rc-{self.hash}.txt",
					"content": b"hello",
					"is_private": 1,
					**values,
				}
			)

		with self.assertRaises(frappe.PermissionError):
			chat_file(attached_to_doctype="Raven Message", attached_to_name="any-message").insert(
				ignore_permissions=True
			)

		self.addCleanup(frappe.form_dict.pop, "doctype", None)
		frappe.form_dict["doctype"] = "Raven Message"
		with self.assertRaises(frappe.PermissionError):
			chat_file(attached_to_doctype="Raven Message").insert(ignore_permissions=True)

	def test_student_can_still_upload_other_files(self):
		"""Assignments and avatars are not chat media."""
		frappe.set_user(self.student)
		other = frappe.get_doc(
			{"doctype": "File", "file_name": f"rc-{self.hash}.txt", "content": b"hello", "is_private": 1}
		).insert(ignore_permissions=True)
		self.addCleanup(self._delete, "File", other.name)

	def test_migrate_keeps_the_raven_user_role_off_the_desk(self):
		before = frappe.db.get_value("Role", "Raven User", "desk_access")
		self.addCleanup(frappe.db.set_value, "Role", "Raven User", "desk_access", before)
		frappe.db.set_value("Role", "Raven User", "desk_access", 1)
		raven_chat.keep_raven_user_role_off_desk()
		self.assertEqual(frappe.db.get_value("Role", "Raven User", "desk_access"), 0)
		self.assertIn("lms.lms.raven_chat.keep_raven_user_role_off_desk", frappe.get_hooks("after_migrate"))
