"""Scoped real-unit admission plus causal split regressions; no efficacy claims."""

from contextlib import ExitStack
from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
from hashlib import sha256
import json
import subprocess
from pathlib import Path

import pytest
import yaml

from richping.cli import main
from richping.core import digest, timestamp
from richping.research_v2.contracts import JsonObject
from richping.research_v2.daily_data import DailyVintage, save_daily, load_daily
from richping.research_v2.daily_identity import IDENTITY, FIELDS, admit_identity_interval, unit_comparison
from richping.research_v2.strategy.daily_input import prepare_daily
from richping.research_v2.strategy.daily_trend import classify_daily_trend
from richping.research_v2.strategy.daily_exhaustion import classify_daily_exhaustion
from test_research_v2_daily_pit import fixture, split, with_actions

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "research/data_evidence/h0001-action-unit-20261003"


@pytest.fixture(scope="module")
def real():
    parent = DailyVintage.loads((ROOT / "research/data_evidence/h0001-daily-pit-20261003/daily-vintage.json").read_text(encoding="utf-8"))
    action = json.loads((EVIDENCE / "action-history-audit.json").read_text(encoding="utf-8"))
    unit = json.loads((EVIDENCE / "ohlc-unit-crosscheck.json").read_text(encoding="utf-8"))
    return parent, action, unit


def admitted(real):
    return admit_identity_interval(*real[:1], "soxx-yahoo-rth-daily-pit-20261003-v2", *real[1:])


def test_frozen_semantics_do_not_freeze_per_asof_negative_receipts():
    record = yaml.safe_load((ROOT / "research/decision_records/H0001-daily-input-freeze-v1.yaml").read_text(encoding="utf-8"))
    s = record["pit_split_semantics"]
    assert s["eligible_action"] == "effective_at_lte_as_of_AND_required_action_evidence_known_at_lte_as_of"
    assert s["announced_but_not_effective"] == "forbidden_until_effective"
    assert s["raw_fallback"] == "forbidden"
    assert s["state_input_known_at"] == "maximum_bar_action_and_other_actual_transform_input_known_at"
    assert not any("negative" in k or "no_action" in k for k in s)
    # The conclusion is recorded as interpretation remediation, not a strategy revision.
    audit = yaml.safe_load((ROOT / "research/decision_records/H0001-action-unit-interpretation-audit-v1.yaml").read_text(encoding="utf-8"))
    assert audit["frozen_decisions_changed"] is False
    assert audit["negative_receipt_requirement"]["explicitly_frozen"] is False
    for p, expected in audit["frozen_file_sha256_LF_normalized"].items():
        # v12 spec is historical evidence; current v13 preserves all primitive
        # roots under the composition revision's separate exact-delta proof.
        raw = (subprocess.check_output(["git", "show", "1c661d8:" + p], cwd=ROOT)
               if p == "research/strategy_specs/H0001-r03-draft.yaml" else (ROOT / p).read_bytes())
        assert sha256(raw.replace(b"\r\n", b"\n")).hexdigest() == expected


def test_real_no_event_admitted_without_backdating_or_relabelling(real):
    v = admitted(real)
    b = v.bars[180]
    r = prepare_daily(v, b.known_at)
    assert r.prefix.input_status == "READY"
    assert r.prefix.transform_known_at == b.known_at
    assert r.prefix.transform_known_at < timestamp(real[1]["captured_at"])
    assert v.actions == real[0].actions and v.actions.unpack()["coverage"] == []
    assert r.transform.unpack()["transform_version"] == IDENTITY
    assert r.transform.unpack()["factor"] == 1 and r.transform.unpack()["applied_actions"] == []
    assert v.manifest.unpack()["raw_price_basis"] == real[0].manifest.unpack()["raw_price_basis"]
    assert [tuple(getattr(x, k) for k in FIELDS) for x in r.prefix.bars] == [tuple(getattr(x, k) for k in FIELDS) for x in v.bars[:181]]


def test_expost_capture_date_is_not_causal_feature(real):
    first = admitted(real)
    later_action, later_unit = deepcopy(real[1]), deepcopy(real[2])
    later_action["captured_at"] = later_unit["captured_at"] = "2026-10-04T12:00:00Z"
    second = admit_identity_interval(real[0], first.dataset_id, later_action, later_unit)
    as_of = first.bars[178].known_at
    a, b = prepare_daily(first, as_of), prepare_daily(second, as_of)
    assert first.content_hash != second.content_hash  # immutable admission vintage changes
    assert a.prefix == b.prefix
    assert a.transform.unpack()["input_hash"] == b.transform.unpack()["input_hash"]
    assert classify_daily_trend(a.prefix, as_of) == classify_daily_trend(b.prefix, as_of)


