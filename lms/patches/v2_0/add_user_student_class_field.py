import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from lms.install import load_install_data


def execute():
	"""Adds the User custom fields from install_data that an older site lacks (student_class)."""
	create_custom_fields(load_install_data("custom_field.json"), update=False)
	frappe.clear_cache(doctype="User")
