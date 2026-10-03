"""Causal Daily mechanics: fixtures are never actual provider/PIT evidence."""

from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
import json
from pathlib import Path
import socket

import pytest

from richping.cli import main
from richping.core import canonical, close_at, digest, sessions, timestamp
from richping.research_v2.contracts import JsonObject, MarketBar, payload
from richping.research_v2.daily_data import (
    BAR_CLOCK, DailyVintage, daily_request, warmup_request, normalize_daily,
    save_daily, load_daily, validate_actions,
)
from richping.research_v2.strategy.daily_input import expected_daily_session, prepare_daily
from richping.research_v2.strategy.daily_proof import readiness_proof, price_only_diagnostic
from richping.research_v2.strategy.mixed_profile import join_as_of, atomic_intraday_batches
from richping.research_v2.sessions import RTH, session_bounds
from richping.research_v2.strategy.daily_trend import classify_daily_trend
from richping.research_v2.strategy.daily_exhaustion import classify_daily_exhaustion
from test_research_v2_real_data import capture as intraday_capture, data as intraday_data


def fixture(ending="2024-03-11", count=400, *, as_ofs=()):
    days = sessions("2022-01-03", ending)[-count:]
    instants = sorted({close_at(s) for s in days} | {timestamp(t) for t in as_ofs})
    common = {"raw_price_basis": "RAW_UNADJUSTED_RTH_OHLC", "raw_capture_hash": "a"*64,
              "known_at_policy": "FIXTURE_BAR_CLOCK", "session_profile": RTH}
    bars = tuple(MarketBar("daily-fixture-v1", "SOXX", "Daily", *session_bounds(s), s,
                 100+i, 102+i, 99+i, 101+i, 100, close_at(s), "fixture", JsonObject.of(common), "UNKNOWN")
                 for i, s in enumerate(days))
    captured = max(instants+[bars[-1].known_at])+timedelta(days=1)
    actions = {"schema_version": "split_evidence_v1", "provider": "fixture",
        "source_vintage": "action-fixture-v1", "symbol": "SOXX", "status": "FIXTURE",
        "captured_at": captured.isoformat(), "events": [],
        "coverage": [{"start_at": bars[0].start_at.isoformat(), "through_at": t.isoformat(),
                      "known_at": t.isoformat(), "known_at_semantics": "FIXTURE_SOURCE_CLOCK",
                      "evidence_ref": "fixture-coverage:"+t.isoformat()} for t in instants]}
    return DailyVintage("daily-fixture-v1", bars, JsonObject.of({"schema_version": "rth_daily_vintage_v1",
        **common, "raw_unit_status": "FIXTURE", "provider": "fixture", "captured_at": captured.isoformat(),
        "requested_range": daily_request("SOXX", days[0], (timestamp(ending+"T00:00:00Z")+timedelta(days=1)).date().isoformat()),
        "missing_sessions": []}), JsonObject.of(actions))


def split(vintage, *, effective=None, known=None, old=1, new=3, revision="r1"):
    effective = effective or vintage.bars[-1].start_at
    known = known or effective
    return {"event_id": "split-1", "revision_id": revision, "symbol": "SOXX",
        "type": "forward_split" if new > old else "reverse_split", "effective_at": timestamp(effective).isoformat(),
        "known_at": timestamp(known).isoformat(), "known_at_semantics": "FIXTURE_SOURCE_CLOCK",
        "old_shares": old, "new_shares": new, "factor_units": "NEW_SHARES_PER_OLD_SHARES",
        "source_fields": {"fixture_receipt": timestamp(known).isoformat()}}


def with_actions(v, events):
    return replace(v, actions=JsonObject.of({**v.actions.unpack(), "events": events}))


