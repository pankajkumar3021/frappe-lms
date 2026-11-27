# Copyright (c) 2026, FOSS United and Contributors
# See license.txt

import frappe

from lms.lms.permissions import can_manage_registrations, registration_query_conditions
from lms.lms.registration import CITIES, CLASSES, FOLLOW_UP_STATUSES
from lms.lms.test_helpers import BaseTestUtils


class TestStudentRegistration(BaseTestUtils):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		if not frappe.db.exists("Role", "Admin"):
			frappe.get_doc({"doctype": "Role", "role_name": "Admin"}).insert()
		cls.student = cls._create_user("reg-student@example.com", "Reg", "Student", ["LMS Student"])
		cls.creator = cls._create_user("reg-creator@example.com", "Reg", "Creator", ["Course Creator"])
		cls.moderator = cls._create_user("reg-mod@example.com", "Reg", "Mod", ["Moderator"])
		cls.team_admin = cls._create_user("reg-admin@example.com", "Reg", "Admin", ["Admin"])
		cls.sysmgr = cls._create_user("reg-sm@example.com", "Reg", "Sm", ["System Manager"])

	def _registration(self, **overrides):
		values = {
			"doctype": "Student Registration",
			"user": self.student.name,
			"full_name": "Reg Student",
			"contact_number": "+919876543210",
			"student_class": "Class 9",
			"city": "Delhi",
			"wants_online": 1,
			"wants_classroom": 0,
		}
		values.update(overrides)
		return frappe.get_doc(values)

	def tearDown(self):
		frappe.set_user("Administrator")
		super().tearDown()

	def test_requires_online_or_classroom(self):
		doc = self._registration(wants_online=0, wants_classroom=0)
		self.assertRaises(frappe.ValidationError, doc.insert)

	def test_registered_on_set_and_status_defaults_new(self):
		doc = self._registration().insert()
		self.assertTrue(doc.registered_on)
		self.assertEqual(doc.follow_up_status, "New")

	def test_doctype_options_match_constants(self):
		meta = frappe.get_meta("Student Registration")
		self.assertEqual(meta.get_field("student_class").options.split("\n"), list(CLASSES))
		self.assertEqual(meta.get_field("city").options.split("\n"), list(CITIES))
		self.assertEqual(meta.get_field("follow_up_status").options.split("\n"), list(FOLLOW_UP_STATUSES))

	def test_can_manage_registrations(self):
		for user in (self.moderator, self.team_admin, self.sysmgr):
			self.assertTrue(can_manage_registrations(user.name), user.name)
		for user in (self.student, self.creator):
			self.assertFalse(can_manage_registrations(user.name), user.name)

	def test_student_cannot_read_registrations(self):
		doc = self._registration().insert()
		frappe.set_user(self.student.name)
		# Frappe refuses a list for a role with no DocPerm outright; an empty list would also
		# be a denial. Either way no row reaches the student.
		try:
			self.assertEqual(frappe.get_list("Student Registration"), [])
		except frappe.PermissionError:
			pass
		self.assertEqual(registration_query_conditions(self.student.name), "1=0")
		with self.assertRaises(frappe.PermissionError):
			frappe.get_doc("Student Registration", doc.name).check_permission("read")

	def test_team_can_read_registrations(self):
		doc = self._registration().insert()
		for user in (self.moderator, self.team_admin):
			frappe.set_user(user.name)
			self.assertEqual(len(frappe.get_list("Student Registration")), 1)
			frappe.get_doc("Student Registration", doc.name).check_permission("read")
