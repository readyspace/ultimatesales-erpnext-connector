"""Real Redis/RQ/native session checks; synthetic CRM only; disposable sites only."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import shutil
import subprocess
from unittest.mock import patch

import frappe

from ultimatesales_connector.tests.acceptance_support import DisposableSiteTestCase, QUEUE


class TestNativeQueue(DisposableSiteTestCase):
    def setUp(self):
        try:
            super().setUp()
            self.bench_executable = shutil.which("bench")
            self.bench_dir = Path(frappe.get_site_path()).resolve().parents[1]
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

    def start_worker(self):
        """Concrete native-process test orchestration; shared fixtures never launch processes."""
        self.assertIsNotNone(self.bench_executable, "The Bench executable is required for the real worker test.")
        result = subprocess.run(
            [self.bench_executable, "worker", "--queue", QUEUE, "--burst", "--quiet"],
            cwd=self.bench_dir, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            shell=False, timeout=90, check=False,
        )
        self.assertEqual(result.returncode, 0, "Dedicated acceptance worker failed; review local bench logs.")

    def enqueue_probe(self, name, barrier_key=None):
        queued = frappe.enqueue(
            "ultimatesales_connector.tests.acceptance_support.run_synthetic_import",
            queue=QUEUE, timeout=120, enqueue_after_commit=False,
            sync_job_name=name, expected_user=self.operator, expected_site=frappe.local.site,
            barrier_key=barrier_key,
        )
        self.rq_jobs.append(queued)
        self.assertEqual(queued.kwargs["user"], self.operator)
        self.assertEqual(queued.kwargs["site"], frappe.local.site)
        self.assertNotIn("user", queued.kwargs["kwargs"])
        return queued

    def test_real_worker_preserves_native_operator_and_site(self):
        # The acceptance runner runs this same external identity on both isolated
        # sites. The native worker independently asserts its own site and actor.
        self.reference = "usac-shared-site-isolation"
        name = self.request()
        frappe.db.commit()  # Commit the SQL intent before enqueueing a separate worker.
        queued = self.enqueue_probe(name)
        self.start_worker()
        frappe.db.rollback()  # Refresh the parent process read snapshot after child commits.
        self.assertEqual(str(queued.get_status(refresh=True)).lower().split(".")[-1], "finished")
        job = frappe.get_doc("US Sync Job", name)
        self.assertEqual(job.status, "Succeeded", job.error_code)
        rows = self.mapping_rows()
        self.assertEqual(len(rows), 2)
        self.assertEqual(frappe.db.get_value("Lead", rows[0].lead, "owner"), self.operator)

    def test_concurrent_native_workers_serialize_same_external_deal(self):
        # Separate durable intents, same deal; two actual worker processes/database connections.
        names = [self.request(), self.request()]
        frappe.db.commit()  # Both intents must be visible to separate worker connections.
        barrier = "usac-barrier-" + frappe.local.site + "-" + self.prefix
        self.rq_keys.append(barrier)
        queued = [self.enqueue_probe(name, barrier_key=barrier) for name in names]
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = [executor.submit(self.start_worker) for _ in range(2)]
            for result in results:
                result.result(timeout=120)
        frappe.db.rollback()
        for name, rq_job in zip(names, queued):
            self.assertEqual(str(rq_job.get_status(refresh=True)).lower().split(".")[-1], "finished")
            self.assertEqual(frappe.db.get_value("US Sync Job", name, "status"), "Succeeded")
        rows = self.mapping_rows()
        self.assertEqual(len(rows), 2)
        self.assertEqual(len({row.lead for row in rows}), 1)
        self.assertEqual(sum(bool(row.opportunity) for row in rows), 1)

    def test_redis_submission_failure_keeps_sql_intent_for_operator_dispatch(self):
        name = self.request()
        frappe.db.commit()  # Commit the SQL intent before enqueueing a separate worker.
        from ultimatesales_connector.api import dispatch_pending
        with patch.object(frappe, "enqueue", side_effect=ConnectionError("Synthetic queue outage")):
            with self.assertRaises(ConnectionError):
                dispatch_pending()
        frappe.db.rollback()
        self.assertEqual(frappe.db.get_value("US Sync Job", name, "status"), "Queued")
        # This real enqueue/worker is the recovery path, still under the operator.
        queued = self.enqueue_probe(name)
        self.start_worker()
        frappe.db.rollback()
        self.assertEqual(str(queued.get_status(refresh=True)).lower().split(".")[-1], "finished")
        self.assertEqual(frappe.db.get_value("US Sync Job", name, "status"), "Succeeded")

    def test_dispatch_enqueues_only_current_operators_committed_due_jobs(self):
        mine = self.request(preview=1)
        frappe.db.commit()
        # Change the designated operator without any business mappings, request as
        # that actual user, then restore the first operator. Ownership remains durable.
        frappe.set_user("Administrator")
        self.connection.integration_user = self.other_operator
        self.connection.save(ignore_permissions=True)
        frappe.db.commit()
        frappe.set_user(self.other_operator)
        from ultimatesales_connector.api import request_import, dispatch_pending
        theirs = request_import(self.connection.name, self.reference + "-other", preview=1)
        frappe.db.commit()
        frappe.set_user("Administrator")
        self.connection.integration_user = self.operator
        self.connection.save(ignore_permissions=True)
        frappe.db.commit()
        frappe.set_user(self.operator)
        with patch.object(frappe, "enqueue") as enqueue:
            dispatch_pending()
        selected = {call.kwargs["sync_job_name"] for call in enqueue.call_args_list}
        self.assertIn(mine, selected)
        self.assertNotIn(theirs, selected)