@pytest.mark.parametrize("defect", ["inside", "prior_boundary", "future_boundary", "coverage_role", "wrong_hash", "row_missing", "quote", "unit_fail", "preadjusted", "nav_only", "scope", "wrong_date"])
def test_identity_audit_defects_fail_closed(real, defect):
    a, u = deepcopy(real[1]), deepcopy(real[2])
    if defect == "inside":
        a["splits_inside_interval"] = [{"trading_date": "2025-01-02"}]
    elif defect == "prior_boundary":
        a["previous_effective_split"]["trading_date"] = a["interval_start"]
    elif defect == "future_boundary":
        a["next_effective_split"]["trading_date"] = a["interval_end"]
    elif defect == "coverage_role":
        a["dataset_completeness_sources"] = [s for s in a["dataset_completeness_sources"] if s["role"] != "INDEPENDENT_ACTION_HISTORY"]
    elif defect == "wrong_hash":
        u["raw_capture_hash"] = "0" * 64
    elif defect == "row_missing":
        u["rows"].pop()
    elif defect == "quote":
        u["rows"][0]["yahoo_quote"]["close"] += 1
    elif defect == "unit_fail":
        u["rows"][0]["market_ohlc"] = {k: val * 1.01 for k, val in u["rows"][0]["market_ohlc"].items()}
    elif defect == "preadjusted":
        u["rows"][0]["market_ohlc"] = {k: val * 3 for k, val in u["rows"][0]["market_ohlc"].items()}
    elif defect == "nav_only":
        u["rows"][0].pop("market_ohlc")
    elif defect == "scope":
        a["certification_scope"] = "STRATEGY_KNOWN_AT"
    else:
        u["rows"][0]["session"] = "2024-10-03"
    with pytest.raises((ValueError, KeyError)):
        admit_identity_interval(real[0], "bad-admission", a, u)


def test_unit_comparison_pass_fail_and_future_preadjustment(real):
    r = real[2]["rows"][-1]
    assert unit_comparison(r["yahoo_quote"], r["market_ohlc"])["unit_certification_result"] == "PASS"
    early = {k: v / 3 for k, v in r["yahoo_quote"].items()}
    result = unit_comparison(early, r["market_ohlc"])
    assert result["future_split_preadjustment_detected"] and result["unit_certification_result"] == "FAIL"
    different = {k: v * 1.01 for k, v in r["yahoo_quote"].items()}
    assert unit_comparison(different, r["market_ohlc"])["unit_certification_result"] == "FAIL"


@pytest.mark.parametrize("position", [0, 100, 499])
def test_actual_event_cannot_hide_in_identity_even_with_unknown_evidence(real, position):
    v = admitted(real)
    event = split(v, effective=v.bars[position].start_at, known=v.bars[-1].known_at)
    event["known_at_semantics"] = "ACTUAL_CAPTURE_RECEIPT"
    event["known_at"] = v.actions.unpack()["captured_at"]
    with pytest.raises(ValueError, match="contradicts"):
        with_actions(v, [event])


def test_prior_2024_and_future_2026_boundaries_outside_real_interval(real):
    a = real[1]
    assert a["previous_effective_split"]["trading_date"] == "2024-03-07" < a["interval_start"]
    assert a["next_effective_split"]["trading_date"] == "2026-11-05" > a["interval_end"]
    v = admitted(real)
    for session in ("2026-09-30", "2026-10-02"):
        b = next(b for b in v.bars if b.session == session)
        assert prepare_daily(v, b.known_at).transform.unpack()["factor"] == 1


@pytest.mark.parametrize("as_of,applied", [("2026-10-02T16:00:00-04:00", False),
    ("2026-09-30T16:00:00-04:00", False), ("2026-11-04T15:59:59-05:00", False),
    ("2026-11-05T09:30:00-05:00", True)])
def test_future_2026_announced_event_never_applied_before_effective(as_of, applied):
    v = fixture(ending="2026-11-05", as_ofs=[as_of])
    e = split(v, effective="2026-11-05T09:30:00-05:00", known="2026-08-22T00:00:00Z")
    # Explicit simulated source clock, not a reconstructed real announcement receipt.
    result = prepare_daily(with_actions(v, [e]), as_of)
    assert result.prefix.input_status == "READY"
    assert bool(result.transform.unpack()["applied_actions"]) == applied
    assert result.transform.unpack()["factors"][0] == pytest.approx(1 / 3 if applied else 1)


