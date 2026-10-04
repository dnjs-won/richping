"""Offline contract tests. No provider/network calls in pytest."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from unittest.mock import patch

import pytest

from scripts.h0001_alpaca_admission import (Client, ProviderFailure, action_pages,
    credentials, grid, paginate, validate_bar)
from scripts.h0001_long_history_audit import write_new
from scripts.h0001_alpaca_offline_admission import compare_units, prove
from richping.research_v2.real_data import expected_slots, request


def row(t="2025-03-10T08:00:00Z", v=100):
    return {"t": t, "o": 100, "h": 101, "l": 99, "c": 100, "v": v, "n": 1, "vw": 100}


PARAMS = {"feed": "sip", "sort": "asc", "start": "2025-03-10T08:00:00Z",
          "end": "2025-03-11T00:00:00Z", "adjustment": "raw", "limit": 7}


def page(rows, token=None):
    return {"symbol": "SOXX", "bars": rows, "next_page_token": token}


def test_credentials_file_and_runtime_priority_without_disclosure(tmp_path):
    path = tmp_path / ".env.local"
    path.write_text('\ufeffAPCA_API_KEY_ID="file-key"\nAPCA_API_SECRET_KEY=secret-value\nUNRELATED_SECRET=ignored', encoding="utf-8")
    values = credentials(path, {"APCA_API_KEY_ID": "runtime-key"})
    assert values == {"APCA-API-KEY-ID": "runtime-key", "APCA-API-SECRET-KEY": "secret-value"}
    with pytest.raises(ValueError, match="Both named"):
        credentials(tmp_path / "absent", {})


def test_pagination_follows_token_even_when_page_short():
    calls = []
    def fetch(params):
        calls.append(dict(params))
        return page([row()], "next") if len(calls) == 1 else page([row("2025-03-10T08:15:00Z")])
    result = paginate(fetch, PARAMS)
    assert result["pages"] == 2 and len(result["rows"]) == 2
    assert calls[1] == {**PARAMS, "page_token": "next"}


@pytest.mark.parametrize("bad", ["duplicate", "cycle", "empty_nonterminal", "no_marker", "wrong_symbol", "error", "outside"])
def test_pagination_failure_never_success_or_empty_market(bad):
    calls = 0
    def fetch(params):
        nonlocal calls
        calls += 1
        if calls == 1:
            return page([row()], "next")
        if bad == "duplicate": return page([row()])
        if bad == "cycle": return page([row("2025-03-10T08:15:00Z")], "next")
        if bad == "empty_nonterminal": return page([], "other")
        if bad == "no_marker": return {"bars": [], "symbol": "SOXX"}
        if bad == "wrong_symbol": return {**page([]), "symbol": "IEX"}
        if bad == "error": return {**page([]), "code": 403}
        return page([row("2025-03-12T08:00:00Z")])
    with pytest.raises(ProviderFailure):
        paginate(fetch, PARAMS)


def test_iex_is_not_sip():
    with pytest.raises(ValueError, match="Explicit SIP"):
        paginate(lambda p: page([]), {**PARAMS, "feed": "iex"})


def test_empty_terminal_is_valid_query_but_not_admission():
    assert paginate(lambda p: page([]), PARAMS)["rows"] == []
    assert grid([], "2025-03-10", "2025-03-11")["missing_count"] == 64


@pytest.mark.parametrize("bad", [None, -1, float("nan"), True])
def test_volume_null_invalid_is_not_zero(bad):
    with pytest.raises(ProviderFailure): validate_bar(row(v=bad))


def test_zero_volume_missing_and_dst_are_separate():
    for day, end, anchor in (("2025-03-07", "2025-03-08", "09"), ("2025-03-10", "2025-03-11", "08")):
        slots, _ = expected_slots(request("SOXX", day, end))
        rows = [row(t.isoformat()) for t in slots]
        rows[0]["v"] = 0
        rows.pop()
        report = grid(rows, day, end)
        assert report["first"].split("T")[1].startswith(anchor)
        assert report["missing_count"] == 1 and report["zero_volume_by_segment"]["PREMARKET"] == 1
        assert report["segments"] == {"PREMARKET": 22, "RTH": 26, "AFTER_HOURS": 15}


def test_early_close_keeps_unsupported_and_official_rth_diagnostic():
    report = grid([row("2025-11-28T18:00:00Z")], "2025-11-28", "2025-11-29")
    assert report["expected_supported_slots"] == 0
    assert report["unsupported_sessions"][0]["session"] == "2025-11-28"
    assert report["segments"] == {"AFTER_HOURS": 1}


def test_duplicate_grid_not_repaired():
    with pytest.raises(ProviderFailure, match="Duplicate"):
        grid([row(), row()], "2025-03-10", "2025-03-11")


@pytest.mark.parametrize("status", [401, 403, 429, 500])
def test_actual_client_http_error_is_evidenced_and_not_empty(tmp_path, status):
    class Response:
        status_code = status
        content = b'{"message":"failure"}'
    client = Client(tmp_path, {"APCA-API-KEY-ID": "example-key", "APCA-API-SECRET-KEY": "example-secret"})
    with patch("curl_cffi.requests.get", return_value=Response()):
        with pytest.raises(ProviderFailure, match="HTTP"):
            client.bars("failed", PARAMS["start"], PARAMS["end"])
    assert client.records[0]["http_status"] == status
    assert "example-key" not in json.dumps(client.records)


def test_transport_exception_message_is_not_persisted(tmp_path):
    client = Client(tmp_path, {"APCA-API-KEY-ID": "private-key", "APCA-API-SECRET-KEY": "private-secret"})
    with patch("curl_cffi.requests.get", side_effect=RuntimeError("private-secret")):
        with pytest.raises(ProviderFailure, match="Transport"):
            client.bars("transport", PARAMS["start"], PARAMS["end"])
    assert "private-secret" not in json.dumps(client.records)
    assert not list(tmp_path.rglob("*.json"))


def test_echoed_credential_response_never_archived(tmp_path):
    class Response:
        status_code = 200
        content = b'{"message":"private-secret"}'
    client = Client(tmp_path, {"APCA-API-KEY-ID": "private-key", "APCA-API-SECRET-KEY": "private-secret"})
    with patch("curl_cffi.requests.get", return_value=Response()):
        with pytest.raises(ProviderFailure, match="not persisted"):
            client.bars("echo", PARAMS["start"], PARAMS["end"])
    assert not list(tmp_path.rglob("*.json"))


def test_action_pagination_does_not_skip_short_pages():
    class Actions:
        def __init__(self): self.calls = []
        def get(self, identity, endpoint, params):
            self.calls.append(params)
            return {"corporate_actions": {"forward_splits": [{"symbol": "SOXX", "id": str(len(self.calls))}]},
                    "next_page_token": "next" if len(self.calls) == 1 else None}
    client = Actions()
    result = action_pages(client)
    assert result["pages"] == 2 and len(result["corporate_actions"]["forward_splits"]) == 2
    assert client.calls[1]["page_token"] == "next"


def test_immutable_offline_reload_and_collision(tmp_path):
    payload = page([row()])
    body = json.dumps(payload, sort_keys=True).encode()
    path = tmp_path / "response.json"
    write_new(path, body)
    write_new(path, body)
    first = paginate(lambda p: json.loads(path.read_bytes()), PARAMS)
    assert first == paginate(lambda p: json.loads(path.read_bytes()), PARAMS)
    with pytest.raises(ValueError, match="collision"): write_new(path, b"changed")
    assert path.read_bytes() == body


def test_split_unit_effective_date_uses_et_including_afterhours_utc_next_day():
    raw = [row("2024-03-07T00:45:00Z", 100), row("2024-03-07T09:00:00Z", 100)]
    adjusted = deepcopy(raw)
    for key in ("o", "h", "l", "c"): adjusted[0][key] /= 3
    adjusted[0]["v"] *= 3
    result = compare_units(raw, adjusted)
    assert result["result"] == "PASS" and result["before_split_rows"] == 1
    adjusted[0]["v"] = 100
    assert compare_units(raw, adjusted)["result"] == "FAIL"


def test_real_archived_probe_offline_hash_reload_without_candidate_or_network():
    with patch("socket.socket.connect", side_effect=AssertionError("network")), patch("curl_cffi.requests.get", side_effect=AssertionError("network")):
        first = prove()
        assert first == prove()
    assert first["status"] == "BLOCKED"
    assert first["capture"]["dataset_id"] is None
    assert first["candidate_count"] is None and first["outcome_queries"] == 0
    assert first["action_pagination_repeat_equal"] is True
    assert first["volume"]["missing_1945_ET_slot_actual_trades"] == 45
