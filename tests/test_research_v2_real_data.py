"""Mock provider quotes test contracts only; no market-performance evidence."""

from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
import json
import socket
import sqlite3
import sys

import pytest

from richping.cli import main
from richping.core import digest
from richping.research_v2.contracts import JsonObject
from richping.research_v2.data_cli import offline_proof
from richping.research_v2.dummy import RecorderStrategy
from richping.research_v2.features import EMASpec, ema
from richping.research_v2.contracts import ReplayContext
from richping.research_v2.market_data import MarketDataset
from richping.research_v2.real_data import (
    ADAPTER, PROVIDER, archive_capture, coverage, expected_slots, fetch_capture,
    incremental_request, new_vintage, normalize_capture, request, write_coverage,
)
from richping.research_v2.replay import replay
from richping.research_v2.sessions import EXTENDED_CONTINUITY
from richping.research_v2.store import ResearchStore


def capture(start="2024-03-11", end="2024-03-12", captured_at="2024-04-01T12:00:00Z"):
    req = request("SOXX", start, end)
    slots, _ = expected_slots(req)
    return {"provider": PROVIDER, "adapter_version": ADAPTER, "provider_version": "fixture-v1",
            "captured_at": captured_at, "request": req, "response": {"chart": {"error": None,
            "result": [{"meta": {"symbol": "SOXX", "dataGranularity": "15m",
                                   "exchangeTimezoneName": "America/New_York",
                                   "currency": "USD", "instrumentType": "ETF"},
                        "timestamp": [int(v.timestamp()) for v in slots],
                        "events": {"dividends": {"1710163800": {"amount": 0.2, "date": 1710163800}}},
                        "indicators": {"quote": [{"open": [100.] * len(slots),
                            "high": [102.] * len(slots), "low": [99.] * len(slots),
                            "close": [101.] * len(slots), "volume": [0.] * len(slots)}]}}]}}}


def result(c):
    return c["response"]["chart"]["result"][0]


def remove(c, indices):
    r = result(c)
    r["timestamp"] = [v for i, v in enumerate(r["timestamp"]) if i not in indices]
    for k, values in r["indicators"]["quote"][0].items():
        r["indicators"]["quote"][0][k] = [v for i, v in enumerate(values) if i not in indices]


def data(c=None, label="real-fixture-v1"):
    return normalize_capture(c or capture(), label)


def test_response_normalization_provenance_and_no_dividend_rewrite():
    c = capture()
    d = data(c)
    report = coverage(d)
    assert len(d.bars) == 64 and not d.gaps
    assert (report["premarket_count"], report["rth_count"], report["after_hours_count"]) == (22, 26, 16)
    assert report["expected_15m_bars"] == 64 and report["missing_bars"] == 0
    assert d.bars[0].known_at == d.bars[0].end_at
    assert all(b.corporate_action == "UNKNOWN" for b in d.bars)
    assert all(b.close == 101 for b in d.bars)  # dividend kept as event, not adjusted into prices
    assert report["corporate_action_events"] == result(c)["events"]
    assert report["raw_capture_hash"] == digest(c)
    assert report["zero_volume_by_segment"] == {"PREMARKET": 22, "RTH": 26, "AFTER_HOURS": 16}


@pytest.mark.parametrize("key,value", [("open", 0), ("high", 99), ("low", 102),
    ("close", float("nan")), ("close", None), ("volume", -1), ("volume", None),
    ("volume", float("inf")), ("volume", True)])
def test_malformed_provider_bar_fails_closed(key, value):
    c = capture()
    result(c)["indicators"]["quote"][0][key][5] = value
    with pytest.raises(ValueError):
        data(c)


@pytest.mark.parametrize("mutation,reason", [("duplicate", "Duplicate"), ("reverse", "ordering"),
    ("unaligned", "Unaligned"), ("before04", "outside extended"),
    ("after20", "outside extended"), ("partial", "partial OHLCV"),
    ("error", "failure"), ("empty", "partial"), ("multiple", "partial")])
