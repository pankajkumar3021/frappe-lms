from lms.lms.raven_chat import ensure_chat_admin_role


def execute():
	"""Runs before the DocType sync, so the Admin role named in Student Registration's
	permissions exists without desk access before Frappe would create it with desk access."""
	ensure_chat_admin_role()
