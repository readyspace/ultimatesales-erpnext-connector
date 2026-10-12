from datetime import datetime, timezone
from decimal import Decimal

import pytest

from ultimatesales_connector.domain import (
    EXPORT_KEYS, RuleError, connection_fingerprint, custom_field_payload, custom_fields_match,
    decimal_text, effective_preview, export_values, external_id, lead_values, normalized_email,
    opportunity_contact_id, parse_retry_after, retry_delay, safe_text, stable_key,
    verify_opportunity, verify_record,
)


@pytest.mark.parametrize("value", ["abc123", "x-y_z", "id-123456"])
def test_valid_external_id(value):
    assert external_id(value) == value


@pytest.mark.parametrize("value", [None, 17, "", "../contacts", "x/y", "x?token=a", "a\n", "https://evil.test", "x" * 141])
def test_rejects_unsafe_external_id(value):
    with pytest.raises(RuleError):
        external_id(value)


def test_identity_keys_do_not_collide_across_boundaries():
    assert stable_key("a:b", "c") != stable_key("a", "b:c")
    assert stable_key("loc1", "contact1") != stable_key("loc2", "contact1")
    assert stable_key("a", "b") == stable_key("a", "b")


def test_verify_record_rejects_different_location():
    with pytest.raises(RuleError, match="location_mismatch"):
        verify_record({"id": "a", "locationId": "other"}, "a", "expected")


@pytest.mark.parametrize("record,code", [([], "invalid_api_contract"), ({"id": "wrong"}, "external_id_mismatch")])
def test_contract_failures(record, code):
    with pytest.raises(RuleError, match=code):
        verify_record(record, "a", "loc")


def remote(**changes):
    return {"id": "opp", "locationId": "loc", "pipelineId": "pipeline",
            "pipelineStageId": "qualified", "status": "open", **changes}


def test_qualification_is_required_only_for_initial_handoff():
    assert verify_opportunity(remote(), "opp", "loc", "pipeline", "qualified", require_qualified=True)
    with pytest.raises(RuleError, match="qualified"):
        verify_opportunity(remote(status="won"), "opp", "loc", "pipeline", "qualified", require_qualified=True)
    assert verify_opportunity(remote(status="won", pipelineStageId="later"), "opp", "loc", "pipeline", "qualified", require_qualified=False)


def test_pipeline_mismatch_is_always_blocked():
    with pytest.raises(RuleError, match="pipeline_mismatch"):
        verify_opportunity(remote(pipelineId="other"), "opp", "loc", "pipeline", "qualified", require_qualified=False)


def test_contact_identity_does_not_silently_change():
    with pytest.raises(RuleError, match="contact_identity_mismatch"):
        opportunity_contact_id({"contactId": "a", "contact": {"id": "b"}})
    assert opportunity_contact_id({"contact": {"id": "a"}}) == "a"
    assert opportunity_contact_id({"contactId": "a"}) == "a"


def test_lead_mapping_is_allowlisted_and_does_not_copy_marketing_consent():
    result = lead_values({"id": "c", "firstName": " Alice ", "lastName": "Tan",
                          "email": "ALICE@EXAMPLE.TEST", "phone": "+6512345678", "dnd": False,
                          "tags": ["subscribe"], "companyName": "Example Pte Ltd"})
    assert result["first_name"] == "Alice"
    assert result["email_id"] == "alice@example.test"
    assert set(result) == {"first_name", "last_name", "email_id", "mobile_no", "company_name"}
    assert lead_values({"id": "c"})["first_name"] == "CRM contact c"


@pytest.mark.parametrize("value", ["<script>bad</script>", "hi\x00there", "x" * 141, 100])
def test_bad_imported_text_rejected(value):
    with pytest.raises(RuleError):
        safe_text(value)


def test_email_validation():
    assert normalized_email(None) == ""
    assert normalized_email(" A@EXAMPLE.TEST ") == "a@example.test"
    with pytest.raises(RuleError):
        normalized_email("Name <a@example.test>")
    with pytest.raises(RuleError):
        normalized_email("not-an-email")


@pytest.mark.parametrize("value", [float("nan"), float("inf"), "NaN", True, None, "bad", "1e99"])
def test_invalid_amounts_rejected(value):
    with pytest.raises(RuleError, match="invalid_amount"):
        decimal_text(value)


def test_decimal_currency_precision_preserved():
    assert decimal_text(Decimal("123.456")) == "123.456"
    with pytest.raises(RuleError):
        decimal_text(-1, nonnegative=True)


def quote(**changes):
    return {"name": "Q-0001", "docstatus": 1, "currency": "SGD", "grand_total": "100.50", **changes}


def test_quote_submission_is_not_sent_paid_or_won():
    values = export_values(quote(), "OPP-0001")
    assert values["state"] == "Submitted"
    assert values["total"] == "100.50"
    assert export_values(quote(docstatus=2), "OPP-0001")["state"] == "Cancelled"
    assert set(values) == set(EXPORT_KEYS)


@pytest.mark.parametrize("status", [0, None, 3])
def test_draft_quotes_never_export(status):
    with pytest.raises(RuleError):
        export_values(quote(docstatus=status), "OPP-0001")


def test_currency_required():
    with pytest.raises(RuleError):
        export_values(quote(currency=""), "OPP-0001")


def mapping():
    return {key: "field_" + key for key in EXPORT_KEYS}


def test_export_cannot_modify_pipeline_or_contact():
    payload = custom_field_payload(export_values(quote(), "OPP-0001"), mapping())
    assert set(payload) == {"customFields"}
    assert len(payload["customFields"]) == 5
    assert all(set(f) == {"id", "fieldValue"} for f in payload["customFields"])
    assert custom_fields_match({"customFields": payload["customFields"]}, payload)
    assert not custom_fields_match({"customFields": []}, payload)


def test_incomplete_and_duplicate_field_mappings_rejected():
    with pytest.raises(RuleError):
        custom_field_payload(export_values(quote(), "OPP"), {})
    with pytest.raises(RuleError):
        custom_field_payload(export_values(quote(), "OPP"), {k: "same" for k in EXPORT_KEYS})
    with pytest.raises(RuleError):
        custom_fields_match({"customFields": {}}, {"customFields": []})


def test_retry_after_seconds_and_http_date():
    now = datetime(2026, 10, 12, 0, 0, tzinfo=timezone.utc)
    assert parse_retry_after("120", now) == 120
    assert parse_retry_after("Mon, 12 Oct 2026 00:02:00 GMT", now) >= 120
    assert parse_retry_after("invalid", now) == 0
    assert parse_retry_after(None, now) == 0
    assert parse_retry_after("-10", now) == 0
    assert retry_delay(2, 86400) == 86400
    assert retry_delay(100) == 1800


@pytest.mark.parametrize("job,connection,writes,expected", [
    (False, False, True, False), (True, False, True, True),
    (False, True, True, True), (False, False, False, True),
])
def test_three_independent_preview_gates(job, connection, writes, expected):
    assert effective_preview(job, connection, writes) is expected


def test_queued_configuration_pins_routing_but_not_rotated_secret():
    a = {"name": "c", "location_id": "loc", "company": "Company", "api_token": "old"}
    b = {**a, "api_token": "rotated"}
    assert connection_fingerprint(a) == connection_fingerprint(b)
    assert connection_fingerprint(a) != connection_fingerprint({**a, "location_id": "other"})
    assert connection_fingerprint(a) != connection_fingerprint({**a, "field_state": "new-field"})
