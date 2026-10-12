"""Synthetic installed-site fixtures. Not whitelisted; never a live API adapter.

Explicit site opt-in is mandatory because worker tests commit real SQL data.
These helpers belong only on disposable acceptance sites with synthetic companies.
Native CLI/worker boundaries and concrete installed TestCases own transactions;
shared fixture helpers leave their writes pending for those callers.
"""
from contextlib import contextmanager
import copy
import hashlib
import sys
import time
import unittest
from unittest.mock import patch
from uuid import uuid4

import frappe
from frappe.utils import cint


QUEUE = "us_acceptance"


def bootstrap_synthetic_company():
    """Explicit disposable-CI setup; ordinary Company insert, no CRM credentials.

    This is intentionally separate from preflight, which remains read-only.
    Run through bench execute only after the per-site disposable opt-in is saved.
    The native CLI owns the commit after a successful return; this helper leaves
    every insert pending so a failed invocation can roll back its whole transaction.
    """
    if cint(frappe.conf.get("ultimatesales_connector_acceptance_tests")) != 1:
        raise RuntimeError("Refusing Company creation without explicit disposable acceptance opt-in.")
    if frappe.session.user != "Administrator":
        raise frappe.PermissionError("Synthetic Company bootstrap requires the native site Administrator.")
    suffix = hashlib.sha256(frappe.local.site.encode()).hexdigest()[:6]
    name = "UltimateSales Acceptance " + suffix
    if frappe.db.exists("Company", name):
        existing = frappe.get_doc("Company", name)
        if existing.default_currency != "USD" or existing.country != "Singapore":
            raise RuntimeError("Existing synthetic fixture Company has an unexpected configuration.")
        return name
    company = frappe.get_doc({"doctype": "Company", "company_name": name, "abbr": "UA" + suffix[:3],
                              "country": "Singapore", "default_currency": "USD",
                              "chart_of_accounts": "Standard"}).insert()
    return company.name


def acceptance_preflight():
    """Read-only, secret-free site facts; the external runner captures Git revisions."""
    import erpnext
    import ultimatesales_connector
    from frappe.utils.background_jobs import get_queues_timeout
    from ultimatesales_connector.install import check_environment

    if cint(frappe.conf.get("ultimatesales_connector_acceptance_tests")) != 1:
        raise RuntimeError("Disposable acceptance tests are not explicitly enabled on this site.")
    if cint(frappe.conf.get("ultimatesales_connector_allow_writes")) != 1:
        raise RuntimeError("The disposable acceptance site's persisted write gate must be enabled for child workers.")
    company = frappe.conf.get("ultimatesales_connector_acceptance_company")
    if not company or not frappe.db.exists("Company", company):
        raise RuntimeError("Configure an existing synthetic acceptance Company on this disposable site.")
    if frappe.conf.get("db_type", "mariadb") != "mariadb":
        raise RuntimeError("Acceptance transaction tests target MariaDB only.")
    check_environment()
    if not frappe.db.exists("Role", "UltimateSales Operator"):
        raise RuntimeError("The UltimateSales Operator role is missing; migrate the installed app first.")
    if QUEUE not in get_queues_timeout():
        raise RuntimeError("Configure the dedicated us_acceptance queue in the disposable bench.")
    return {
        "site": frappe.local.site, "company": company, "frappe": frappe.__version__,
        "erpnext": erpnext.__version__, "database": frappe.db.sql("SELECT VERSION()")[0][0],
        "queue": QUEUE, "transport": "synthetic; no live CRM requests", "writes_enabled": True,
        "connector": ultimatesales_connector.__version__, "python": sys.version.split()[0],
    }


class SyntheticClient:
    def __init__(self, connection):
        self.connection = connection
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    def get_opportunity(self, name):
        if not name.startswith("usac-"):
            raise RuntimeError("Acceptance fixtures only accept synthetic references.")
        self.calls.append(("GET opportunity", name))
        return {"id": name, "locationId": self.connection.location_id,
                "pipelineId": self.connection.pipeline_id,
                "pipelineStageId": self.connection.qualified_stage_id,
                "status": "open", "contactId": name + "-contact", "monetaryValue": 123}

    def get_contact(self, name):
        if not name.startswith("usac-"):
            raise RuntimeError("Acceptance fixtures only accept synthetic references.")
        self.calls.append(("GET contact", name))
        return {"id": name, "locationId": self.connection.location_id,
                "firstName": name, "email": name + "@example.invalid"}