def provider_capture(count=500):
    f = fixture(ending="2024-11-29", count=count)
    req = f.manifest.unpack()["requested_range"]
    return {"provider": "yahoo_chart", "adapter_version": "yahoo_chart_rth_daily_v1", "provider_version": "fixture-version",
        "request": req, "captured_at": "2024-12-02T22:00:00Z", "response": {"chart": {"error": None, "result": [{
        "meta": {"symbol": "SOXX", "dataGranularity": "1d", "exchangeTimezoneName": "America/New_York",
                 "instrumentType": "ETF", "currency": "USD"}, "timestamp": [int(b.start_at.timestamp()) for b in f.bars],
        "events": {}, "indicators": {"quote": [{k: [getattr(b, k) for b in f.bars]
                                                 for k in ("open", "high", "low", "close", "volume")}]}}]}}}


def test_multiyear_ingestion_and_immutable_roundtrip(tmp_path):
    c = provider_capture()
    v = normalize_daily(c, "daily-real-fixture-v1")
    assert len(v.bars) == 500 and not v.manifest.unpack()["missing_sessions"]
    assert v.bars[-1].end_at == timestamp("2024-11-29T18:00:00Z")
    save_daily(v, tmp_path)
    restored = load_daily(v.dataset_id, tmp_path)
    assert restored == v and restored.content_hash == v.content_hash
    assert save_daily(restored, tmp_path).exists()
    changed = replace(v, actions=JsonObject.of({**v.actions.unpack(), "limitations": ["revised"]}))
    with pytest.raises(ValueError, match="collision"):
        save_daily(changed, tmp_path)


@pytest.mark.parametrize("defect", ["duplicate", "reverse", "timezone", "partial", "out_of_range", "array", "error", "granularity"])
def test_daily_capture_defects_fail_closed(defect):
    c = provider_capture(10)
    r = c["response"]["chart"]["result"][0]
    if defect == "duplicate":
        r["timestamp"][1] = r["timestamp"][0]
    elif defect == "reverse":
        r["timestamp"][0], r["timestamp"][1] = r["timestamp"][1], r["timestamp"][0]
    elif defect == "timezone":
        r["meta"]["exchangeTimezoneName"] = "UTC"
    elif defect == "partial":
        c["captured_at"] = "2024-11-29T17:59:59Z"
    elif defect == "out_of_range":
        c["request"]["end"] = "2024-11-29"
    elif defect == "array":
        r["indicators"]["quote"][0]["close"].pop()
    elif defect == "error":
        c["response"]["chart"]["error"] = {"code": "Bad"}
    else:
        r["meta"]["dataGranularity"] = "15m"
    with pytest.raises(ValueError):
        normalize_daily(c, "bad")


@pytest.mark.parametrize("field,value", [("open", None), ("high", 1), ("low", -1), ("close", float("nan")),
    ("close", float("inf")), ("close", True), ("volume", -1)])
def test_daily_OHLC_validation(field, value):
    c = provider_capture(10)
    c["response"]["chart"]["result"][0]["indicators"]["quote"][0][field][1] = value
    with pytest.raises(ValueError):
        normalize_daily(c, "bad")


def test_missing_internal_session_never_fills():
    v = fixture(count=400)
    missing = v.bars[20].session
    v = replace(v, bars=v.bars[:20]+v.bars[21:],
                manifest=JsonObject.of({**v.manifest.unpack(), "missing_sessions": [missing]}))
    result = prepare_daily(v, v.bars[-1].known_at)
    assert result.prefix.input_reason == "missing_Daily_session_in_required_prefix"
    assert result.prefix.bars == ()


def test_no_action_is_versioned_identity_not_raw_fallback():
    v = fixture()
    r = prepare_daily(v, v.bars[-1].known_at)
    assert r.prefix.input_status == "READY"
    p = r.transform.unpack()
    assert p["result"] == "NO_APPLIED_SPLIT_IN_CAUSAL_PREFIX" and p["applied_actions"] == []
    assert p["factors"] == [1.0]*400 and p["raw_fallback"] is False
    assert p["input_hash"] and p["action_evidence_ref"] and p["transform_version"]
    assert [b.close for b in r.prefix.bars] == [b.close for b in v.bars]