def test_response_failure_modes(mutation, reason):
    c = capture()
    r = result(c)
    if mutation == "duplicate":
        r["timestamp"][1] = r["timestamp"][0]
    elif mutation == "reverse":
        r["timestamp"][0], r["timestamp"][1] = r["timestamp"][1], r["timestamp"][0]
    elif mutation == "unaligned":
        r["timestamp"][5] += 60
    elif mutation == "before04":
        r["timestamp"][0] -= 900
    elif mutation == "after20":
        r["timestamp"][-1] += 900
    elif mutation == "partial":
        r["indicators"]["quote"][0]["volume"].pop()
    elif mutation == "error":
        c["response"]["chart"]["error"] = {"code": "Not Found"}
    elif mutation == "empty":
        c["response"]["chart"]["result"] = []
    else:
        c["response"]["chart"]["result"].append(deepcopy(r))
    with pytest.raises(ValueError, match=reason):
        data(c)


@pytest.mark.parametrize("key,value", [("symbol", "SPY"), ("dataGranularity", "30m"),
    ("exchangeTimezoneName", "UTC"), ("currency", "EUR"), ("instrumentType", "CRYPTO")])
def test_provider_metadata_rejected(key, value):
    c = capture()
    result(c)["meta"][key] = value
    with pytest.raises(ValueError, match="Unexpected provider"):
        data(c)


@pytest.mark.parametrize("key,value", [("provider", "other"), ("price_basis", "raw"),
    ("quality", "SYNTHETIC"), ("known_at_policy", "actual_live"),
    ("provider_version", "different")])
def test_mixed_bar_provenance_rejected(key, value):
    d = data()
    b = d.bars[0]
    b = replace(b, provenance=JsonObject.of({**b.provenance.unpack(), key: value}))
    with pytest.raises(ValueError, match="provenance"):
        replace(d, bars=(b, *d.bars[1:]))


def test_real_contract_cannot_claim_pit_or_confirmed_actions():
    d = data()
    with pytest.raises(ValueError, match="UNKNOWN"):
        replace(d, bars=(replace(d.bars[0], corporate_action="NONE_CONFIRMED"), *d.bars[1:]))
    with pytest.raises(ValueError, match="real dataset provenance"):
        meta = d.manifest.unpack()
        del meta["raw_capture_hash"]
        replace(d, manifest=JsonObject.of(meta))
    with pytest.raises(ValueError, match="coverage manifest"):
        replace(d, manifest=JsonObject.of({**d.manifest.unpack(), "missing_slots": ["fabricated"]}))


def test_gap_reporting_includes_edges_entire_day_and_blocks_replay_before_callback(tmp_path):
    c = capture("2024-03-11", "2024-03-14")
    remove(c, {0, 1, 63, *range(64, 128), 191})
    d = data(c)
    report = coverage(d)
    assert report["expected_15m_bars"] == 192
    assert report["missing_bars"] == 68 and len(d.gaps) == 68
    assert report["gap_count"] == 4
    assert report["missing_status"] == "UNKNOWN/UNAVAILABLE"
    assert report["coverage_status"] == "UNAVAILABLE"
    with ResearchStore(tmp_path / "market.sqlite") as store:
        store.save_dataset(d)  # diagnostic quarantine may be retained, never replayed
        assert store.load_dataset(d.dataset_id) == d
    class CannotInitialize(RecorderStrategy):
        def initialize(self, context):
            pytest.fail("Incomplete real coverage must fail before strategy callback")
    with pytest.raises(ValueError, match="replay refused"):
        replay(d, CannotInitialize())
    with pytest.raises(ValueError, match="iteration refused"):
        offline_proof(d)


def test_extended_early_close_reports_and_does_not_skip():
    c = capture("2024-11-27", "2024-12-03", "2024-12-04T12:00:00Z")
    _, unsupported = expected_slots(c["request"])
    assert unsupported[0]["session"] == "2024-11-29"
    with pytest.raises(ValueError, match="early-close"):
        data(c)


