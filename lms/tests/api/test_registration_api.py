from unittest.mock import patch

import frappe

from lms.lms.api import get_user_info
from lms.lms.registration import (
	get_registration_state,
	normalize_mobile,
	submit_registration,
)
from lms.lms.test_helpers import BaseTestUtils


class TestRegistrationApi(BaseTestUtils):
	def tearDown(self):
		frappe.set_user("Administrator")
		super().tearDown()

	def _student(self, roles=("LMS Student",), user_type="Website User"):
		frappe.set_user("Administrator")
		email = f"reg-{frappe.generate_hash(length=8)}@example.com"
		return self._create_user(email, "Reg", "Student", list(roles), user_type=user_type)

	def _state_for(self, user):
		frappe.set_user(user.email)
		return get_registration_state()

	def _submit(self, **overrides):
		args = {
			"full_name": "Asha Verma",
			"contact_number": "98765 43210",
			"student_class": "Class 10",
			"city": "Delhi",
			"wants_online": True,
			"wants_classroom": False,
		}
		args.update(overrides)
		return submit_registration(**args)

	def test_fresh_student_needs_registration(self):
		state = self._state_for(self._student())
		self.assertTrue(state["needs_registration"])
		self.assertEqual(state["classes"][0], "Class 1")
		self.assertIn("Motipur", state["cities"])
		self.assertEqual(state["prefill"]["full_name"], "Reg Student")

	def test_staff_do_not_need_registration(self):
		if not frappe.db.exists("Role", "Admin"):
			frappe.get_doc({"doctype": "Role", "role_name": "Admin", "desk_access": 0}).insert()
		for role in ("Course Creator", "Moderator", "Admin"):
			with self.subTest(role=role):
				user = self._student(roles=("LMS Student", role))
				self.assertFalse(self._state_for(user)["needs_registration"])
		with self.subTest(role="System User"):
			frappe.set_user("Administrator")
			if not frappe.db.exists("Role", "Reg Desk Role"):
				frappe.get_doc({"doctype": "Role", "role_name": "Reg Desk Role", "desk_access": 1}).insert()
			user = self._student(roles=("Reg Desk Role",), user_type="System User")
			self.assertFalse(self._state_for(user)["needs_registration"])

	def test_batch_enrolled_student_does_not_need_registration(self):
		hash = frappe.generate_hash(length=6)
		instructor = self._create_user(
			f"reg-instr-{hash}@example.com", "Reg", "Instr", ["Course Creator", "Moderator"]
		)
		self._create_evaluator(instructor.email)
		course = self._create_course(title=f"Reg Course {hash}", instructor=instructor.email)
		batch = self._create_batch(
			course=course.name,
			instructor=instructor.email,
			title=f"Reg Batch {hash}",
			evaluator=instructor.email,
		)
		student = self._student()
		self._create_batch_enrollment(student.email, batch.name)
		self.assertFalse(self._state_for(student)["needs_registration"])

	def test_submit_creates_record_and_copies_to_user(self):
		student = self._student()
		frappe.set_user(student.email)
		self.assertEqual(self._submit(), {"student_class": "Class 10"})
		self.assertFalse(get_registration_state()["needs_registration"])
		frappe.set_user("Administrator")
		user = frappe.db.get_value(
			"User",
			student.email,
			["mobile_no", "city", "student_class", "full_name", "first_name", "last_name"],
			as_dict=True,
		)
		self.assertEqual(user.mobile_no, "+919876543210")
		self.assertEqual(user.city, "Delhi")
		self.assertEqual(user.student_class, "Class 10")
		self.assertEqual(user.full_name, "Asha Verma")
		registration = frappe.get_doc("Student Registration", student.email)
		self.assertEqual(registration.contact_number, "+919876543210")
		self.assertEqual(registration.follow_up_status, "New")
		self.assertTrue(registration.wants_online)
		self.assertFalse(registration.wants_classroom)

	def test_normalize_mobile(self):
		for value in ("98765 43210", "+91 9876543210", "09876543210", "919876543210", "9876543210"):
			with self.subTest(value=value):
				self.assertEqual(normalize_mobile(value), "+919876543210")
		for value in ("12345", "5876543210", "", "98765432101234"):
			with self.subTest(value=value):
				with self.assertRaises(frappe.ValidationError):
					normalize_mobile(value)

	def test_rejects_unknown_class_and_city(self):
		frappe.set_user(self._student().email)
		with self.assertRaises(frappe.ValidationError):
			self._submit(student_class="Class 13")
		with self.assertRaises(frappe.ValidationError):
			self._submit(city="Mumbai")

	def test_rejects_neither_mode(self):
		frappe.set_user(self._student().email)
		with self.assertRaises(frappe.ValidationError):
			self._submit(wants_online=False, wants_classroom=False)

	def test_second_submit_says_already_registered(self):
		frappe.set_user(self._student().email)
		self._submit()
		with self.assertRaises(frappe.ValidationError) as caught:
			self._submit()
		self.assertIn("already registered", str(caught.exception))
		self.assertNotIsInstance(caught.exception, frappe.UniqueValidationError)

	def test_concurrent_duplicate_says_already_registered(self):
		"""A second request that passed the exists() check still gets the friendly error."""
		frappe.set_user(self._student().email)
		self._submit()
		with patch("lms.lms.registration.frappe.db.exists", return_value=False):
			with self.assertRaises(frappe.ValidationError) as caught:
				self._submit()
		self.assertIn("already registered", str(caught.exception))
		self.assertNotIsInstance(caught.exception, frappe.DuplicateEntryError)

	def test_submit_grants_no_roles(self):
		student = self._student()
		before = sorted(frappe.get_roles(student.email))
		frappe.set_user(student.email)
		self._submit()
		frappe.set_user("Administrator")
		self.assertEqual(sorted(frappe.get_roles(student.email)), before)
		if frappe.db.exists("DocType", "Raven User"):
			self.assertFalse(frappe.db.exists("Raven User", {"user": student.email}))
		self.assertFalse(frappe.db.exists("LMS Batch Enrollment", {"member": student.email}))

	def test_guest_is_refused(self):
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			get_registration_state()
		with self.assertRaises(frappe.PermissionError):
			self._submit()

	def test_get_user_info_has_student_class(self):
		student = self._student()
		frappe.set_user(student.email)
		info = get_user_info()
		self.assertIn("student_class", info)
		self.assertFalse(info["can_manage_registrations"])
		self._submit()
		self.assertEqual(get_user_info()["student_class"], "Class 10")
		frappe.set_user("Administrator")
		self.assertTrue(get_user_info()["can_manage_registrations"])