@pytest.mark.parametrize("old,new,factor", [(1, 3, 1/3), (10, 1, 10)])
def test_forward_reverse_split_factor_all_four_fields(old, new, factor):
    v = fixture()
    event = split(v, old=old, new=new)
    r = prepare_daily(with_actions(v, [event]), v.bars[-1].known_at)
    assert r.prefix.input_status == "READY"
    for field in ("open", "high", "low", "close"):
        assert getattr(r.prefix.bars[-2], field) == pytest.approx(getattr(v.bars[-2], field)*factor)
        assert getattr(r.prefix.bars[-1], field) == getattr(v.bars[-1], field)
    assert r.prefix.bars[-2].volume == v.bars[-2].volume


def test_effective_boundary_and_announced_future_split_excluded():
    effective = timestamp("2024-03-11T08:00:00Z")
    before = effective-timedelta(microseconds=1)
    v = fixture(as_ofs=[before, effective])
    event = split(v, effective=effective, known=effective-timedelta(days=2))
    v = with_actions(v, [event])
    assert prepare_daily(v, before).transform.unpack()["applied_actions"] == []
    at = prepare_daily(v, effective)
    assert at.prefix.bars[-1].close == pytest.approx(v.bars[-2].close/3)
    assert len(at.transform.unpack()["applied_actions"]) == 1


def test_effective_but_unknown_fails_and_known_boundary_rebases():
    known = timestamp("2024-03-11T10:02:00Z")
    before = known-timedelta(microseconds=1)
    v = fixture(as_ofs=[before, known])
    v = with_actions(v, [split(v, effective="2024-03-11T08:00:00Z", known=known)])
    assert prepare_daily(v, before).prefix.input_reason == "effective_split_required_evidence_not_yet_known"
    assert prepare_daily(v, known).prefix.input_status == "READY"
    assert prepare_daily(v, known).prefix.transform_known_at == known


def test_snapshot_immutable_and_correction_requires_new_vintage(tmp_path):
    before, later = timestamp("2024-03-11T10:00:00Z"), timestamp("2024-03-11T11:00:00Z")
    v = fixture(as_ofs=[before, later])
    first = split(v, effective="2024-03-11T08:00:00Z", known=before)
    v1 = with_actions(v, [first])
    original = prepare_daily(v1, before)
    snapshot = canonical(payload(original))
    v2 = with_actions(v1, [first, split(v, effective=first["effective_at"], known=later, new=4, revision="r2")])
    assert prepare_daily(v2, before) == original
    assert prepare_daily(v2, later).prefix.bars[-1].close == pytest.approx(v.bars[-2].close/4)
    assert canonical(payload(original)) == snapshot
    save_daily(v1, tmp_path)
    with pytest.raises(ValueError, match="collision"):
        save_daily(v2, tmp_path)
    v2 = replace(v2, dataset_id="daily-fixture-v2", bars=tuple(replace(b, dataset_id="daily-fixture-v2") for b in v2.bars))
    save_daily(v2, tmp_path)
    assert load_daily(v1.dataset_id, tmp_path) == v1 and load_daily(v2.dataset_id, tmp_path) == v2


@pytest.mark.parametrize("defect", ["units", "unknown", "negative", "direction", "missing_ref", "backdate", "future_coverage", "process_date"])
def test_action_import_rejects_false_evidence(defect):
    v = fixture()
    body = v.actions.unpack()
    e = split(v)
    body["events"] = [e]
    if defect == "units":
        e["factor_units"] = "PRICE_MULTIPLIER"
    elif defect == "unknown":
        e["new_shares"] = None
    elif defect == "negative":
        e["old_shares"] = -1
    elif defect == "direction":
        e["type"] = "reverse_split"
    elif defect == "missing_ref":
        e["source_fields"] = {}
    elif defect == "backdate":
        body["status"] = "CROSS_CHECK_ONLY"
        e["known_at_semantics"] = "ACTUAL_CAPTURE_RECEIPT"
    elif defect == "future_coverage":
        body["coverage"][0]["through_at"] = body["captured_at"]
    else:
        e["known_at_semantics"] = "PROVIDER_PROCESS_DATE"
    with pytest.raises(ValueError):
        validate_actions(body)