def test_2024_event_still_requires_known_at_and_correct_factor_direction():
    effective = timestamp("2024-03-07T09:30:00-05:00")
    known = effective + timedelta(minutes=5)
    v = fixture(ending="2024-03-08", as_ofs=[effective, known])
    # Simulate pre-split old-share prices three times the same economic scale.
    post_unit_bars = v.bars
    v = replace(v, bars=tuple(replace(b, **{k: getattr(b, k) * 3 for k in FIELDS})
        if b.end_at <= effective else b for b in v.bars))
    v = with_actions(v, [split(v, effective=effective, known=known)])
    assert prepare_daily(v, effective).prefix.input_reason == "effective_split_required_evidence_not_yet_known"
    r = prepare_daily(v, v.bars[-1].known_at)
    assert r.prefix.input_status == "READY"
    before = next(i for i, b in enumerate(v.bars) if b.session == "2024-03-06")
    after = before + 1
    for k in FIELDS:
        assert getattr(r.prefix.bars[before], k) == pytest.approx(getattr(v.bars[before], k) / 3)
        assert getattr(r.prefix.bars[after], k) == getattr(v.bars[after], k)
        assert getattr(r.prefix.bars[before], k) == pytest.approx(getattr(post_unit_bars[before], k))
    assert r.prefix.bars[before].volume == v.bars[before].volume


@pytest.mark.parametrize("n,trend,exhaustion", [(178, "UNAVAILABLE", "UNAVAILABLE"), (179, "READY", "UNAVAILABLE"),
    (380, "READY", "UNAVAILABLE"), (381, "READY", "READY")])
def test_real_frozen_boundaries_execute_admitted_vintage(real, n, trend, exhaustion):
    from scripts.h0001_action_unit_offline_proof import calendar_guards
    with ExitStack() as stack:
        calendar_guards(stack)
        v = admitted(real)
        at = v.bars[n - 1].known_at
        p = prepare_daily(v, at).prefix
        assert len(p.bars) == n and p.input_status == "READY"
        assert classify_daily_trend(p, at).status == trend
        assert classify_daily_exhaustion(p, at).status == exhaustion


def test_old_and_new_vintage_immutable_offline_cli(real, tmp_path, capsys, monkeypatch):
    v = real[0]
    save_daily(v, tmp_path)
    old_bytes = (tmp_path / "daily" / (v.dataset_id + ".json")).read_bytes()
    def forbidden(*args, **kwargs):
        raise AssertionError("Network forbidden")
    monkeypatch.setattr("socket.socket.connect", forbidden)
    args = ["research-v2-data", "--output-dir", str(tmp_path), "daily-identity-import", v.dataset_id,
            str(EVIDENCE / "action-history-audit.json"), str(EVIDENCE / "ohlc-unit-crosscheck.json"),
            "--new-dataset-id", "soxx-yahoo-rth-daily-pit-20261003-v2"]
    assert main(args) == 0
    one = json.loads(capsys.readouterr().out)
    assert main(args) == 0 and json.loads(capsys.readouterr().out) == one
    assert load_daily(one["dataset_id"], tmp_path) == admitted(real)
    assert (tmp_path / "daily" / (v.dataset_id + ".json")).read_bytes() == old_bytes
    child = admitted(real)
    changed = replace(child, manifest=JsonObject.of({**child.manifest.unpack(), "note": "changed"}))
    with pytest.raises(ValueError, match="collision"):
        save_daily(changed, tmp_path)
    args[-1] = v.dataset_id
    assert main(args) == 1


def test_real_offline_proof_all2624_and_no_outcome_lookup():
    smoke = json.loads((EVIDENCE / "smoke.json").read_text(encoding="utf-8"))
    join = json.loads((EVIDENCE / "mixed-profile-join-proof.json").read_text(encoding="utf-8"))
    ready = json.loads((EVIDENCE / "daily-readiness.json").read_text(encoding="utf-8"))
    assert smoke["repeat_equal"] and smoke["events"] == join["events"] == 2624
    assert smoke["join_proof_hash"] == digest(join) and smoke["readiness_hash"] == digest(ready)
    assert smoke["join_stream_hash"] == join["joined_event_hash"]
    assert join["joint_READY_evaluations"] > 0 and ready["eligible_input_observations"] == 500
    assert smoke["network_calls"] == smoke["outcome_queries"] == 0
    assert smoke["SQL_reads_whitelist"] == ["v2_bars", "v2_datasets"]
    assert join["ENTRY_CANDIDATE"] is None and smoke["profitability"] == "NOT_RUN"
