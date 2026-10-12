import json

import pytest
import requests

from ultimatesales_connector.client import APIError, HighLevelClient
from ultimatesales_connector.domain import API_BASE, RuleError


class Response:
    def __init__(self, data=None, status=200, headers=None, raw=None):
        self.data = data
        self.status_code = status
        self.headers = headers or {}
        self.content = raw if raw is not None else json.dumps(data).encode()

    def json(self):
        if self.data == "INVALID":
            raise ValueError("private body must not leak")
        return self.data


class Session:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.headers = {}
        self.calls = []
        self.closed = False

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        result = self.responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    def close(self):
        self.closed = True


def record(**kw):
    return {"id": "opp", "locationId": "loc", **kw}


def client(*responses):
    session = Session(*responses)
    return HighLevelClient("not-a-real-secret", "loc", session=session), session


def test_fixed_host_version_tls_no_redirects_and_session_cleanup():
    c, session = client(Response({"opportunity": record()}))
    with c:
        assert c.get_opportunity("opp")["id"] == "opp"
    method, url, opts = session.calls[0]
    assert method == "GET" and url == API_BASE + "/opportunities/opp"
    assert opts["allow_redirects"] is False and opts["verify"] is True
    assert opts["timeout"] == (5, 25)
    assert session.headers["Version"] == "v3"
    assert session.trust_env is False
    assert session.closed


def test_contact_location_verified():
    c, _ = client(Response({"contact": {"id": "contact", "locationId": "other"}}))
    with pytest.raises(RuleError, match="location_mismatch"):
        c.get_contact("contact")


def test_contact_retrieval():
    c, _ = client(Response({"contact": {"id": "contact", "locationId": "loc"}}))
    assert c.get_contact("contact")["id"] == "contact"


@pytest.mark.parametrize("status,retryable", [(401, False), (403, False), (404, False), (422, False), (302, False), (429, True), (500, True), (503, True)])
def test_http_errors_are_classified_without_body_leaks(status, retryable):
    c, _ = client(Response({"email": "PRIVATE", "token": "SECRET"}, status=status, headers={"Retry-After": "80"}))
    with pytest.raises(APIError) as caught:
        c.get_opportunity("opp")
    error = caught.value
    assert error.retryable is retryable
    assert "PRIVATE" not in str(error) and "SECRET" not in str(error)
    assert error.status == status
    if status == 429:
        assert error.retry_after == 80


def test_transport_exception_does_not_expose_secret():
    c, _ = client(requests.Timeout("Authorization: Bearer SUPERSECRET"))
    with pytest.raises(APIError) as error:
        c.get_opportunity("opp")
    assert str(error.value) == "transport_error" and error.value.retryable


@pytest.mark.parametrize("response", [Response("INVALID"), Response([]), Response({}, raw=b"x" * 2_000_001)])
def test_malformed_responses_fail_closed(response):
    c, _ = client(response)
    with pytest.raises(APIError):
        c.get_opportunity("opp")


def test_invalid_id_never_makes_network_call():
    c, s = client()
    with pytest.raises(RuleError):
        c.get_opportunity("../contacts")
    assert not s.calls


def payload():
    return {"customFields": [{"id": f"field{i}", "fieldValue": str(i)} for i in range(5)]}


def test_only_mapped_fields_are_sent_and_readback_verified():
    data = payload()
    c, s = client(Response({"opportunity": record()}), Response({"opportunity": record(**data)}))
    c.update_opportunity_fields("opp", data, before=record())
    assert s.calls[0][0] == "PUT"
    assert s.calls[0][2]["json"] == data
    assert s.calls[1][0] == "GET"


def test_failed_readback_is_visible_not_false_success():
    c, _ = client(Response({"opportunity": record()}), Response({"opportunity": record(customFields=[])}))
    with pytest.raises(APIError, match="export_readback_mismatch"):
        c.update_opportunity_fields("opp", payload(), before=record())


