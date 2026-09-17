from copy import deepcopy
from dataclasses import replace
import json
import sqlite3
from types import SimpleNamespace

import pytest

from richping.cli import main
from richping.core import Config, OUTCOME_VERSION_V2, canonical, cutoff_at
from richping.coverage import (coverage_report, outcome_summary, pairing_summary,
                              select_candidates, window_reasons)
from richping.data import Dataset, synthetic_dataset
from richping.engine import Engine, observe
from richping.store import Store
from richping.validation import validate


@pytest.fixture(scope="module")
def data():
    return synthetic_dataset(n=350)


@pytest.fixture
def config():
    return Config(tickers=("ALFA", "BETA", "GAMA", "DELT"), train_sessions=180)


def changed(data, symbol, reason, index=100):
    metadata = deepcopy(data.metadata)
    bars = data.bars
    day = data.sessions[index]
    if reason in {"dividend", "split"}:
        bars = [replace(b, **{reason: 1.0}) if (b.ticker, b.session) == (symbol, day) else b for b in bars]
    elif reason == "capital_gains":
        metadata["action_capture"]["events"].append({"ticker": symbol, "session": day,
            "field": "Capital Gains", "amount": 0.5, "known_at": cutoff_at(day).isoformat()})
    elif reason == "action_capture_unknown":
        metadata["action_capture"]["tickers"].pop(symbol)
    return Dataset(bars, metadata, data.members)


@pytest.mark.parametrize("symbol", ["SPY", "QQQ"])
@pytest.mark.parametrize("reason", ["dividend", "split", "capital_gains", "action_capture_unknown"])
def test_independent_benchmark_reason_and_61_session_boundary(data, config, symbol, reason):
    altered = changed(data, symbol, reason)
    report = coverage_report(altered, config, data.sessions[100], data.sessions[161])
    count = 62 if reason == "action_capture_unknown" else 61
    assert report["benchmark"][symbol]["by_reason"][reason]["count"] == count
    other = "QQQ" if symbol == "SPY" else "SPY"
    assert report["benchmark"][other]["by_reason"][reason]["count"] == 0
    assert report["signal_blocks"]["by_reason"][reason]["rate"] == count / 62
    assert report["trading_days"]["signal_blocked"]["count"] == count
    with pytest.raises(ValueError):
        Engine(altered, config).signals(data.sessions[100])


def test_benchmark_overlapping_reasons_do_not_double_count_days(data, config):
    altered = changed(changed(changed(data, "SPY", "dividend"), "QQQ", "dividend"), "SPY", "action_capture_unknown")
    report = coverage_report(altered, config, data.sessions[100], data.sessions[100])
    assert report["trading_days"]["signal_blocked"]["count"] == 1
    assert report["signal_blocks"]["by_reason"]["dividend"]["count"] == 1
    assert report["signal_blocks"]["both_benchmarks_dividend"]["count"] == 1
    for symbol in ("SPY", "QQQ"):
        assert report["benchmark"][symbol]["by_reason"]["dividend"]["count"] == 1
    assert report["signal_blocks"]["by_reason"]["action_capture_unknown"]["count"] == 1


@pytest.mark.parametrize("reason", ["dividend", "split", "capital_gains", "action_capture_unknown"])
def test_candidate_actions_independently_diagnosed_on_blocked_days(data, config, reason):
    altered = changed(changed(data, "ALFA", reason), "SPY", "dividend")
    report = coverage_report(altered, config, data.sessions[100], data.sessions[101])
    candidates = report["candidate_evaluations"]
    assert candidates["total"] == 8
    assert candidates["by_reason"][reason]["count"] == 2
    assert candidates["by_reason"][reason]["rate"] == 2 / 8
    assert candidates["supported"]["count"] == 0
    assert candidates["not_evaluated_benchmark_blocked"]["count"] == 6
    assert report["signal_blocks"]["by_reason"]["dividend"]["rate"] == 1
    assert report["evaluation"]["eligible_complete"]["rate"] is None


def test_missing_history_and_unknown_shadow_data_are_distinct(data):
    day = data.sessions[100]
    missing = Dataset([b for b in data.bars if (b.ticker, b.session) != ("QQQ", day)], data.metadata, data.members)
    assert window_reasons(missing, "QQQ", day) == ["missing_or_unknown_history"]
    future = cutoff_at(data.sessions[101]).isoformat()
    bars = [replace(b, known_at=future) if (b.ticker, b.session) == ("SPY", day) else b for b in data.bars]
    delayed = Dataset(bars, data.metadata, data.members)
    assert window_reasons(delayed, "SPY", day, mode="shadow") == ["data_not_yet_known"]
    # Future capture itself remains pending, never mislabelled capture unknown.
    assert window_reasons(data, "QQQ", day, mode="shadow") == ["data_not_yet_known"]


def test_candidate_asof_universe_and_production_filter_reasons(data, config):
    day = data.sessions[200]
    members = [{**m, "active_from": data.sessions[201]} if m["ticker"] == "ALFA" else m for m in data.members]
    altered = Dataset(data.bars, data.metadata, members)
    cfg = replace(config, min_price=1e9)
    report = coverage_report(altered, cfg, day, day)
    reasons = report["candidate_evaluations"]["by_reason"]
    assert reasons["not_in_asof_universe"]["count"] == 1
    assert reasons["price_or_liquidity"]["count"] == 3
    assert report["decision_funnel"]["by_category"]["no_raw_signal"]["count"] == 1


