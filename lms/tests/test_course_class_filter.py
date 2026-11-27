# Copyright (c) 2026, FOSS United and Contributors
# For license information, please see license.txt

import frappe

from lms.lms.test_helpers import BaseTestUtils
from lms.lms.utils import get_courses

TAGS = {
	"Tag One": "Class 1",
	"Tag Two": "Class 1, Maths",
	"Tag Three": "Maths, Class 1",
	"Tag Four": "Science, Class 1, Maths",
	"Tag Five": "Class 1 ,Maths",
	"Tag Ten": "Class 10, Science",
	"Tag Eleven": "Class 11 PCM",
	"Tag Empty": "",
}


class TestCourseClassFilter(BaseTestUtils):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.student = cls._create_user(
			"class-filter-student@example.com", "Class", "Student", ["LMS Student"]
		)
		cls.instructor = cls._create_user(
			"class-filter-author@example.com", "Class", "Author", ["Course Creator"]
		)
		cls.names = {}
		for title, tags in TAGS.items():
			course = cls._create_course(title, cls.instructor.email)
			frappe.db.set_value("LMS Course", course.name, "tags", tags)
			cls.names[title] = course.name

	def setUp(self):
		super().setUp()
		frappe.set_user(self.student.email)

	def tearDown(self):
		frappe.set_user("Administrator")
		super().tearDown()

	def _titles(self, filters):
		wanted = set(self.names.values())
		return {c.title for c in get_courses(filters, limit_page_length=100) if c.name in wanted}

	def test_class_1_matches_whole_tag_only(self):
		self.assertEqual(
			self._titles({"class": "Class 1"}),
			{"Tag One", "Tag Two", "Tag Three", "Tag Four", "Tag Five"},
		)

	def test_class_10_does_not_match_class_1(self):
		self.assertEqual(self._titles({"class": "Class 10"}), {"Tag Ten"})
		self.assertNotIn("Tag Ten", self._titles({"class": "Class 1"}))

	def test_unknown_class_ignored(self):
		self.assertEqual(self._titles({"class": "Class 99"}), set(TAGS))

	def test_class_intersects_with_enrolled_filter(self):
		for title in ("Tag One", "Tag Ten"):
			self._create_enrollment(self.student.email, self.names[title])
		self.assertEqual(self._titles({"class": "Class 1", "enrolled": 1}), {"Tag One"})