class SyntheticQuotationHTTP:
    """Stateful fake HTTP server used with the production HighLevel client."""
    def __init__(self, connection, reference):
        self.headers = {}
        self.trust_env = False
        self.put_count = 0
        self.connection = connection
        self.remote = SyntheticClient(connection).get_opportunity(reference)
        self.remote["customFields"] = [{"id": "unrelated", "fieldValue": "preserved synthetic value"}]

    def close(self):
        pass

    def request(self, method, url, **kwargs):
        from types import SimpleNamespace
        if "/locations/" in url:
            fields = [{"id": self.connection.get("field_" + key), "model": "opportunity",
                       "dataType": "TEXT", "locationId": self.connection.location_id}
                      for key in ("opportunity", "quotation", "state", "currency", "total")]
            return SimpleNamespace(status_code=200, headers={}, content=b"{}",
                                   json=lambda: {"customFields": fields})
        if method == "PUT":
            self.put_count += 1
            fields = copy.deepcopy(kwargs["json"]["customFields"])
            owned = {field["id"] for field in fields}
            self.remote["customFields"] = [field for field in self.remote["customFields"]
                                          if field["id"] not in owned] + fields
        return SimpleNamespace(status_code=200, headers={}, content=b"{}",
                               json=lambda: {"opportunity": copy.deepcopy(self.remote)})


def run_synthetic_import(sync_job_name, expected_user, expected_site, barrier_key=None):
    """Executed by the genuine Frappe/RQ worker under its native enqueue user."""
    acceptance_preflight()
    if frappe.local.site != expected_site or frappe.session.user != expected_user:
        raise RuntimeError("Native worker site or actor differs from its enqueue context.")
    job = frappe.get_doc("US Sync Job", sync_job_name)
    connection = frappe.get_doc("US Connection", job.connection)
    if not connection.connection_name.startswith("usac-") or not job.reference.startswith("usac-"):
        raise RuntimeError("Refusing a non-synthetic acceptance job.")
    from ultimatesales_connector.jobs import run

    if barrier_key:
        from frappe.utils.background_jobs import get_redis_conn
        if not barrier_key.startswith("usac-barrier-"):
            raise RuntimeError("Invalid synthetic barrier.")
        redis = get_redis_conn()
        redis.sadd(barrier_key, sync_job_name)
        redis.expire(barrier_key, 180)
        deadline = time.monotonic() + 30
        while redis.scard(barrier_key) != 2:
            if time.monotonic() >= deadline:
                raise RuntimeError("The second concurrent native worker did not reach the barrier.")
            time.sleep(0.1)

    # The framework already selected the native user before entering this helper.
    # Prevent the app from silently switching identity during its execution.
    with patch("ultimatesales_connector.service.get_client", return_value=SyntheticClient(connection)), \
         patch.object(frappe, "set_user", side_effect=RuntimeError("App attempted identity switching")):
        run(sync_job_name)


class DisposableSiteTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if cint(frappe.conf.get("ultimatesales_connector_acceptance_tests")) != 1:
            raise unittest.SkipTest("Not enabled: disposable installed-site acceptance tests.")
        cls.environment = acceptance_preflight()
        if frappe.db.exists("US Connection", {"enabled": 1}):
            raise RuntimeError("Acceptance requires a disposable site with no enabled connections.")

    def setUp(self):
        """Prepare pending fixture rows; the concrete TestCase owns durability."""
        self.previous_user = frappe.session.user
        self.previous_gate = frappe.conf.get("ultimatesales_connector_allow_writes", 0)
        self.prefix = "usac-" + uuid4().hex[:16]
        self.reference = self.prefix + "-deal"
        self.company = self.environment["company"]
        self.users = []
        self.connections = []
        self.rq_jobs = []
        self.rq_keys = []
        self.quotations = []
        self.items = []
        self.price_lists = []
        frappe.set_user("Administrator")
        self.operator = self.new_user("operator", ["Sales User", "UltimateSales Operator"])
        self.other_operator = self.new_user("other", ["Sales User", "UltimateSales Operator"])
        self.general_user = self.new_user("general", ["Sales User"])
        for user in (self.operator, self.other_operator, self.general_user):
            frappe.get_doc({"doctype": "User Permission", "user": user,
                            "allow": "Company", "for_value": self.company,
                            "apply_to_all_doctypes": 1}).insert(ignore_permissions=True)
        self.connection = self.new_connection(self.operator)
        # Concrete installed TestCases commit this setup before entering jobs.run,
        # which rolls back its initial read-only snapshot. Shared helpers never commit.
        frappe.conf.ultimatesales_connector_allow_writes = 1
        frappe.set_user(self.operator)

    def new_user(self, suffix, roles):
        name = self.prefix + "-" + suffix + "@example.invalid"
        self.users.append(name)
        doc = frappe.get_doc({"doctype": "User", "email": name, "first_name": self.prefix,
                             "enabled": 1, "user_type": "System User", "send_welcome_email": 0,
                             "roles": [{"role": role} for role in roles]})
        doc.insert(ignore_permissions=True)
        frappe.clear_cache(user=name)
        return name

    def new_connection(self, user):
        suffix = "-" + str(len(self.connections) + 1)
        doc = frappe.get_doc({
            "doctype": "US Connection", "connection_name": self.prefix + suffix,
            "company": self.company, "crm_currency": frappe.db.get_value("Company", self.company, "default_currency"),
            "integration_user": user, "location_id": self.prefix + suffix + "-location",
            "pipeline_id": self.prefix + "-pipeline", "qualified_stage_id": self.prefix + "-stage",
            "enabled": 1, "preview_only": 0, "allow_quotation_export": 0,
            "api_token": "fabricated-acceptance-value-never-sent",
        }).insert(ignore_permissions=True)
        self.connections.append(doc.name)
        return doc

    def request(self, *, preview=0):
        """Create a pending request; commit explicitly before worker dispatch."""
        from ultimatesales_connector.api import request_import
        name = request_import(self.connection.name, self.reference, preview=preview)
        return name

    @contextmanager
    def transport(self):
        remote = SyntheticClient(self.connection)
        with patch("ultimatesales_connector.service.get_client", return_value=remote):
            yield remote

    def run_job(self, name):
        """Run with synthetic transport; the owning test commits normal completion."""
        from ultimatesales_connector.jobs import run
        with self.transport() as remote:
            run(name)
        return frappe.get_doc("US Sync Job", name), remote

    def mapping_rows(self):
        return frappe.get_all("US Record Link", filters={"connection": self.connection.name},
                              fields=["name", "record_kind", "lead", "opportunity", "company"])

    def cleanup_fixture(self):
        """Delete exact fixture rows; teardown owns commit and context restoration."""
        frappe.db.rollback()
        frappe.set_user("Administrator")
        for name in self.connections:
            if frappe.db.exists("US Connection", name):
                frappe.db.set_value("US Connection", name, "enabled", 0)
        for name in self.quotations:
            if frappe.db.exists("Quotation", name):
                quote = frappe.get_doc("Quotation", name)
                if quote.docstatus == 1:
                    quote.cancel()
                frappe.delete_doc("Quotation", name, ignore_permissions=True)
        leads, opportunities = set(), set()
        for name in self.connections:
            rows = frappe.get_all("US Record Link", filters={"connection": name},
                                  fields=["lead", "opportunity"])
            leads.update(row.lead for row in rows if row.lead)
            opportunities.update(row.opportunity for row in rows if row.opportunity)
            # Exact synthetic connection only, never table-wide deletes.
            frappe.db.delete("US Sync Job", {"connection": name})
            frappe.db.delete("US Record Link", {"connection": name})
        # Catch a fixture failure between business insertion and mapping insertion.
        leads.update(frappe.get_all("Lead", filters={"email_id": self.reference + "-contact@example.invalid"}, pluck="name"))
        for name in opportunities:
            if frappe.db.exists("Opportunity", name):
                frappe.delete_doc("Opportunity", name, ignore_permissions=True)
        for name in leads:
            if frappe.db.exists("Lead", name):
                frappe.delete_doc("Lead", name, ignore_permissions=True)
        for name in self.connections:
            if frappe.db.exists("US Connection", name):
                frappe.delete_doc("US Connection", name, ignore_permissions=True)
        for name in self.users:
            frappe.db.delete("User Permission", {"user": name})
            if frappe.db.exists("User", name):
                frappe.delete_doc("User", name, ignore_permissions=True)
            frappe.clear_cache(user=name)
        for job in self.rq_jobs:
            job.delete()
        if self.rq_keys:
            from frappe.utils.background_jobs import get_redis_conn
            for key in self.rq_keys:
                get_redis_conn().delete(key)
        for name in self.items:
            if frappe.db.exists("Item", name):
                # ERPNext may create a rate during normal quotation validation.
                frappe.db.delete("Item Price", {"item_code": name})
                frappe.delete_doc("Item", name, ignore_permissions=True)
        for name in self.price_lists:
            if frappe.db.exists("Price List", name):
                frappe.delete_doc("Price List", name, ignore_permissions=True)
        # Concrete TestCase teardown commits successful cleanup and restores context.

    def prepare_submitted_quote(self, opportunity, lead):
        """Normal ERPNext Item/Quotation setup; no raw docstatus fixture writes."""
        frappe.set_user("Administrator")
        item = frappe.get_doc({"doctype": "Item", "item_code": self.prefix + "-service",
                               "item_name": self.prefix + " synthetic service", "item_group": "All Item Groups",
                               "stock_uom": "Nos", "is_stock_item": 0}).insert(ignore_permissions=True)
        self.items.append(item.name)
        prices = frappe.get_doc({"doctype": "Price List", "price_list_name": self.prefix + "-prices",
                                 "selling": 1, "enabled": 1,
                                 "currency": self.connection.crm_currency}).insert(ignore_permissions=True)
        self.price_lists.append(prices.name)
        frappe.set_user(self.operator)
        quote = frappe.get_doc({
            "doctype": "Quotation", "quotation_to": "Lead", "party_name": lead,
            "company": self.company, "opportunity": opportunity, "currency": self.connection.crm_currency,
            "conversion_rate": 1, "selling_price_list": prices.name,
            "price_list_currency": self.connection.crm_currency, "plc_conversion_rate": 1,
            "items": [{"item_code": item.name, "qty": 1, "rate": 100}],
        }).insert()
        self.quotations.append(quote.name)
        quote.submit()
        return quote
