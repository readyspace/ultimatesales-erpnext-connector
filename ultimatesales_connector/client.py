"""Small HighLevel v3 adapter. Fixed HTTPS host, no redirects, no raw-body logging."""
from __future__ import annotations

from typing import Any
import re

import requests

from .domain import (
    API_BASE, API_VERSION, RuleError, custom_fields_match, external_id,
    parse_retry_after, verify_record,
)


class APIError(Exception):
    def __init__(self, code: str, *, retryable: bool = False,
                 retry_after: int = 0, status: int | None = None):
        self.code = code
        self.retryable = retryable
        self.retry_after = retry_after
        self.status = status
        super().__init__(code)


class HighLevelClient:
    def __init__(self, token: str, location_id: str, session=None):
        if not isinstance(token, str) or not token.strip() or "\n" in token or "\r" in token:
            raise RuleError("missing_or_invalid_token")
        self.location_id = external_id(location_id)
        self.session = session or requests.Session()
        self.session.trust_env = False
        self.session.headers.update({
            "Authorization": f"Bearer {token.strip()}",
            "Version": API_VERSION,
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "ReadySpace-UltimateSales-ERPNext/0.1.0a3",
        })

    def close(self):
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def _request(self, method: str, path: str, **kwargs) -> dict[str, Any]:
        # All callers construct paths solely from validated identifiers.
        if not re.fullmatch(r"/(?:opportunities/[A-Za-z0-9_-]{1,140}|contacts/[A-Za-z0-9_-]{1,140}|locations/[A-Za-z0-9_-]{1,140}/customFields)", path):
            raise RuleError("invalid_api_path")
        if method not in ("GET", "PUT") or (method == "PUT" and not path.startswith("/opportunities/")):
            raise RuleError("invalid_api_method")
        try:
            response = self.session.request(
                method, API_BASE + path, timeout=(5, 25),
                allow_redirects=False, verify=True, **kwargs,
            )
        except requests.RequestException:
            # Original exceptions can contain URLs, response bodies or bearer tokens.
            raise APIError("transport_error", retryable=True) from None
        code = response.status_code
        if code == 429:
            raise APIError("rate_limited", retryable=True, status=code,
                           retry_after=parse_retry_after(response.headers.get("Retry-After")))
        if 500 <= code <= 599:
            raise APIError("remote_service_error", retryable=True, status=code)
        if not 200 <= code <= 299:
            message = {
                401: "authentication_failed", 403: "scope_or_location_forbidden",
                404: "external_record_not_found",
            }.get(code, "remote_request_rejected")
            raise APIError(message, status=code)
        if len(response.content) > 2_000_000:
            raise APIError("response_too_large")
        try:
            data = response.json()
        except ValueError:
            raise APIError("invalid_json_response") from None
        if not isinstance(data, dict):
            raise APIError("invalid_response_shape")
        return data

    def get_opportunity(self, opportunity_id: str) -> dict:
        opportunity_id = external_id(opportunity_id)
        data = self._request("GET", "/opportunities/" + opportunity_id)
        return verify_record(data.get("opportunity"), opportunity_id, self.location_id)

    def get_contact(self, contact_id: str) -> dict:
        contact_id = external_id(contact_id)
        data = self._request("GET", "/contacts/" + contact_id)
        return verify_record(data.get("contact"), contact_id, self.location_id)

    def get_pipelines(self) -> list[dict]:
        data = self._request("GET", "/opportunities/pipelines", params={"locationId": self.location_id})
        pipelines = data.get("pipelines")
        if not isinstance(pipelines, list) or any(not isinstance(p, dict) for p in pipelines):
            raise RuleError("invalid_api_contract")
        for pipeline in pipelines:
            external_id(pipeline.get("id"))
            if pipeline.get("locationId", self.location_id) != self.location_id:
                raise RuleError("location_mismatch")
        return pipelines

    def get_opportunity_fields(self) -> list[dict]:
        data = self._request("GET", "/locations/" + self.location_id + "/customFields",
                             params={"model": "opportunity"})
        fields = data.get("customFields")
        if not isinstance(fields, list) or any(not isinstance(f, dict) for f in fields):
            raise RuleError("invalid_api_contract")
        for field in fields:
            external_id(field.get("id"))
            if field.get("locationId", self.location_id) != self.location_id:
                raise RuleError("location_mismatch")
        return fields

    def update_opportunity_fields(self, opportunity_id: str, payload: dict, *, before=None) -> None:
        if set(payload) != {"customFields"}:
            raise RuleError("only_custom_fields_may_be_exported")
        fields = payload.get("customFields")
        if not isinstance(fields, list) or len(fields) != 5:
            raise RuleError("incomplete_export_mapping")
        ids = []
        for field in fields:
            if not isinstance(field, dict) or set(field) != {"id", "fieldValue"}:
                raise RuleError("invalid_custom_field_payload")
            ids.append(external_id(field["id"]))
            if not isinstance(field["fieldValue"], str):
                raise RuleError("export_requires_text_fields")
        if len(ids) != len(set(ids)):
            raise RuleError("duplicate_export_field_id")
        opportunity_id = external_id(opportunity_id)
        before = before if before is not None else self.get_opportunity(opportunity_id)
        verify_record(before, opportunity_id, self.location_id)
        owned_ids = set(ids)
        unrelated = self._unrelated_fields(before, owned_ids)
        # The service verifies current location, contact, pipeline and ERP ownership
        # immediately before invoking this narrowly scoped method.
        data = self._request("PUT", "/opportunities/" + opportunity_id, json=payload)
        verify_record(data.get("opportunity"), opportunity_id, self.location_id)
        actual = self.get_opportunity(opportunity_id)
        if not custom_fields_match(actual, payload):
            raise APIError("export_readback_mismatch")
        if self._unrelated_fields(actual, owned_ids) != unrelated:
            raise APIError("unrelated_custom_fields_changed")
        for key in ("name", "pipelineId", "pipelineStageId", "status", "contactId", "monetaryValue"):
            if key in before and actual.get(key) != before[key]:
                raise APIError("unowned_opportunity_fields_changed")

    @staticmethod
    def _unrelated_fields(record, owned_ids):
        fields = record.get("customFields", [])
        if not isinstance(fields, list):
            raise RuleError("invalid_api_contract")
        result = {}
        for field in fields:
            if not isinstance(field, dict) or not field.get("id") or field["id"] in result:
                raise RuleError("invalid_api_contract")
            if field["id"] not in owned_ids:
                result[field["id"]] = field.get("fieldValue")
        return result