def test_roundtrip_deterministic_hash_and_immutable_collision(tmp_path):
    d = data()
    path = tmp_path / "market.sqlite"
    with ResearchStore(path) as store:
        store.save_dataset(d)
        store.save_dataset(d)
        assert store.load_dataset(d.dataset_id) == d
        altered = replace(d, bars=(replace(d.bars[0], close=100.5), *d.bars[1:]))
        with pytest.raises(ValueError, match="collision"):
            store.save_dataset(altered)
        assert store.load_dataset(d.dataset_id).content_hash == d.content_hash
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            store.db.execute("UPDATE v2_bars SET body='{}'")
    original = path.read_bytes()
    with ResearchStore(path, read_only=True) as store:
        assert store.load_dataset(d.dataset_id) == d
        assert store.list_datasets()[0]["dataset_id"] == d.dataset_id
    assert path.read_bytes() == original


def test_offline_reload_and_replay_identity_network_disabled(tmp_path, monkeypatch):
    d = data()
    expected = offline_proof(d)
    path = tmp_path / "market.sqlite"
    with ResearchStore(path) as store:
        store.save_dataset(d)
    def no_network(*args, **kwargs):
        pytest.fail("Offline inspection/replay attempted network")
    monkeypatch.setattr(socket, "socket", no_network)
    monkeypatch.setattr("richping.research_v2.real_data.fetch_capture", no_network)
    monkeypatch.setattr("richping.research_v2.data_cli.fetch_capture", no_network)
    with ResearchStore(path, read_only=True) as store:
        loaded = store.load_dataset(d.dataset_id)
        assert offline_proof(loaded) == expected
        a, b = replay(d, RecorderStrategy()), replay(loaded, RecorderStrategy())
        assert a == b and a.hash == b.hash
        assert a.summary.unpack()["evidence"] == "REAL_HISTORICAL_SNAPSHOT_RESEARCH_NOT_PIT"
        derived = a.traces[-1].event.completed[-1]
        assert derived.corporate_action == "UNKNOWN"
    assert expected["completed_bars"] == {"15m": 64, "1H": 16, "Daily": 1}
    assert main(["research-v2-data", "--store", str(path), "proof", d.dataset_id]) == 0


def test_snapshot_feature_preserves_unknown_policy_and_synthetic_unknown_still_rejected():
    from test_research_v2 import fixture_data
    d = data()
    context = ReplayContext(d.bars[-1].known_at, d.bars)
    output = ema(context, "SOXX", "15m", EMASpec(3, 3, continuity=EXTENDED_CONTINUITY))
    assert output.status == "READY"
    b = replace(fixture_data(count=1).bars[0], corporate_action="UNKNOWN")
    with pytest.raises(ValueError, match="corporate action"):
        ema(ReplayContext(b.known_at, (b,)), b.symbol, "15m", EMASpec(3, 1))


def test_incremental_refresh_revisions_and_old_vintage_unchanged(tmp_path):
    parent = data(capture("2024-03-11", "2024-03-13"))
    req = incremental_request(parent, "2024-03-14", overlap_days=1)
    assert req["start"] == "2024-03-12"
    c = capture(req["start"], req["end"], "2024-04-02T12:00:00Z")
    result(c)["indicators"]["quote"][0]["close"][0] = 100.5
    incoming = data(c, "refresh-capture")
    old_hash = parent.content_hash
    child = new_vintage(parent, incoming, "real-v2")
    assert len(child.bars) == 192
    revisions = child.manifest.unpack()["incremental"]
    assert revisions["revised_slots"] == [parent.bars[64].start_at.isoformat()]
    assert revisions["parent_content_hash"] == old_hash
    assert child.bars[0].provenance == parent.bars[0].provenance
    assert child.bars[64].close == 100.5 and parent.bars[64].close == 101
    assert parent.content_hash == old_hash
    with ResearchStore(tmp_path / "market.sqlite") as store:
        store.save_dataset(parent)
        store.save_dataset(child)
        assert store.load_dataset(parent.dataset_id).content_hash == old_hash
        assert store.load_dataset(child.dataset_id) == child
    assert new_vintage(parent, incoming, "real-v2") == child
    with pytest.raises(ValueError, match="new dataset identity"):
        new_vintage(parent, incoming, parent.dataset_id)


