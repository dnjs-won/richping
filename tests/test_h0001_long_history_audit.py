"""Deterministic diagnostics; no live provider request in these tests."""

from copy import deepcopy
import json

import pytest

from scripts.h0001_long_history_audit import credential_inventory, grid_diagnostic, write_new
from richping.research_v2.real_data import expected_slots, request


def fixture(start="2026-10-01", end="2026-10-02"):
    req = request("SOXX", start, end)
    slots, _ = expected_slots(req)
    times = [int(s.timestamp()) for s in slots]
    return {"request": req, "captured_at": "2026-10-03T12:00:00+00:00",
            "response": {"chart": {"result": [{"timestamp": times,
                 "indicators": {"quote": [{k: [100] * len(times)
                   for k in ("open", "high", "low", "close", "volume")} ]}}], "error": None}}}


def quote(c):
    return c["response"]["chart"]["result"][0]["indicators"]["quote"][0]


def test_zero_volume_present_bar_is_not_missing_or_no_trade():
    c = fixture()
    quote(c)["volume"][0] = 0
    report = grid_diagnostic(c)
    assert report["expected_slots"] == report["observed_rows"] == 64
    assert report["missing_count"] == 0
    assert report["zero_volume_by_segment"] == {"PREMARKET": 1}
    assert report["segments"] == {"PREMARKET": 22, "RTH": 26, "AFTER_HOURS": 16}
    assert report["status"] == "COMPLETE_GRID_ONLY_NOT_ADMISSION"
    assert "NOT_PROOF_OF_NO_TRADING" in report["zero_volume_interpretation"]


def test_missing_bar_does_not_become_zero_volume_or_market_closed():
    c = fixture()
    c["response"]["chart"]["result"][0]["timestamp"].pop(0)
    for values in quote(c).values():
        values.pop(0)
    r = grid_diagnostic(c)
    assert r["status"] == "UNAVAILABLE"
    assert r["missing_count"] == 1 and r["zero_volume_by_segment"] == {}
    assert r["missing_slots"] == ["2026-10-01T08:00:00+00:00"]
    assert "NOT_ZERO_VOLUME_OR_PROVEN_MARKET_UNAVAILABLE" in r["missing_interpretation"]


@pytest.mark.parametrize("day,end,anchor", [("2025-03-07", "2025-03-08", "09:00:00"),
                                          ("2025-03-10", "2025-03-11", "08:00:00")])
def test_dst_uses_new_york_04_anchor(day, end, anchor):
    r = grid_diagnostic(fixture(day, end))
    assert r["status"] == "COMPLETE_GRID_ONLY_NOT_ADMISSION"
    assert r["first_start"] == day + "T" + anchor + "+00:00"
    assert r["expected_slots"] == 64


def test_early_close_stays_unsupported_without_rth_substitution():
    r = grid_diagnostic(fixture("2025-11-28", "2025-11-29"))
    assert r["status"] == "UNAVAILABLE" and r["expected_slots"] == 0
    assert len(r["unsupported_sessions"]) == 1
    assert r["unsupported_sessions"][0]["session"] == "2025-11-28"


@pytest.mark.parametrize("field,key", [("open", "null_ohlc_rows"), ("volume", "null_volume_rows")])
def test_null_is_neither_zero_nor_valid_grid(field, key):
    c = fixture()
    quote(c)[field][0] = None
    r = grid_diagnostic(c)
    assert r[key] == 1 and r["status"] == "UNAVAILABLE"
    assert r["zero_volume_by_segment"] == {}


def test_duplicate_and_latest_non_grid_point_not_dropped():
    c = fixture()
    times = c["response"]["chart"]["result"][0]["timestamp"]
    times.extend([times[0], times[-1] + 14 * 60 + 54])
    for values in quote(c).values():
        values.extend([100, 100])
    r = grid_diagnostic(c)
    assert r["duplicates"] == 1 and r["outside_supported_grid"] == 1
    assert r["observed_rows"] == 66 and r["status"] == "UNAVAILABLE"


def test_incomplete_bar_cannot_pass():
    c = fixture()
    c["captured_at"] = "2026-10-01T23:59:59+00:00"
    r = grid_diagnostic(c)
    assert r["incomplete_rows"] == 1 and r["status"] == "UNAVAILABLE"


def test_provider_error_is_not_missing_grid_or_capability_absence():
    c = fixture()
    c["response"] = {"chart": {"result": None, "error": {"code": "rate-limit"}}}
    r = grid_diagnostic(c)
    assert r["status"] == "PROVIDER_ERROR_NOT_GRID_EVIDENCE"
    assert "missing_count" not in r


def test_malformed_arrays_are_not_partial_success():
    c = fixture()
    quote(c)["close"].pop()
    assert grid_diagnostic(c) == {"status": "MALFORMED_ARRAYS"}


def test_credential_inventory_never_contains_values():
    r = credential_inventory({"APCA_API_KEY_ID": "sensitive-example", "UNRELATED_SECRET": "do-not-read"})
    assert r["alpaca"]["APCA_API_KEY_ID"] is True
    assert r["alpaca"]["APCA_API_SECRET_KEY"] is False
    assert "sensitive" not in json.dumps(r) and "UNRELATED" not in json.dumps(r)


def test_evidence_collision_preserves_original_bytes(tmp_path):
    p = tmp_path / "raw" / "capture.bin"
    write_new(p, b"original")
    write_new(p, b"original")
    with pytest.raises(ValueError, match="collision"):
        write_new(p, b"revised")
    assert p.read_bytes() == b"original"
