"""Framework-independent rules. No network, database, secrets or Frappe imports."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from email.utils import parsedate_to_datetime
from typing import Any

ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,140}$")
API_BASE = "https://services.leadconnectorhq.com"
API_VERSION = "v3"
EXPORT_KEYS = ("opportunity", "quotation", "state", "currency", "total")
MAX_ATTEMPTS = 5


class RuleError(Exception):
    """An allowlisted error code; never put contact data or tokens in this error."""
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def external_id(value: Any) -> str:
    if not isinstance(value, str) or not ID_PATTERN.fullmatch(value):
        raise RuleError("invalid_external_id")
    return value


def safe_text(value: Any, maximum: int = 140) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise RuleError("invalid_text_value")
    result = unicodedata.normalize("NFC", value).strip()
    if len(result) > maximum or any(unicodedata.category(c) == "Cc" for c in result):
        raise RuleError("invalid_text_value")
    # Imported fields are plain text, not rich HTML. Fail closed on markup.
    if "<" in result or ">" in result:
        raise RuleError("html_not_allowed")
    return result


def normalized_email(value: Any) -> str:
    value = safe_text(value, 254).lower()
    if value and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
        raise RuleError("invalid_email")
    return value


def decimal_text(value: Any, *, nonnegative: bool = False) -> str:
    if isinstance(value, bool):
        raise RuleError("invalid_amount")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise RuleError("invalid_amount") from None
    if not result.is_finite() or abs(result) > Decimal("1000000000000000"):
        raise RuleError("invalid_amount")
    if nonnegative and result < 0:
        raise RuleError("invalid_amount")
    return format(result, "f")


def stable_key(*parts: Any) -> str:
    # JSON avoids collisions caused by delimiter-containing document names.
    encoded = json.dumps(parts, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def verify_record(record: Any, expected_id: str, location_id: str) -> dict:
    if not isinstance(record, dict):
        raise RuleError("invalid_api_contract")
    if record.get("id") != external_id(expected_id):
        raise RuleError("external_id_mismatch")
    if record.get("locationId") != external_id(location_id):
        raise RuleError("location_mismatch")
    return record


def verify_opportunity(record: Any, expected_id: str, location: str,
                       pipeline: str, stage: str, *, require_qualified: bool) -> dict:
    record = verify_record(record, expected_id, location)
    if record.get("pipelineId") != external_id(pipeline):
        raise RuleError("pipeline_mismatch")
    if require_qualified and (
        record.get("pipelineStageId") != external_id(stage) or record.get("status") != "open"
    ):
        raise RuleError("opportunity_not_in_qualified_open_stage")
    return record


def opportunity_contact_id(record: dict) -> str:
    nested = record.get("contact") or {}
    nested_id = nested.get("id") if isinstance(nested, dict) else None
    direct = record.get("contactId")
    if direct and nested_id and direct != nested_id:
        raise RuleError("contact_identity_mismatch")
    return external_id(direct or nested_id)


def lead_values(contact: dict) -> dict:
    first = safe_text(contact.get("firstName"))
    last = safe_text(contact.get("lastName"))
    if not first:
        name = safe_text(contact.get("name"))
        first = name or f"CRM contact {external_id(contact['id'])}"
        last = ""
    return {
        "first_name": first,
        "last_name": last,
        "email_id": normalized_email(contact.get("email")),
        "mobile_no": safe_text(contact.get("phone"), 40),
        "company_name": safe_text(contact.get("companyName")),
    }


def export_values(quotation: dict, opportunity: str) -> dict[str, str]:
    # Submitted is NOT equivalent to sent, accepted, paid, or won.
    status = quotation.get("docstatus")
    if status not in (1, 2):
        raise RuleError("quotation_not_submitted_or_cancelled")
    currency = safe_text(quotation.get("currency"), 8)
    if not currency:
        raise RuleError("quotation_currency_missing")
    return {
        "opportunity": safe_text(opportunity),
        "quotation": safe_text(quotation.get("name")),
        "state": "Submitted" if status == 1 else "Cancelled",
        "currency": currency,
        "total": decimal_text(quotation.get("grand_total")),
    }


def custom_field_payload(values: dict, mapping: dict) -> dict:
    if set(values) != set(EXPORT_KEYS) or set(mapping) != set(EXPORT_KEYS):
        raise RuleError("incomplete_export_mapping")
    ids = [external_id(mapping[k]) for k in EXPORT_KEYS]
    if len(ids) != len(set(ids)):
        raise RuleError("duplicate_export_field_id")
    return {"customFields": [
        {"id": mapping[k], "fieldValue": str(values[k])} for k in EXPORT_KEYS
    ]}


def custom_fields_match(record: dict, payload: dict) -> bool:
    fields = record.get("customFields", [])
    if not isinstance(fields, list):
        raise RuleError("invalid_api_contract")
    current = {f.get("id"): f.get("fieldValue") for f in fields if isinstance(f, dict)}
    return all(current.get(f["id"]) == f["fieldValue"] for f in payload["customFields"])


def parse_retry_after(value: str | None, now: datetime | None = None) -> int:
    if not value:
        return 0
    try:
        return max(0, int(value))
    except (ValueError, TypeError):
        pass
    try:
        date = parsedate_to_datetime(value)
        if date.tzinfo is None:
            date = date.replace(tzinfo=timezone.utc)
        seconds = (date - (now or datetime.now(timezone.utc))).total_seconds()
        return max(0, int(seconds) + 1)
    except (ValueError, TypeError, OverflowError):
        return 0


def retry_delay(attempt: int, retry_after: int = 0) -> int:
    # Never retry earlier than a server-provided Retry-After.
    return max(min(30 * (2 ** min(max(attempt - 1, 0), 8)), 1800), retry_after)


def effective_preview(job_preview: bool, connection_preview: bool, writes_allowed: bool) -> bool:
    return bool(job_preview or connection_preview or not writes_allowed)


def connection_fingerprint(connection) -> str:
    """Pin each queued intent to routing/configuration, but allow safe token rotation."""
    fields = ("name", "company", "location_id", "pipeline_id", "qualified_stage_id",
              "crm_currency", "integration_user") + tuple("field_" + k for k in EXPORT_KEYS)
    return stable_key("configuration", *(connection.get(key) for key in fields))
