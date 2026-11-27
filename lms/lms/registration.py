# Copyright (c) 2026, FOSS United and Contributors
# For license information, please see license.txt

"""Online sign-up registration. The option lists live here once; the Student
Registration DocType's Select options must equal them (see its test)."""

import re

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit
from frappe.utils import cint, now_datetime

from lms.lms.permissions import CHAT_STAFF_ROLES

CLASSES = (
	*(f"Class {number}" for number in range(1, 11)),
	"Class 11 PCM",
	"Class 11 PCB",
	"Class 12 PCM",
	"Class 12 PCB",
)
CITIES = ("Delhi", "Noida", "Muzaffarpur", "Motipur")
FOLLOW_UP_STATUSES = ("New", "Contacted", "Joined", "Not interested")

_MOBILE_PATTERN = re.compile(r"[6-9]\d{9}")


def normalize_mobile(value: str) -> str:
	"""An Indian mobile typed any usual way, as +91XXXXXXXXXX."""
	digits = re.sub(r"[\s\-()]", "", value or "")
	if digits.startswith("+91"):
		digits = digits[3:]
	elif len(digits) == 12 and digits.startswith("91"):
		digits = digits[2:]
	elif len(digits) == 11 and digits.startswith("0"):
		digits = digits[1:]
	if not _MOBILE_PATTERN.fullmatch(digits):
		frappe.throw(_("Enter a valid 10-digit Indian mobile number."), frappe.ValidationError)
	return f"+91{digits}"


def _needs_registration(user: str) -> bool:
	if user == "Guest" or frappe.db.get_value("User", user, "user_type") != "Website User":
		return False
	if set(frappe.get_roles(user)) & set(CHAT_STAFF_ROLES):
		return False
	if frappe.db.exists("Student Registration", user):
		return False
	return not frappe.db.exists("LMS Batch Enrollment", {"member": user})


@frappe.whitelist()
def get_registration_state() -> dict:
	user = frappe.session.user
	if user == "Guest":
		frappe.throw(_("Please log in to continue."), frappe.PermissionError)
	full_name, mobile_no = frappe.db.get_value("User", user, ["full_name", "mobile_no"])
	return {
		"needs_registration": _needs_registration(user),
		"classes": list(CLASSES),
		"cities": list(CITIES),
		"prefill": {"full_name": full_name or "", "contact_number": mobile_no or ""},
	}


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=5, seconds=60)
def submit_registration(
	full_name: str,
	contact_number: str,
	student_class: str,
	city: str,
	wants_online: bool,
	wants_classroom: bool,
) -> dict:
	"""Registers the signed-in user only. Grants no role, batch or chat access."""
	user = frappe.session.user
	if user == "Guest":
		frappe.throw(_("Please log in to continue."), frappe.PermissionError)
	if frappe.db.exists("Student Registration", user):
		frappe.throw(_("You are already registered."), frappe.ValidationError)

	full_name = (full_name or "").strip()
	if not full_name:
		frappe.throw(_("Enter your full name."), frappe.ValidationError)
	mobile = normalize_mobile(contact_number)
	if student_class not in CLASSES:
		frappe.throw(_("Choose a class from the list."), frappe.ValidationError)
	if city not in CITIES:
		frappe.throw(_("Choose a city from the list."), frappe.ValidationError)
	wants_online = cint(wants_online)
	wants_classroom = cint(wants_classroom)
	if not (wants_online or wants_classroom):
		frappe.throw(_("Choose Online, Classroom or both."), frappe.ValidationError)

	registration = frappe.get_doc(
		{
			"doctype": "Student Registration",
			"user": user,
			"full_name": full_name,
			"contact_number": mobile,
			"student_class": student_class,
			"city": city,
			"wants_online": wants_online,
			"wants_classroom": wants_classroom,
			"registered_on": now_datetime(),
		}
	)
	# nosemgrep: lms-unjustified-ignore-permissions - students have no DocPerm on Student Registration; the row is for session.user only and every field is validated above
	registration.insert(ignore_permissions=True)

	first_name, _sep, last_name = full_name.partition(" ")
	frappe.db.set_value(
		"User",
		user,
		{
			"first_name": first_name,
			"full_name": full_name,
			"last_name": last_name.strip(),
			"mobile_no": mobile,
			"city": city,
			"student_class": student_class,
		},
	)
	return {"student_class": student_class}
