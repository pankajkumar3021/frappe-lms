# Copyright (c) 2026, FOSS United and Contributors
# See license.txt
"""How long Raven chat keeps messages, and clearing it by hand (lms.lms.raven_retention).

Skipped where Raven is not installed (CI).
"""

import os
import unittest
from unittest.mock import patch

import frappe
from frappe.utils import add_days, now_datetime

from lms.lms import raven_retention
from lms.lms.raven_retention import DIRECT_MESSAGE_DAYS_FIELD, KEEP_HISTORY_FIELD, WORKSPACE_DAYS_FIELD
from lms.lms.test_helpers import BaseTestUtils


def raven_installed() -> bool:
	return "raven" in frappe.get_installed_apps()


@unittest.skipUnless(raven_installed(), "Raven is not installed on this site")
class TestRavenRetention(BaseTestUtils):
	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")
		raven_retention.ensure_retention_fields()
		# The job commits after each batch; a commit would end the test's savepoint.
		commit = patch.object(frappe.db, "commit")
		commit.start()
		self.addCleanup(commit.stop)
		self.hash = frappe.generate_hash(length=6)
		self.addCleanup(frappe.set_user, "Administrator")
		self.workspace = self._workspace(days=30)

	# ---- helpers -----------------------------------------------------------------------

	def _workspace(self, days=0):
		ws = frappe.get_doc(
			{
				"doctype": "Raven Workspace",
				"workspace_name": f"rr-ws-{self.hash}-{frappe.generate_hash(length=4)}",
				"type": "Private",
				WORKSPACE_DAYS_FIELD: days,
			}
		).insert(ignore_permissions=True)
		self.addCleanup(self._delete, "Raven Workspace", ws.name)
		return ws.name

	def _channel(self, workspace=None, keep=0):
		channel = frappe.get_doc(
			{
				"doctype": "Raven Channel",
				"channel_name": f"rr-{frappe.generate_hash(length=6)}",
				"type": "Private",
				"workspace": workspace or self.workspace,
				KEEP_HISTORY_FIELD: keep,
			}
		).insert(ignore_permissions=True)
		self.addCleanup(self._delete, "Raven Channel", channel.name)
		return channel.name

	def _message(self, channel, days_old=0, text="hello"):
		message = frappe.get_doc(
			{
				"doctype": "Raven Message",
				"channel_id": channel,
				"message_type": "Text",
				"text": f"<p>{text}</p>",
			}
		).insert(ignore_permissions=True)
		if days_old:
			frappe.db.set_value(
				"Raven Message",
				message.name,
				"creation",
				add_days(now_datetime(), -days_old),
				update_modified=False,
			)
		return message.name

	def _file_message(self, channel, days_old=0):
		message = self._message(channel, days_old)
		file = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": f"rr-{self.hash}-{frappe.generate_hash(length=4)}.txt",
				"content": b"chat file",
				"is_private": 1,
				"attached_to_doctype": "Raven Message",
				"attached_to_name": message,
			}
		).insert(ignore_permissions=True)
		frappe.db.set_value(
			"Raven Message", message, {"message_type": "File", "file": file.file_url}, update_modified=False
		)
		return message, file

	def _delete(self, doctype, name):
		frappe.set_user("Administrator")
		if frappe.db.exists(doctype, name):
			frappe.delete_doc(doctype, name, ignore_permissions=True, force=True, delete_permanently=True)

	def _exists(self, name):
		return bool(frappe.db.exists("Raven Message", name))

	# ---- the daily job -----------------------------------------------------------------

	def test_old_messages_go_and_new_ones_stay(self):
		channel = self._channel()
		old = self._message(channel, days_old=31)
		new = self._message(channel, days_old=29)
		raven_retention.delete_old_messages()
		self.assertFalse(self._exists(old))
		self.assertTrue(self._exists(new))

	def test_a_deleted_message_takes_its_file_off_the_disk(self):
		channel = self._channel()
		message, file = self._file_message(channel, days_old=31)
		path = file.get_full_path()
		self.assertTrue(os.path.exists(path))
		raven_retention.delete_old_messages()
		frappe.db.after_commit.run()  # Frappe removes the file from disk once the delete commits
		self.assertFalse(self._exists(message))
		self.assertFalse(frappe.db.exists("File", file.name))
		self.assertFalse(os.path.exists(path))

	def test_reactions_go_with_their_message(self):
		channel = self._channel()
		message = self._message(channel, days_old=31)
		frappe.get_doc(
			{
				"doctype": "Raven Message Reaction",
				"message": message,
				"channel_id": channel,
				"reaction": "👍",
				"reaction_escaped": "👍",
			}
		).insert(ignore_permissions=True)
		raven_retention.delete_old_messages()
		self.assertFalse(frappe.db.exists("Raven Message Reaction", {"message": message}))

	def test_an_old_thread_goes_with_all_its_replies_and_their_files(self):
		from raven.api.threads import create_thread

		channel = self._channel()
		root = self._message(channel, days_old=31)
		create_thread(root)
		reply = self._message(root)  # a new reply in an old thread
		reply_with_file, file = self._file_message(root)
		raven_retention.delete_old_messages()
		for name in (root, reply, reply_with_file):
			self.assertFalse(self._exists(name))
		self.assertFalse(frappe.db.exists("Raven Channel", root))
		self.assertFalse(frappe.db.exists("File", file.name))

	def test_old_replies_go_from_a_new_thread(self):
		from raven.api.threads import create_thread

		channel = self._channel()
		root = self._message(channel)
		create_thread(root)
		old_reply = self._message(root, days_old=31)
		new_reply = self._message(root)
		raven_retention.delete_old_messages()
		self.assertTrue(self._exists(root))
		self.assertFalse(self._exists(old_reply))
		self.assertTrue(self._exists(new_reply))

	def test_keep_chat_history_and_workspaces_without_a_period_are_left_alone(self):
		kept = self._message(self._channel(keep=1), days_old=400)
		elsewhere = self._message(self._channel(self._workspace(days=0)), days_old=400)
		raven_retention.delete_old_messages()
		self.assertTrue(self._exists(kept))
		self.assertTrue(self._exists(elsewhere))

	def test_direct_messages_follow_the_raven_settings_period(self):
		from raven.api.raven_channel import create_direct_message_channel

		peer = self._create_user(f"rr-peer-{self.hash}@example.com", "Rr", "Peer", ["LMS Student"]).name
		for user in ("Administrator", peer):
			if not frappe.db.exists("Raven User", {"user": user}):
				frappe.get_doc({"doctype": "Raven User", "user": user, "type": "User"}).insert(
					ignore_permissions=True
				)
		dm = frappe.get_doc("Raven Channel", create_direct_message_channel(peer))
		self.assertTrue(dm.is_direct_message)
		old = self._message(dm.name, days_old=10)

		before = frappe.db.get_single_value("Raven Settings", DIRECT_MESSAGE_DAYS_FIELD)
		self.addCleanup(frappe.db.set_single_value, "Raven Settings", DIRECT_MESSAGE_DAYS_FIELD, before)
		frappe.db.set_single_value("Raven Settings", DIRECT_MESSAGE_DAYS_FIELD, 0)
		raven_retention.delete_old_messages()
		self.assertTrue(self._exists(old))

		frappe.db.set_single_value("Raven Settings", DIRECT_MESSAGE_DAYS_FIELD, 7)
		raven_retention.delete_old_messages()
		self.assertFalse(self._exists(old))

	def test_the_job_and_the_fields_are_wired(self):
		self.assertIn(
			"lms.lms.raven_retention.delete_old_messages", frappe.get_hooks("scheduler_events")["daily_long"]
		)
		self.assertIn("lms.lms.raven_retention.ensure_retention_fields", frappe.get_hooks("after_migrate"))
		self.assertTrue(frappe.get_meta("Raven Workspace").has_field(WORKSPACE_DAYS_FIELD))
		self.assertTrue(frappe.get_meta("Raven Channel").has_field(KEEP_HISTORY_FIELD))
		self.assertTrue(frappe.get_meta("Raven Settings").has_field(DIRECT_MESSAGE_DAYS_FIELD))

	# ---- clearing by hand --------------------------------------------------------------

	def test_clearing_a_workspace_deletes_every_message_but_kept_channels(self):
		workspace = self._workspace(days=0)
		class_channel = self._channel(workspace)
		staff_channel = self._channel(workspace, keep=1)
		new = self._message(class_channel)
		kept = self._message(staff_channel)

		cleared = raven_retention.clear_workspace_history(workspace)
		self.assertEqual(len(cleared), 1)
		raven_retention.delete_messages_in(raven_retention.workspace_channels(workspace))  # the queued job

		self.assertFalse(self._exists(new))
		self.assertTrue(self._exists(kept))

	def test_clearing_a_channel_deletes_every_message(self):
		channel = self._channel(keep=1)
		message = self._message(channel)
		raven_retention.clear_channel_history(channel)
		raven_retention.delete_messages_in([channel])  # the queued job
		self.assertFalse(self._exists(message))

	def test_only_a_raven_admin_can_clear(self):
		teacher = self._create_user(
			f"rr-teacher-{self.hash}@example.com", "Rr", "Teacher", ["Moderator"]
		).name
		channel = self._channel()
		frappe.set_user(teacher)
		with self.assertRaises(frappe.PermissionError):
			raven_retention.clear_channel_history(channel)
		with self.assertRaises(frappe.PermissionError):
			raven_retention.clear_workspace_history(self.workspace)
