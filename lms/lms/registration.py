# Copyright (c) 2026, FOSS United and Contributors
# For license information, please see license.txt

"""Online sign-up registration. The option lists live here once; the Student
Registration DocType's Select options must equal them (see its test)."""

import re

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit
from frappe.utils import cint, now_datetime

from lms.lms.permissions import CHAT_STAFF_ROLES, REGISTRATION_TEAM_ROLES, can_manage_registrations

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
@rate_limit(limit=5, seconds=60, user_based=True)
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
	try:
		# nosemgrep: lms-unjustified-ignore-permissions - students have no DocPerm here; own row, fields validated
		registration.insert(ignore_permissions=True)
	except frappe.DuplicateEntryError:
		# Two tabs or a double click can both pass the exists() check above.
		frappe.throw(_("You are already registered."), frappe.ValidationError)

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


_LIST_FILTER_KEYS = ("follow_up_status", "wants_classroom", "student_class", "city", "assigned_to")
_ROW_FIELDS = (
	"name",
	"full_name",
	"contact_number",
	"student_class",
	"city",
	"wants_online",
	"wants_classroom",
	"follow_up_status",
	"assigned_to",
	"follow_up_notes",
	"registered_on",
)


def _require_team():
	if not can_manage_registrations():
		frappe.throw(_("Not permitted"), frappe.PermissionError)


def _team_users() -> list[dict]:
	"""Enabled users holding a team role, as {value: email, label: full name}."""
	emails = frappe.get_all(
		"Has Role",
		filters={"role": ("in", REGISTRATION_TEAM_ROLES), "parenttype": "User"},
		pluck="parent",
		distinct=True,
	)
	users = frappe.get_all(
		"User",
		filters={"name": ("in", emails), "enabled": 1},
		fields=["name", "full_name"],
		order_by="full_name asc",
	)
	return [
		{"value": user.name, "label": user.full_name or user.name}
		for user in users
		if user.name != "Administrator"
	]


@frappe.whitelist()
def get_registrations(filters: dict | None = None, start: int = 0, page_length: int = 20) -> dict:
	_require_team()
	filters = frappe.parse_json(filters) if isinstance(filters, str) else filters
	conditions = {
		key: value
		for key, value in (filters or {}).items()
		if key in _LIST_FILTER_KEYS and value not in (None, "")
	}
	if "wants_classroom" in conditions:
		conditions["wants_classroom"] = cint(conditions["wants_classroom"])
	rows = frappe.get_all(
		"Student Registration",
		filters=conditions,
		fields=list(_ROW_FIELDS),
		order_by="registered_on desc, name asc",
		offset=cint(start),
		limit=cint(page_length),
	)
	names = {}
	if assignees := {row.assigned_to for row in rows if row.assigned_to}:
		names = dict(
			frappe.get_all(
				"User", filters={"name": ("in", list(assignees))}, fields=["name", "full_name"], as_list=True
			)
		)
	for row in rows:
		row["assigned_to_name"] = names.get(row.assigned_to) or row.assigned_to or ""
	return {"rows": rows, "count": frappe.db.count("Student Registration", conditions)}


@frappe.whitelist(methods=["POST"])
def update_registration(
	name: str,
	follow_up_status: str | None = None,
	assigned_to: str | None = None,
	follow_up_notes: str | None = None,
) -> dict:
	"""Changes the follow-up status, assignee and notes only."""
	_require_team()
	changes = {}
	if follow_up_status is not None:
		if follow_up_status not in FOLLOW_UP_STATUSES:
			frappe.throw(_("Choose a status from the list."), frappe.ValidationError)
		changes["follow_up_status"] = follow_up_status
	if assigned_to is not None:
		if assigned_to and assigned_to not in {user["value"] for user in _team_users()}:
			frappe.throw(_("Assign the registration to a team member."), frappe.ValidationError)
		changes["assigned_to"] = assigned_to or None
	if follow_up_notes is not None:
		changes["follow_up_notes"] = follow_up_notes
	registration = frappe.get_doc("Student Registration", name)
	registration.check_permission("write")
	registration.update(changes)
	registration.save()
	return {field: registration.get(field) for field in _ROW_FIELDS}


@frappe.whitelist()
def get_registration_team() -> list[dict]:
	_require_team()
	return _team_users()
