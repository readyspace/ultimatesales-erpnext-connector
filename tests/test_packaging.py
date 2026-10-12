import ast
import json
from pathlib import Path
import tomllib

ROOT = Path(__file__).parents[1]


def schema(name):
    return json.loads((ROOT / "ultimatesales_connector" / "ultimatesales_connector" / "doctype" / name / (name + ".json")).read_text())


def test_module_and_doctype_paths_match():
    for name in ("us_connection", "us_record_link", "us_sync_job"):
        data = schema(name)
        assert data["module"] == "UltimateSales Connector"
        assert set(data["field_order"]) == {f["fieldname"] for f in data["fields"]}
        assert len(data["field_order"]) == len(data["fields"])
        assert data["engine"] == "InnoDB"


def test_defaults_cannot_write_or_export():
    fields = {f["fieldname"]: f for f in schema("us_connection")["fields"]}
    assert fields["enabled"]["default"] == "0"
    assert fields["preview_only"]["default"] == "1"
    assert fields["allow_quotation_export"]["default"] == "0"
    assert fields["api_token"]["fieldtype"] == "Password"
    assert fields["location_id"]["unique"] == 1


def test_connector_records_are_not_public_or_general_sales_visible():
    for name in ("us_connection", "us_record_link", "us_sync_job"):
        permissions = schema(name)["permissions"]
        assert {p["role"] for p in permissions} == {"System Manager", "UltimateSales Operator", "UltimateSales Auditor"}
        assert not any(p.get("write") or p.get("create") or p.get("delete")
                       for p in permissions if p["role"] != "System Manager")
        if name != "us_connection":
            assert not any(p.get("write") or p.get("create") or p.get("delete") for p in permissions)


def test_public_endpoints_are_post_only_and_not_guest():
    tree = ast.parse((ROOT / "ultimatesales_connector" / "api.py").read_text())
    functions = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
    assert {f.name for f in functions} == {"request_import", "request_export", "bind_existing_lead",
        "retry_job", "dispatch_pending", "setup_diagnostics", "test_connection", "job_diagnostics"}
    for func in functions:
        decorator = func.decorator_list[0]
        assert isinstance(decorator, ast.Call)
        assert {kw.arg: ast.literal_eval(kw.value) for kw in decorator.keywords} == {"methods": ["POST"]}
        first = ast.unparse(func.body[0])
        assert "require_operator" in first or "Guest" in first


def test_no_core_override_hooks_or_hr_dependency():
    namespace = {}
    exec((ROOT / "ultimatesales_connector" / "hooks.py").read_text(), namespace)
    assert namespace["required_apps"] == ["erpnext"]
    assert set(namespace["doc_events"]) == {"Quotation"}
    assert "override_doctype_class" not in namespace
    assert "override_whitelisted_methods" not in namespace


def test_dependency_target_is_explicit_not_all_versions():
    data = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert data["tool"]["bench"]["frappe-dependencies"]["frappe"] == ">=16.0.0,<17.0.0"
    assert data["project"]["version"] == "0.1.0a3"