def test_missing_action_evidence_even_no_splits_never_identity():
    v = fixture()
    v = replace(v, actions=JsonObject.of({**v.actions.unpack(), "coverage": []}))
    assert prepare_daily(v, v.bars[-1].known_at).prefix.input_status == "UNAVAILABLE"
    assert prepare_daily(v, v.bars[-1].known_at).prefix.bars == ()


@pytest.mark.parametrize("as_of,expected", [
    ("2026-10-01T06:00:00-04:00", "2026-09-30"),
    ("2026-10-01T15:59:59-04:00", "2026-09-30"),
    ("2026-10-01T16:00:00-04:00", "2026-10-01"),
    ("2026-10-04T12:00:00-04:00", "2026-10-02"),
    ("2026-09-07T12:00:00-04:00", "2026-09-04"),
    ("2024-11-29T12:59:59-05:00", "2024-11-27"),
    ("2024-11-29T13:00:00-05:00", "2024-11-29"),
])
def test_expected_official_session_boundaries(as_of, expected):
    assert expected_daily_session(as_of) == expected


@pytest.mark.parametrize("as_of", ["1989-12-31T12:00:00Z", "2036-01-01T12:00:00Z"])
def test_unsupported_calendar_fail_closed(as_of):
    with pytest.raises(ValueError):
        expected_daily_session(as_of)
    assert prepare_daily(fixture(), as_of).prefix.input_reason == "unsupported_calendar_date"


@pytest.mark.parametrize("ending,pre,close,later", [
    ("2024-03-11", "2024-03-11T15:59:59-04:00", "2024-03-11T16:00:00-04:00", "2024-03-11T16:02:00-04:00"),
    ("2024-11-29", "2024-11-29T12:59:59-05:00", "2024-11-29T13:00:00-05:00", "2024-11-29T13:02:00-05:00"),
])
def test_delayed_expected_daily_never_carries_old_state(ending, pre, close, later):
    v = fixture(ending, as_ofs=[pre, close, later])
    v = replace(v, bars=(*v.bars[:-1], replace(v.bars[-1], known_at=timestamp(later))))
    before = prepare_daily(v, pre)
    assert before.prefix.input_status == "READY" and before.prefix.bars[-1].session != ending
    at = prepare_daily(v, close)
    assert at.prefix.input_status == "UNAVAILABLE" and at.prefix.bars == ()
    assert classify_daily_trend(at.prefix, close).state == "UNAVAILABLE"
    fresh = prepare_daily(v, later)
    assert fresh.prefix.input_status == "READY" and fresh.prefix.bars[-1].session == ending
    assert classify_daily_trend(fresh.prefix, later).known_at == timestamp(later)


@pytest.mark.parametrize("n,trend,exhaustion", [(178, "UNAVAILABLE", "UNAVAILABLE"), (179, "READY", "UNAVAILABLE"),
    (380, "READY", "UNAVAILABLE"), (381, "READY", "READY")])
def test_frozen_readiness_boundaries(n, trend, exhaustion):
    v = fixture(count=n)
    r = prepare_daily(v, v.bars[-1].known_at)
    assert classify_daily_trend(r.prefix, r.prefix.eligibility_as_of).status == trend
    assert classify_daily_exhaustion(r.prefix, r.prefix.eligibility_as_of).status == exhaustion


def test_premarket_separate_identity_and_deterministic_poll():
    as_of = "2024-03-11T06:00:00-04:00"
    v = fixture(as_ofs=[as_of])
    intraday = intraday_data()
    j = join_as_of(v, intraday, as_of)
    assert j == join_as_of(v, intraday, as_of)
    assert j["expected_Daily_session"] == "2024-03-08" and j["Daily_input_status"] == "READY"
    refs = j["references"]
    assert refs[0]["session_profile"] == RTH and refs[2]["session_profile"] != RTH
    assert refs[2]["source_end_at"] == timestamp(as_of).isoformat()
    assert refs[3]["source_end_at"] == timestamp(as_of).isoformat()
    assert refs[0]["source_end_at"] == timestamp("2024-03-08T16:00:00-05:00").isoformat()
    assert refs[0]["source_vintage"] != refs[2]["source_vintage"]
    assert j["concatenated_stream"] is False and j["ENTRY_CANDIDATE"] is None


