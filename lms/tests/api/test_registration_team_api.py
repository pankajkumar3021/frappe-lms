import frappe

from lms.lms.registration import get_registration_team, get_registrations, update_registration
from lms.lms.test_helpers import BaseTestUtils


class TestRegistrationTeamApi(BaseTestUtils):
	def tearDown(self):
		frappe.set_user("Administrator")
		super().tearDown()

	def _user(self, roles):
		frappe.set_user("Administrator")
		for role in roles:
			if not frappe.db.exists("Role", role):
				frappe.get_doc({"doctype": "Role", "role_name": role, "desk_access": 0}).insert()
		email = f"team-{frappe.generate_hash(length=8)}@example.com"
		return self._create_user(email, "Team", "Member", list(roles))

	def _registration(self, **fields):
		frappe.set_user("Administrator")
		student = self._user(["LMS Student"])
		values = {
			"doctype": "Student Registration",
			"user": student.email,
			"full_name": "Asha Verma",
			"contact_number": "+919876543210",
			"student_class": "Class 10",
			"city": "Delhi",
			"wants_online": 1,
			"wants_classroom": 0,
		}
		values.update(fields)
		registered_on = values.pop("registered_on", None)
		doc = frappe.get_doc(values).insert(ignore_permissions=True)
		if registered_on:
			frappe.db.set_value("Student Registration", doc.name, "registered_on", registered_on)
		return doc

	def test_student_and_course_creator_are_refused(self):
		registration = self._registration()
		for roles in (["LMS Student"], ["Course Creator"]):
			user = self._user(roles)
			frappe.set_user(user.email)
			with self.subTest(roles=roles):
				with self.assertRaises(frappe.PermissionError):
					get_registrations()
				with self.assertRaises(frappe.PermissionError):
					update_registration(registration.name, follow_up_status="Contacted")
				with self.assertRaises(frappe.PermissionError):
					get_registration_team()

	def test_admin_role_and_moderator_can_list(self):
		self._registration()
		for role in ("Admin", "Moderator"):
			frappe.set_user(self._user([role]).email)
			with self.subTest(role=role):
				result = get_registrations()
				self.assertGreaterEqual(result["count"], 1)
				self.assertTrue(result["rows"])

	def test_filters_and_order(self):
		member = self._user(["Moderator"])
		kwargs = {"assigned_to": member.email}
		old = self._registration(wants_classroom=1, registered_on="2026-01-01 10:00:00", **kwargs)
		new = self._registration(wants_classroom=1, registered_on="2026-02-01 10:00:00", **kwargs)
		self._registration(wants_classroom=0, **kwargs)
		self._registration(wants_classroom=1, follow_up_status="Contacted", **kwargs)
		frappe.set_user(member.email)
		result = get_registrations(
			{"follow_up_status": "New", "wants_classroom": 1, "assigned_to": member.email}
		)
		self.assertEqual([row["name"] for row in result["rows"]], [new.name, old.name])
		self.assertEqual(result["count"], 2)
		self.assertEqual(result["rows"][0]["assigned_to_name"], "Team Member")
		page = get_registrations({"assigned_to": member.email}, start=1, page_length=1)
		self.assertEqual(len(page["rows"]), 1)
		self.assertEqual(page["count"], 4)

	def test_unknown_filter_keys_ignored(self):
		registration = self._registration()
		frappe.set_user(self._user(["Moderator"]).email)
		result = get_registrations({"user": "x", "contact_number": "nope"})
		self.assertIn(registration.name, [row["name"] for row in result["rows"]])

	def test_update_changes_only_three_fields(self):
		registration = self._registration()
		member = self._user(["Admin"])
		frappe.set_user(member.email)
		update_registration(
			registration.name,
			follow_up_status="Contacted",
			assigned_to=member.email,
			follow_up_notes="Called, will join Monday",
		)
		doc = frappe.get_doc("Student Registration", registration.name)
		self.assertEqual(doc.follow_up_status, "Contacted")
		self.assertEqual(doc.assigned_to, member.email)
		self.assertEqual(doc.follow_up_notes, "Called, will join Monday")
		try:
			frappe.call(
				"lms.lms.registration.update_registration",
				name=registration.name,
				follow_up_status="Joined",
				contact_number="+911111111111",
			)
		except TypeError:
			pass
		stored = frappe.db.get_value("Student Registration", registration.name, "contact_number")
		self.assertEqual(stored, "+919876543210")

	def test_update_refuses_bad_status_and_non_team_assignee(self):
		registration = self._registration()
		outsider = self._user(["LMS Student"])
		frappe.set_user(self._user(["Moderator"]).email)
		with self.assertRaises(frappe.ValidationError):
			update_registration(registration.name, follow_up_status="Bogus")
		with self.assertRaises(frappe.ValidationError):
			update_registration(registration.name, assigned_to=outsider.email)

	def test_team_lists_enabled_team_users_only(self):
		member = self._user(["Moderator"])
		student = self._user(["LMS Student"])
		frappe.set_user(member.email)
		values = [row["value"] for row in get_registration_team()]
		self.assertIn(member.email, values)
		self.assertNotIn(student.email, values)
		self.assertNotIn("Administrator", values)
