"""Real installed-site SQL/permissions, fake CRM transport. Never live API proof."""
from unittest.mock import patch

import frappe

from ultimatesales_connector.domain import RuleError
from ultimatesales_connector.tests.acceptance_support import DisposableSiteTestCase, SyntheticQuotationHTTP


class TestPermissionsAndRecovery(DisposableSiteTestCase):
    def setUp(self):
        try:
            super().setUp()
            # Persist the whole fixture before jobs.run refreshes its read snapshot
            # or a child RQ worker opens a separate database connection.
            frappe.db.commit()
        except Exception:
            # unittest does not call tearDown after a failed setUp.
            if hasattr(self, "connections"):
                self.tearDown()
            raise

    def tearDown(self):
        try:
            self.cleanup_fixture()
            # Only the owning installed TestCase makes successful cleanup durable.
            frappe.db.commit()
        except Exception:
            frappe.db.rollback()
            raise
        finally:
            frappe.conf.ultimatesales_connector_allow_writes = self.previous_gate
            frappe.set_user(self.previous_user)

    def assert_blocked_before_transport(self, job, remote, code):
        self.assertEqual(job.status, "Blocked")
        self.assertEqual(job.error_code, code)
        self.assertFalse(remote.calls)
        self.assertFalse(self.mapping_rows())

    def test_default_preview_writes_no_business_records(self):
        name = self.request(preview=1)
        frappe.db.commit()  # The request must survive the worker's initial rollback.
        job, _ = self.run_job(name)
        frappe.db.commit()  # Simulate the native worker commit after normal app return.
        self.assertEqual(job.status, "Preview")
        self.assertFalse(self.mapping_rows())
        self.assertFalse(frappe.db.exists("Lead", {"email_id": self.reference + "-contact@example.invalid"}))

    def test_normal_permissions_import_once_and_replay(self):
        name = self.request()
        frappe.db.commit()  # The request must survive the worker's initial rollback.
        with patch.object(frappe, "set_user", side_effect=RuntimeError("App switched user")):
            job, _ = self.run_job(name)
            frappe.db.commit()  # Native worker boundary after a normal return.
        self.assertEqual(job.status, "Succeeded", job.error_code)
        rows = self.mapping_rows()
        self.assertEqual(len(rows), 2)
        deal = next(row for row in rows if row.record_kind == "Opportunity")
        self.assertEqual(frappe.db.get_value("Lead", deal.lead, "owner"), self.operator)
        self.assertEqual(frappe.db.get_value("Opportunity", deal.opportunity, "owner"), self.operator)
        self.assertEqual(frappe.db.get_value("Opportunity", deal.opportunity, "company"), self.company)
        replay_name = self.request()
        frappe.db.commit()
        replay, _ = self.run_job(replay_name)
        frappe.db.commit()
        self.assertEqual(replay.status, "Succeeded", replay.error_code)
        self.assertEqual({row.name for row in rows}, {row.name for row in self.mapping_rows()})

    def test_two_deals_for_one_contact_keep_separate_opportunity_mappings(self):
        from ultimatesales_connector.tests.acceptance_support import SyntheticClient
        from ultimatesales_connector.jobs import run
        from ultimatesales_connector.api import request_import
        remote = SyntheticClient(self.connection)
        original = remote.get_opportunity
        contact = self.reference + "-contact"

        def same_contact(name):
            result = original(name)
            result["contactId"] = contact
            return result

        names = [self.request(), request_import(self.connection.name, self.reference + "-second", preview=0)]
        frappe.db.commit()
        with patch.object(remote, "get_opportunity", side_effect=same_contact), \
             patch("ultimatesales_connector.service.get_client", return_value=remote):
            for name in names:
                run(name)
                frappe.db.commit()  # Framework-owned worker boundary simulated by the fixture.
                self.assertEqual(frappe.db.get_value("US Sync Job", name, "status"), "Succeeded")
        rows = self.mapping_rows()
        deals = [row for row in rows if row.record_kind == "Opportunity"]
        self.assertEqual(len(rows), 3)
        self.assertEqual(len(deals), 2)
        self.assertEqual(len({row.lead for row in rows}), 1)
        self.assertEqual(len({row.opportunity for row in deals}), 2)

    def test_native_requester_mismatch_blocks_before_remote_reads(self):
        name = self.request()
        frappe.db.commit()  # The request must survive the worker's initial rollback.
        frappe.set_user(self.other_operator)
        job, remote = self.run_job(name)
        frappe.db.commit()
        self.assert_blocked_before_transport(job, remote, "requesting_identity_changed")

    def test_role_revoked_after_request_blocks(self):
        name = self.request()
        frappe.db.commit()  # The request must survive the worker's initial rollback.
        frappe.set_user("Administrator")
        user = frappe.get_doc("User", self.operator)
        user.set("roles", [row for row in user.roles if row.role != "UltimateSales Operator"])
        user.save(ignore_permissions=True)
        frappe.db.commit()
        frappe.clear_cache(user=self.operator)
        frappe.set_user(self.operator)
        job, remote = self.run_job(name)
        frappe.db.commit()
        self.assert_blocked_before_transport(job, remote, "operator_role_required")

    def test_disabled_requester_after_request_blocks(self):
        name = self.request()
        frappe.db.commit()  # The request must survive the worker's initial rollback.
        frappe.set_user("Administrator")
        frappe.db.set_value("User", self.operator, "enabled", 0)
        frappe.db.commit()
        frappe.clear_cache(user=self.operator)
        frappe.set_user(self.operator)
        job, remote = self.run_job(name)
        frappe.db.commit()
        self.assert_blocked_before_transport(job, remote, "invalid_integration_user")

    def test_privileged_role_added_after_request_blocks(self):
        name = self.request()
        frappe.db.commit()  # The request must survive the worker's initial rollback.
        frappe.set_user("Administrator")
        user = frappe.get_doc("User", self.operator)
        user.append("roles", {"role": "System Manager"})
        user.save(ignore_permissions=True)
        frappe.db.commit()
        frappe.clear_cache(user=self.operator)
        frappe.set_user(self.operator)
        job, remote = self.run_job(name)
        frappe.db.commit()
        self.assert_blocked_before_transport(job, remote, "integration_user_has_excessive_permissions")

    def test_company_permission_revoked_after_request_blocks(self):
        name = self.request()
        frappe.db.commit()  # The request must survive the worker's initial rollback.
        frappe.set_user("Administrator")
        frappe.db.delete("User Permission", {"user": self.operator, "allow": "Company"})
        frappe.db.commit()
        frappe.clear_cache(user=self.operator)
        frappe.set_user(self.operator)
        job, remote = self.run_job(name)
        frappe.db.commit()
        self.assert_blocked_before_transport(job, remote, "company_permission_required")

    def test_sales_create_permission_revoked_uses_actual_erp_permission_checks(self):
        name = self.request()
        frappe.db.commit()  # The request must survive the worker's initial rollback.
        frappe.set_user("Administrator")
        user = frappe.get_doc("User", self.operator)
        user.set("roles", [row for row in user.roles if row.role != "Sales User"])
        user.save(ignore_permissions=True)
        frappe.db.commit()
        frappe.clear_cache(user=self.operator)
        frappe.set_user(self.operator)
        self.assertFalse(frappe.has_permission("Lead", "create"), "Acceptance site grants unexpected create rights.")
        job, _ = self.run_job(name)
        frappe.db.commit()  # Simulate the native worker commit after normal app return.
        self.assertIn(job.status, ("Blocked", "Failed"))
        self.assertFalse(self.mapping_rows())
        self.assertFalse(frappe.db.exists("Lead", {"email_id": self.reference + "-contact@example.invalid"}))

    def test_changed_configuration_blocks_old_intent(self):
        name = self.request()
        frappe.db.commit()  # The request must survive the worker's initial rollback.
        frappe.set_user("Administrator")
        self.connection.pipeline_id = self.prefix + "-changed"
        self.connection.save(ignore_permissions=True)
        frappe.db.commit()
        frappe.set_user(self.operator)
        job, remote = self.run_job(name)
        frappe.db.commit()
        self.assert_blocked_before_transport(job, remote, "configuration_changed")

    def test_connection_disable_blocks_committed_intent(self):
        name = self.request()
        frappe.db.commit()  # The request must survive the worker's initial rollback.
        frappe.set_user("Administrator")
        frappe.db.set_value("US Connection", self.connection.name, "enabled", 0)
        frappe.db.commit()
        frappe.set_user(self.operator)
        job, remote = self.run_job(name)
        frappe.db.commit()
        self.assert_blocked_before_transport(job, remote, "connection_disabled")

    def test_handled_failure_rolls_back_real_lead_and_mapping_inserts(self):
        name = self.request()
        frappe.db.commit()  # The request must survive the worker's initial rollback.
        from ultimatesales_connector.service import create_link
        inserted = []

        def fail_after_contact_link(connection, kind, external, **kwargs):
            link = create_link(connection, kind, external, **kwargs)
            inserted.append(link.name)
            if kind == "Contact":
                self.assertTrue(frappe.db.exists("Lead", kwargs["lead"]))
                raise RuleError("synthetic_failure_after_lead_insert")
            return link

        with patch("ultimatesales_connector.service.create_link", side_effect=fail_after_contact_link):
            job, _ = self.run_job(name)
            frappe.db.commit()  # Native worker boundary after a normal return.
        self.assertEqual(job.status, "Failed")
        self.assertEqual(job.error_code, "synthetic_failure_after_lead_insert")
        self.assertTrue(inserted, "The test must reach a real local insert before failing.")
        self.assertFalse(self.mapping_rows())
        self.assertFalse(frappe.db.exists("Lead", {"email_id": self.reference + "-contact@example.invalid"}))

    def test_interrupted_before_commit_remains_recoverable_in_real_sql(self):
        name = self.request()
        frappe.db.commit()  # The request must survive the worker's initial rollback.
        from ultimatesales_connector.jobs import _finish

        def lose_completion(job, status, code, summary):
            if status == "Succeeded":
                raise RuntimeError("Synthetic completion loss")
            return _finish(job, status, code, summary)

        with patch("ultimatesales_connector.jobs._finish", side_effect=lose_completion):
            with self.assertRaises(RuntimeError):
                self.run_job(name)
        frappe.db.rollback()
        self.assertEqual(frappe.db.get_value("US Sync Job", name, "status"), "Queued")
        self.assertFalse(self.mapping_rows())
        recovered, _ = self.run_job(name)
        frappe.db.commit()  # Recovery returned normally; make its completion durable.
        self.assertEqual(recovered.status, "Succeeded", recovered.error_code)
        self.assertEqual(len(self.mapping_rows()), 2)

    def test_remote_success_local_failure_replay_converges_on_real_sql(self):
        import_name = self.request()
        frappe.db.commit()
        imported, _ = self.run_job(import_name)
        frappe.db.commit()
        self.assertEqual(imported.status, "Succeeded", imported.error_code)
        link = next(row for row in self.mapping_rows() if row.record_kind == "Opportunity")
        quote = self.prepare_submitted_quote(link.opportunity, link.lead)
        frappe.db.commit()  # The subsequent worker must see the submitted quotation.
        frappe.set_user("Administrator")
        for key in ("opportunity", "quotation", "state", "currency", "total"):
            self.connection.set("field_" + key, self.prefix + "-" + key)
        # Test fixture contract only: no claim that live fields have been verified.
        self.connection.allow_quotation_export = 1
        self.connection.export_contract_verified = 1
        self.connection.save(ignore_permissions=True)
        frappe.db.commit()
        frappe.set_user(self.operator)
        from ultimatesales_connector.api import request_export
        from ultimatesales_connector.client import HighLevelClient
        from ultimatesales_connector.jobs import run, _finish
        name = request_export(quote.name, preview=0)
        frappe.db.commit()
        remote = SyntheticQuotationHTTP(self.connection, self.reference)

        def lose_completion(job, status, code, summary):
            if status == "Succeeded":
                raise RuntimeError("Synthetic local completion loss after remote acceptance")
            return _finish(job, status, code, summary)

        with patch("ultimatesales_connector.service.get_client", side_effect=lambda _:
                   HighLevelClient("fabricated-test-value", self.connection.location_id, session=remote)):
            with patch("ultimatesales_connector.jobs._finish", side_effect=lose_completion):
                with self.assertRaises(RuntimeError):
                    run(name)
            frappe.db.rollback()
            self.assertEqual(frappe.db.get_value("US Sync Job", name, "status"), "Queued")
            self.assertEqual(remote.put_count, 1)
            run(name)
            frappe.db.commit()  # Commit only after the app returned normally.
        job = frappe.get_doc("US Sync Job", name)
        self.assertEqual(job.status, "Succeeded", job.error_code)
        self.assertIn("no external write", job.result_summary)
        self.assertEqual(remote.put_count, 1)
        self.assertIn({"id": "unrelated", "fieldValue": "preserved synthetic value"}, remote.remote["customFields"])

    def test_operator_cannot_edit_settings_or_read_another_operators_job(self):
        name = self.request()
        frappe.db.commit()  # The request must survive the worker's initial rollback.
        self.assertFalse(frappe.has_permission("US Connection", "write", doc=self.connection))
        frappe.set_user(self.other_operator)
        self.assertFalse(frappe.has_permission("US Sync Job", "read", doc=frappe.get_doc("US Sync Job", name)))
        from ultimatesales_connector.api import retry_job, request_import
        with self.assertRaises((frappe.PermissionError, RuleError)):
            request_import(self.connection.name, self.reference, preview=1)
        with self.assertRaises((frappe.PermissionError, RuleError)):
            retry_job(name)

    def test_guest_and_general_user_cannot_request_or_dispatch(self):
        from ultimatesales_connector.api import dispatch_pending, request_import
        for user in ("Guest", self.general_user):
            frappe.set_user(user)
            with self.assertRaises((frappe.PermissionError, RuleError)):
                request_import(self.connection.name, self.reference, preview=1)
            with self.assertRaises((frappe.PermissionError, RuleError)):
                dispatch_pending()

    def test_system_manager_does_not_execute_as_stored_operator(self):
        from ultimatesales_connector.api import request_import
        frappe.set_user("Administrator")
        with self.assertRaises((frappe.PermissionError, RuleError)):
            request_import(self.connection.name, self.reference, preview=0)
        self.assertFalse(self.mapping_rows())

    def test_internal_audit_documents_reject_direct_document_save_even_for_manager(self):
        name = self.request(preview=1)
        frappe.db.commit()  # The request must survive the worker's initial rollback.
        frappe.set_user("Administrator")
        job = frappe.get_doc("US Sync Job", name)
        job.reference = self.reference + "-tampered"
        with self.assertRaises(frappe.PermissionError):
            job.save(ignore_permissions=True)
        frappe.db.rollback()
        self.assertEqual(frappe.db.get_value("US Sync Job", name, "reference"), self.reference)