def test_mixed_close_delayed_fresh_and_future_known_rejection():
    close, later = "2024-03-11T16:00:00-04:00", "2024-03-11T16:02:00-04:00"
    v = fixture(as_ofs=[close, later])
    v = replace(v, bars=(*v.bars[:-1], replace(v.bars[-1], known_at=timestamp(later))))
    intraday = intraday_data()
    j = join_as_of(v, intraday, close)
    assert j["Daily_input_status"] == "UNAVAILABLE" and j["references"][0]["state"] == "UNAVAILABLE"
    assert join_as_of(v, intraday, later)["Daily_input_status"] == "READY"
    with pytest.raises(ValueError, match="Future"):
        join_as_of(v, intraday, close, published=intraday.bars)
    with pytest.raises(ValueError, match="vintage"):
        join_as_of(v, intraday, close, published=(replace(intraday.bars[0], dataset_id="wrong-vintage"),))


def test_equal_known_batch_publishes_before_join():
    at = timestamp("2024-03-11T10:00:00Z")
    c = intraday_capture()
    intraday = intraday_data(c)
    bars = tuple(replace(b, known_at=at) if b.end_at <= at else b for b in intraday.bars)
    # Actual research snapshot enforces assumed bar-end known_at. Use the
    # established synthetic extended contract for delivery/batch fixture.
    from test_research_v2_extended import dataset, bars as extended_bars
    source = extended_bars(symbols=("SOXX",))
    source = tuple(replace(b, known_at=at) if b.end_at <= at else b for b in source)
    intraday = dataset(source)
    v = fixture(as_ofs=[at])
    v = with_actions(v, [split(v, effective="2024-03-11T08:00:00Z", known=at)])
    batches = list(atomic_intraday_batches(intraday))
    known, visible, completed = batches[0]
    assert known == at and len([b for b in completed if b.timeframe == "15m"]) == 8
    assert len([b for b in visible if b.timeframe == "1H"]) == 2
    # Give synthetic fixture an explicit price identity used by join.
    intraday = replace(intraday, manifest=JsonObject.of({**intraday.manifest.unpack(), "price_basis": "synthetic_unadjusted"}))
    j = join_as_of(v, intraday, at, published=visible)
    assert j["Daily_transform"]["applied_actions"][0]["known_at"] == at.isoformat()
    assert j["references"][2]["source_end_at"] == at.isoformat()


def test_new_daily_intraday_action_same_batch_and_partial_rejected():
    at = timestamp("2024-03-11T16:00:00-04:00")
    v = fixture(as_ofs=[at])
    v = with_actions(v, [split(v, effective="2024-03-11T08:00:00Z", known=at)])
    intraday = intraday_data()
    _, visible, _ = next(batch for batch in atomic_intraday_batches(intraday) if batch[0] == at)
    joined = join_as_of(v, intraday, at, published=visible)
    assert joined["Daily_input_status"] == "READY"
    assert joined["expected_Daily_session"] == "2024-03-11"
    assert all(r["source_known_at"] == at.isoformat() for r in joined["references"])
    with pytest.raises(ValueError, match="Partial"):
        join_as_of(v, intraday, at, published=visible[:-1])


def test_future_action_does_not_change_causal_input_hash():
    v = fixture()
    future = split(v, effective="2024-03-12T08:00:00Z", known=v.bars[-1].known_at)
    as_of = v.bars[-1].known_at
    assert prepare_daily(v, as_of) == prepare_daily(with_actions(v, [future]), as_of)