@pytest.mark.parametrize("bad", [
    {"status": "won"}, {"customFields": []},
    {"customFields": [{"id": "f", "fieldValue": "x", "extra": 1}] * 5},
    {"customFields": [{"id": "f", "fieldValue": 5}] * 5},
    {"customFields": [{"id": "f", "fieldValue": "x"}] * 5},
])
def test_unsafe_export_payloads_never_reach_network(bad):
    c, s = client()
    with pytest.raises(RuleError):
        c.update_opportunity_fields("opp", bad)
    assert not s.calls


@pytest.mark.parametrize("token", [None, "", "hello" + chr(10) + "world"])
def test_bad_tokens_rejected(token):
    with pytest.raises(RuleError):
        HighLevelClient(token, "loc", session=Session())


def test_unknown_api_path_rejected():
    c, s = client()
    with pytest.raises(RuleError):
        c._request("GET", "https://elsewhere.test/")
    assert not s.calls


def test_pipeline_read_uses_location_parameter():
    c, s = client(Response({"pipelines": [{"id": "pipeline", "stages": [{"id": "qualified"}]}]}))
    assert c.get_pipelines()[0]["id"] == "pipeline"
    assert s.calls[0][2]["params"] == {"locationId": "loc"}
    assert s.calls[0][0] == "GET"


def test_opportunity_field_metadata_is_scoped_and_read_only():
    c, s = client(Response({"customFields": [{"id": "field", "model": "opportunity", "dataType": "TEXT"}]}))
    assert c.get_opportunity_fields()[0]["id"] == "field"
    assert s.calls[0][1] == API_BASE + "/locations/loc/customFields"
    assert s.calls[0][2]["params"] == {"model": "opportunity"}


@pytest.mark.parametrize("endpoint", ["pipelines", "fields"])
def test_wrong_location_metadata_rejected(endpoint):
    response = {"pipelines": [{"id": "p", "locationId": "other"}]} if endpoint == "pipelines" else {
        "customFields": [{"id": "f", "locationId": "other"}]}
    c, _ = client(Response(response))
    with pytest.raises(RuleError, match="location_mismatch"):
        (c.get_pipelines if endpoint == "pipelines" else c.get_opportunity_fields)()


def test_export_preserves_unowned_custom_fields_without_sending_them():
    other = {"id": "unrelated", "fieldValue": "synthetic-unchanged"}
    before = record(name="Synthetic deal", status="open", customFields=[other])
    data = payload()
    after = record(name="Synthetic deal", status="open", customFields=[other] + data["customFields"])
    c, s = client(Response({"opportunity": after}), Response({"opportunity": after}))
    c.update_opportunity_fields("opp", data, before=before)
    assert s.calls[0][2]["json"] == data


@pytest.mark.parametrize("change,code", [("unrelated", "unrelated_custom_fields_changed"), ("native", "unowned_opportunity_fields_changed")])
def test_export_detects_destructive_partial_update(change, code):
    before = record(name="Synthetic", customFields=[{"id": "other", "fieldValue": "untouched"}])
    after = record(name="Synthetic" if change == "unrelated" else "changed", customFields=payload()["customFields"])
    if change == "native": after["customFields"].append({"id": "other", "fieldValue": "untouched"})
    c, _ = client(Response({"opportunity": after}), Response({"opportunity": after}))
    with pytest.raises(APIError, match=code):
        c.update_opportunity_fields("opp", payload(), before=before)


def test_export_without_caller_snapshot_reads_before_put():
    before = record(customFields=[])
    after = record(**payload())
    c, s = client(Response({"opportunity": before}), Response({"opportunity": after}), Response({"opportunity": after}))
    c.update_opportunity_fields("opp", payload())
    assert [call[0] for call in s.calls] == ["GET", "PUT", "GET"]


def test_arbitrary_location_write_never_reaches_network():
    c, s = client()
    with pytest.raises(RuleError, match="invalid_api_method"):
        c._request("PUT", "/locations/loc/customFields")
    assert not s.calls