def test_decision_gates_are_separate_and_ordered(config):
    candidates = [{"ticker": str(i)} for i in range(5)]
    estimates = [
        {"eligible": False, "reason": "insufficient_calibration"},
        {"eligible": False, "reason": "edge_not_supported"},
        {"eligible": True, "edge_ci": [0.001, 0.01]},
        {"eligible": True, "edge_ci": [0.003, 0.01]},
        {"eligible": True, "edge_ci": [0.003, 0.01]},
    ]
    engine = SimpleNamespace(config=config, calibration=lambda s, _: estimates[int(s["ticker"])])
    signals = {"supported": True, "candidates": candidates}
    chosen, rejected = select_candidates(engine, signals, state="REDUCED_EXPOSURE")
    assert chosen == [candidates[3]]
    assert rejected == {"insufficient_calibration": 1, "edge_not_supported": 1,
                        "reduced_exposure_edge_threshold": 1, "below_top_k": 1}
    assert select_candidates(engine, {**signals, "supported": False}) == ([], {})


def test_outcome_denominators_preserve_v2_exclusions_and_pending(data, config):
    engine = Engine(data, config)
    signal = next(s for day in data.sessions[200:300] for s in engine.signals(day)["candidates"])
    as_of = cutoff_at(data.end).isoformat()
    result = observe(signal, data, config.horizon, as_of)
    assert result["status"] == "COMPLETE"
    legacy = {**signal, "outcome_version": OUTCOME_VERSION_V2}
    legacy_result = observe(legacy, data, config.horizon, as_of)
    pending = observe(signal, data, config.horizon, signal["cutoff"])
    records = [(signal, result), (legacy, legacy_result), (signal, pending)]
    before = canonical(records)
    outcomes, evaluation, rows = outcome_summary(records, data, as_of)
    assert outcomes["COMPLETE"] == {"count": 2, "denominator": 3,
                                     "denominator_unit": "holding_period_outcomes", "rate": 2 / 3}
    assert outcomes["PENDING"]["count"] == 1
    assert evaluation["excluded_complete"]["rate"] == 0.5
    assert evaluation["by_reason"]["legacy_v2_unverified_contract"]["count"] == 1
    assert evaluation["by_version"][OUTCOME_VERSION_V2]["count"] == 1
    assert len(rows) == 1
    assert canonical(records) == before


def test_pairing_keeps_neither_eligible_in_unmatched_denominator():
    paired = pairing_summary({"a", "b", "c", "d"}, {"a", "b"}, {"a", "c"})
    assert paired["paired_signal_dates"]["rate"] == 0.25
    assert paired["candidate_only_signal_dates"]["dates"] == ["b"]
    assert paired["spy_only_signal_dates"]["dates"] == ["c"]
    assert paired["unmatched_signal_dates"]["count"] == 3


def test_frozen_replay_matches_existing_validation_and_is_deterministic(data, config, tmp_path):
    before = canonical({"metadata": data.metadata, "members": data.members})
    engine = Engine(data, config)
    original = engine.signals(data.sessions[310])
    with Store(tmp_path / "validation.db") as store:
        reference = validate(store, data, config, train=180, validation=30, oos=30)
    fold = reference["folds"][0]
    expected = fold["oos"]
    report = coverage_report(data, config, expected["start"], expected["end"], fold["calibration_frozen_at"])
    assert report == coverage_report(data, config, expected["start"], expected["end"], fold["calibration_frozen_at"])
    assert report["outcomes"]["COMPLETE"]["count"] > 0
    for status in ("COMPLETE", "PENDING", "UNRESOLVED"):
        assert report["outcomes"][status]["count"] == expected["outcomes"][status]
    for key in ("eligible_complete", "excluded_complete"):
        assert report["evaluation"][key]["count"] == expected["outcomes"]["evaluation"][key]
    for key in report["pairing"]:
        assert report["pairing"][key]["count"] == expected["matched_SPY_evaluation"][key]
    assert report["matched_candidate"] == expected["matched_candidate"]
    assert report["matched_SPY"]["metrics"] == expected["matched_SPY"]
    c = report["candidate_evaluations"]
    assert sum(c[k]["count"] for k in ("supported", "excluded", "not_evaluated_benchmark_blocked")) == c["total"]
    assert sum(m["count"] for m in report["decision_funnel"]["by_category"].values()) == report["trading_days"]["total"]
    assert Engine(data, config).signals(data.sessions[310]) == original
    assert canonical({"metadata": data.metadata, "members": data.members}) == before


def test_cli_coverage_is_read_only_and_missing_db_not_created(data, tmp_path):
    path = tmp_path / "source.db"
    output = tmp_path / "coverage.json"
    with Store(path) as store:
        store.save_dataset(data)
        before = list(store.db.iterdump())
    args = ["--db", str(path), "coverage", "--start", data.end, "--output", str(output)]
    assert main(args) == 0
    first = output.read_bytes()
    assert main(args) == 0
    assert output.read_bytes() == first
    with Store(path, read_only=True) as store:
        assert list(store.db.iterdump()) == before
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            store.db.execute("DELETE FROM experiments")
    result = json.loads(first)
    assert result["quality"] == "synthetic"
    assert result["operational_evidence"]["unattended_multi_day_stability"] == "NOT_ESTABLISHED"
    missing = tmp_path / "missing.db"
    assert main(["--db", str(missing), "coverage", "--output", str(output)]) == 1
    assert not missing.exists()
