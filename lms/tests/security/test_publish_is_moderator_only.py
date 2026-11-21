"""Only a Moderator (or a site administrator) publishes or unpublishes a batch or a
program. Instructors edit everything else. The course rule has its own tests in
lms/lms/doctype/lms_course/test_lms_course.py."""

import frappe
from frappe.utils import add_days, nowdate

from lms.lms.test_helpers import BaseTestUtils


class TestBatchAndProgramPublishIsModeratorOnly(BaseTestUtils):
	def setUp(self):
		super().setUp()
		self.hash = frappe.generate_hash(length=6)
		self.instructor = self._create_user(
			f"pub-instructor-{self.hash}@example.com", "Ivy", "Instructor", ["Course Creator"]
		).name
		self.moderator = self._create_user(
			f"pub-moderator-{self.hash}@example.com", "Max", "Moderator", ["Moderator"]
		).name
		self._require_no_moderators(self.instructor)

	# --- batches ---------------------------------------------------------------

	def _batch(self, published=0):
		"""A batch the instructor teaches, made by the Administrator."""
		return frappe.get_doc(
			{
				"doctype": "LMS Batch",
				"title": f"Publish Batch {self.hash}",
				"start_date": nowdate(),
				"end_date": add_days(nowdate(), 10),
				"start_time": "09:00:00",
				"end_time": "11:00:00",
				"timezone": "Asia/Kolkata",
				"description": "Batch",
				"batch_details": "Batch details",
				"published": published,
				"instructors": [{"instructor": self.instructor}],
			}
		).insert()

	def _batch_as(self, user, name):
		frappe.set_user(user)
		return frappe.get_doc("LMS Batch", name)

	def test_batch_instructor_cannot_publish(self):
		batch = self._batch_as(self.instructor, self._batch().name)
		batch.published = 1
		with self.assertRaises(frappe.PermissionError):
			batch.save()

	def test_batch_instructor_cannot_unpublish(self):
		batch = self._batch_as(self.instructor, self._batch(published=1).name)
		batch.published = 0
		with self.assertRaises(frappe.PermissionError):
			batch.save()

	def test_batch_instructor_can_edit_other_fields(self):
		name = self._batch().name
		batch = self._batch_as(self.instructor, name)
		batch.description = "Edited by the instructor"
		batch.save()

		frappe.set_user("Administrator")
		saved = frappe.db.get_value("LMS Batch", name, ["description", "published"], as_dict=True)
		self.assertEqual(saved.description, "Edited by the instructor")
		self.assertEqual(saved.published, 0)

	def test_moderator_can_publish_a_batch(self):
		name = self._batch().name
		batch = self._batch_as(self.moderator, name)
		batch.published = 1
		batch.save()
		self.assertEqual(frappe.db.get_value("LMS Batch", name, "published"), 1)

	# --- programs --------------------------------------------------------------

	def _program_as_instructor(self, published=0):
		frappe.set_user(self.instructor)
		return frappe.get_doc(
			{"doctype": "LMS Program", "title": f"Publish Program {self.hash}", "published": published}
		)

	def test_program_instructor_cannot_create_a_published_program(self):
		with self.assertRaises(frappe.PermissionError):
			self._program_as_instructor(published=1).insert()

	def test_program_instructor_cannot_publish(self):
		program = self._program_as_instructor().insert()
		program.published = 1
		with self.assertRaises(frappe.PermissionError):
			program.save()

	def test_program_instructor_can_edit_other_fields(self):
		program = self._program_as_instructor().insert()
		program.enforce_course_order = 1
		program.save()
		self.assertEqual(frappe.db.get_value("LMS Program", program.name, "published"), 0)

	def test_moderator_can_publish_a_program(self):
		name = self._program_as_instructor().insert().name
		frappe.set_user(self.moderator)
		program = frappe.get_doc("LMS Program", name)
		program.published = 1
		program.save()
		self.assertEqual(frappe.db.get_value("LMS Program", name, "published"), 1)
