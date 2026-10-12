"""Run on an isolated installed Frappe site, NOT in the root offline pytest suite."""
import unittest

import frappe

from ultimatesales_connector.access import require_manager
from ultimatesales_connector.install import check_environment


class TestInstallContract(unittest.TestCase):
    def test_framework_and_erp_schema_contract(self):
        check_environment()

    def test_native_doc_types_exist(self):
        for name in ("US Connection", "US Record Link", "US Sync Job"):
            self.assertTrue(frappe.db.exists("DocType", name))

    def test_default_safety_metadata(self):
        meta = frappe.get_meta("US Connection")
        self.assertEqual(str(meta.get_field("enabled").default), "0")
        self.assertEqual(str(meta.get_field("preview_only").default), "1")
        self.assertEqual(meta.get_field("api_token").fieldtype, "Password")

    def test_guest_is_denied_administrative_access(self):
        previous = frappe.session.user
        try:
            frappe.set_user("Guest")
            with self.assertRaises(frappe.PermissionError):
                require_manager()
        finally:
            frappe.set_user(previous)
