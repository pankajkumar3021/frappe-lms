# Copyright (c) 2026, FOSS United and Contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime


class StudentRegistration(Document):
	def validate(self):
		if not (self.wants_online or self.wants_classroom):
			frappe.throw(_("Choose online classes, classroom classes, or both."), frappe.ValidationError)

	def before_insert(self):
		self.registered_on = now_datetime()