def test_verified_evidence_capture_time_not_historical_known_at():
    v = normalize_daily(provider_capture(10), "capture-only-v1")
    body = v.actions.unpack()
    captured = timestamp(body["captured_at"])
    body.update(status="VERIFIED", availability_and_completeness_audit_ref="fixture-audit-not-real")
    body["coverage"] = [{"start_at": v.bars[0].start_at.isoformat(), "through_at": captured.isoformat(),
        "known_at": captured.isoformat(), "known_at_semantics": "ACTUAL_CAPTURE_RECEIPT", "evidence_ref": "capture-only"}]
    meta = {**v.manifest.unpack(), "raw_unit_status": "VERIFIED_AS_TRADED", "raw_price_basis": "RAW_UNADJUSTED_RTH_OHLC",
            "unit_audit_ref": "fixture-unit-audit-not-real", "unit_known_at": captured.isoformat()}
    bars = tuple(replace(b, provenance=JsonObject.of({**b.provenance.unpack(), "raw_price_basis": meta["raw_price_basis"]})) for b in v.bars)
    v = replace(v, manifest=JsonObject.of(meta), actions=JsonObject.of(body), bars=bars)
    assert prepare_daily(v, v.bars[-1].known_at).prefix.input_reason == "raw_OHLC_unit_evidence_not_yet_known"


def test_weekend_holiday_freshness_with_causal_coverage():
    for ending, as_of in [("2024-03-08", "2024-03-10T12:00:00-04:00"),
                          ("2024-05-24", "2024-05-27T12:00:00-04:00")]:
        v = fixture(ending=ending, as_ofs=[as_of])
        r = prepare_daily(v, as_of)
        assert r.prefix.input_status == "READY" and r.prefix.expected_session == ending


def test_yahoo_is_not_PIT_even_without_splits_and_numeric_warmup_is_separate():
    v = normalize_daily(provider_capture(), "yahoo-fixture-v1")
    proof = readiness_proof(v)
    assert proof["trend_READY"] == proof["exhaustion_READY"] == proof["joint_READY_count"] == 0
    assert proof["trend_UNAVAILABLE"] == proof["exhaustion_UNAVAILABLE"] == 500
    assert proof["price_only_diagnostic"]["observations_with_joint_numeric_warmup"] == 120
    assert proof["price_only_diagnostic"]["eligible_READY_claim"] is False


def test_offline_cli_and_hash_reproducibility(tmp_path, monkeypatch, capsys):
    v = normalize_daily(provider_capture(10), "daily-offline-v1")
    save_daily(v, tmp_path)
    def forbidden(*args, **kwargs):
        raise AssertionError("Network/provider forbidden")
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr("richping.research_v2.daily_data.fetch_daily", forbidden)
    assert load_daily(v.dataset_id, tmp_path).content_hash == v.content_hash
    args = ["research-v2-data", "--output-dir", str(tmp_path), "daily-proof", v.dataset_id]
    assert main(args) == 0
    one = json.loads(capsys.readouterr().out)
    assert main(args) == 0
    assert json.loads(capsys.readouterr().out) == one


def test_session_count_drives_start_not_calendar_days():
    req = warmup_request("SOXX", "2026-10-03", 500)
    assert len(sessions(req["start"], "2026-10-02")) == 500
    assert req["start"] > "2024-03-07"


def test_action_import_cli_preserves_parent_and_requires_new_identity(tmp_path, capsys):
    v = normalize_daily(provider_capture(10), "daily-parent-v1")
    save_daily(v, tmp_path)
    evidence = tmp_path/"actions.json"
    evidence.write_text(canonical(v.actions.unpack()), encoding="utf-8")
    args = ["research-v2-data", "--output-dir", str(tmp_path), "daily-action-import",
            v.dataset_id, str(evidence), "--new-dataset-id", "daily-parent-v2"]
    assert main(args) == 0
    capsys.readouterr()
    child = load_daily("daily-parent-v2", tmp_path)
    assert load_daily(v.dataset_id, tmp_path) == v
    assert child.manifest.unpack()["parent_content_hash"] == v.content_hash
    assert child.manifest.unpack()["raw_unit_status"] == "UNVERIFIED"
    assert prepare_daily(child, child.bars[-1].known_at).prefix.input_status == "UNAVAILABLE"
    args[-1] = v.dataset_id
    assert main(args) == 1