def test_overlap_deletion_does_not_silently_keep_old_bar():
    parent = data(capture("2024-03-11", "2024-03-13"))
    c = capture("2024-03-12", "2024-03-14")
    remove(c, {0})
    child = new_vintage(parent, data(c, "fresh"), "child")
    assert len(child.bars) == 191
    assert coverage(child)["missing_bars"] == 1
    assert child.manifest.unpack()["incremental"]["deleted_slots"] == [parent.bars[64].start_at.isoformat()]
    assert len(parent.bars) == 128


def test_incremental_split_mixed_version_shrink_and_no_overlap_rejected():
    parent = data(capture("2024-03-11", "2024-03-13"))
    c = capture("2024-03-12", "2024-03-14")
    result(c)["events"]["splits"] = {"1710250200": {"numerator": 2, "denominator": 1}}
    with pytest.raises(ValueError, match="full recapture"):
        new_vintage(parent, data(c, "incoming"), "child")
    c = capture("2024-03-12", "2024-03-14")
    c["provider_version"] = "fixture-v2"
    with pytest.raises(ValueError, match="full recapture"):
        new_vintage(parent, data(c, "incoming"), "child")
    with pytest.raises(ValueError, match="shrink"):
        incremental_request(parent, "2024-03-12")
    with pytest.raises(ValueError, match="overlap"):
        new_vintage(parent, data(capture("2024-03-13", "2024-03-14"), "incoming"), "child")


def test_http_failure_no_implicit_retry(monkeypatch):
    from yfinance.data import YfData
    class Failure:
        status_code = 429
    calls = []
    def failed(self, **kwargs):
        calls.append(kwargs)
        return Failure()
    monkeypatch.setattr(YfData, "get", failed)
    with pytest.raises(ValueError, match="HTTP failure: 429"):
        fetch_capture(request("SOXX", "2024-03-11", "2024-03-12"))
    assert len(calls) == 1 and calls[0]["params"]["includePrePost"] is True


def test_offline_import_inspect_and_coverage_artifacts(tmp_path, capsys):
    c = capture()
    raw = archive_capture(c, tmp_path)
    assert archive_capture(c, tmp_path) == raw
    db = tmp_path / "market.sqlite"
    prefix = ["research-v2-data", "--store", str(db), "--output-dir", str(tmp_path)]
    assert main([*prefix, "import", str(raw), "--dataset-id", "saved"]) == 0
    assert json.loads(capsys.readouterr().out)["observed_bars"] == 64
    assert main([*prefix, "inspect", "saved"]) == 0
    assert json.loads(capsys.readouterr().out)["coverage_status"] == "COMPLETE_GRID"
    assert main([*prefix, "list"]) == 0
    assert json.loads(capsys.readouterr().out)[0]["dataset_id"] == "saved"
    assert (tmp_path / "saved.coverage.json").exists()
    assert (tmp_path / "saved.coverage.md").exists()
    assert main([*prefix, "import", str(raw), "--dataset-id", "../bad"]) == 1


def test_failed_import_preserves_raw_diagnostics_and_no_dataset(tmp_path):
    c = capture("2024-11-27", "2024-12-03", "2024-12-04T12:00:00Z")
    raw = archive_capture(c, tmp_path)
    db = tmp_path / "market.sqlite"
    assert main(["research-v2-data", "--store", str(db), "--output-dir", str(tmp_path),
                 "import", str(raw)]) == 1
    assert not db.exists()
    failures = list(tmp_path.glob("*.failure.json"))
    assert len(failures) == 1
    report = json.loads(failures[0].read_text())
    assert report["unsupported_sessions"][0]["session"] == "2024-11-29"
    assert report["status"] == "REJECTED_NOT_REPLAYABLE"
