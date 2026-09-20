import json
from datetime import timedelta
from hashlib import sha256
from pathlib import Path

import pytest

from richping.cli import main
from richping.core import Config, canonical, cutoff_at
from richping.data import Dataset, synthetic_dataset
from richping.engine import Engine
from richping.operations import (
    REPORT_SCHEMA,
    artifact_root,
    build_operational_report,
    ensure_start_manifest,
    publish_report,
)
from richping.pipeline import scan
from richping.store import Store


def attempt(at, status="SUCCEEDED", attempt_id="fixture-attempt"):
    return {
        "schema": "richping_execution_attempt_v1",
        "attempt_id": attempt_id,
        "command": "daily",
        "role": "research",
        "database": "fixture.db",
        "status": status,
        "stage": "COMPLETE" if status == "SUCCEEDED" else "FAILED",
        "started_at": at,
        "finished_at": at,
        "target_session": None,
        "run_id": None,
        "dataset_id": None,
        "decision": None,
        "error": None if status == "SUCCEEDED" else "ConnectionError: offline",
        "events": [],
    }


def shadow_fixture(tmp_path, n=100):
    data = synthetic_dataset(n=n, symbols=("ALFA",), captured_at=None)
    config = Config(tickers=("ALFA",))
    now = (cutoff_at(data.end) + timedelta(minutes=1)).isoformat()
    path = tmp_path / "fixture.db"
    with Store(path) as store:
        store.save_dataset(data)
        report = scan(store, data, config, data.end, "shadow", now=now)
    return path, data, config, now, report


def test_successful_normal_no_trade_report_is_explicit_and_read_only(tmp_path):
    path, data, config, now, run = shadow_fixture(tmp_path)
    assert run["decision"] == "NO TRADE"
    before = path.read_bytes()
    with Store(path, read_only=True) as store:
        derived = build_operational_report(
            store, config, run, attempt(now), tmp_path / "ops", now=now, dataset=data,
        )
    assert path.read_bytes() == before
    assert derived["schema"] == REPORT_SCHEMA
    assert derived["execution"]["status"] == "SUCCEEDED"
    assert derived["judgment"]["status"] == "NORMAL_NO_TRADE"
    assert derived["no_trade"]["normal"] is True
    assert derived["freshness"]["status"] == "CURRENT"
    assert derived["evidence"]["alpha"] == "INSUFFICIENT_EVIDENCE"
    assert derived["evidence"]["portfolio_return"] is None
    assert derived["evidence"]["forward_observations"]["read_only"] is True


def test_frozen_investment_decision_matches_pre_r0_golden_values():
    """Captured before R0 reporting edits; model provenance may change, judgment may not."""
    data = synthetic_dataset(n=700, symbols=("ALFA", "BETA", "GAMA", "DELT"))
    config = Config(tickers=("ALFA", "BETA", "GAMA", "DELT"))
    engine = Engine(data, config)
    signal = engine.signals("2024-05-28")
    candidate = next(item for item in signal["candidates"] if item["ticker"] == "BETA")
    calibration = engine.calibration(candidate)
    assert signal["regime"] == "RISK_ON_LOW_VOL"
    assert signal["supported"] is True
    assert candidate["score"] == pytest.approx(61.17693692456759)
    assert candidate["entry_reference"] == pytest.approx(497.24605892409465)
    assert candidate["stop_reference"] == pytest.approx(469.4161450571534)
    assert candidate["target_reference"] == pytest.approx(552.9058866579771)
    assert calibration["eligible"] is True
    assert calibration["samples"] == 419
    assert calibration["signal_dates"] == 298
    assert calibration["expected_return"] == pytest.approx(0.011059415273089809)
    assert calibration["edge_ci"] == pytest.approx([0.005998905764518649, 0.015880765150104663])


def test_candidate_report_labels_atr_and_calibration_as_reference_evidence(tmp_path):
    full = synthetic_dataset(n=700, symbols=("ALFA", "BETA", "GAMA", "DELT"))
    target = "2024-05-28"
    bars = [bar for bar in full.bars if bar.session <= target]
    metadata = dict(full.metadata)
    metadata["quality"] = "research"
    metadata["source"] = "fixture-forward"
    metadata["action_capture"] = dict(metadata["action_capture"], captured_at=cutoff_at(target).isoformat())
    data = Dataset(bars, metadata, full.members)
    config = Config(tickers=("ALFA", "BETA", "GAMA", "DELT"))
    now = (cutoff_at(target) + timedelta(minutes=1)).isoformat()
    path = tmp_path / "candidate.db"
    with Store(path) as store:
        store.save_dataset(data)
        run = scan(store, data, config, target, "shadow", now=now)
        derived = build_operational_report(
            store, config, run, attempt(now), tmp_path / "ops", now=now, dataset=data,
        )
    assert derived["judgment"]["status"] == "CANDIDATES_AVAILABLE"
    assert derived["evidence"]["level"] == "FRESH_SHADOW"
    beta = next(item for item in derived["candidates"] if item["ticker"] == "BETA")
    assert beta["atr"] > 0
    assert beta["reference_warning"] == "Close/ATR references only; not orders or fills"
    assert beta["entry_observation"] == "next XNYS session open"
    assert beta["evaluation_exit"] == "5th XNYS session close"
    assert beta["expected_value"]["samples"] == 419
    assert beta["expected_value"]["independent_signal_dates"] == 298
    assert "research calibration" in beta["expected_value"]["limitation"]


def test_reporting_model_id_change_inherits_compatible_performance_pause(tmp_path):
    data = synthetic_dataset(n=100, symbols=("ALFA",))
    config = Config(tickers=("ALFA",))
    path = tmp_path / "latch.db"
    old_model = "baseline-v1-pre-r0"
    with Store(path) as store:
        store.save_dataset(data)
        with store.db:
            store.db.execute("INSERT INTO model_versions VALUES(?,?)", (old_model, canonical(config.payload())))
            store.db.execute("INSERT INTO risk_state VALUES(?,?,?,?)",
                             (old_model, "shadow", "PAUSED", data.sessions[70]))
        now = (cutoff_at(data.end) + timedelta(minutes=1)).isoformat()
        manifest = ensure_start_manifest(tmp_path / "ops", store, config, now=now)
        report = scan(store, data, config, data.end, "shadow", now=now)
        state = store.db.execute(
            "SELECT state FROM risk_state WHERE model_id=? AND mode='shadow'", (config.model_id,)
        ).fetchone()[0]
    assert report["state"] == "PAUSED"
    assert report["state_reason"] == "performance_pause_latched"
    assert report["risk_latch_source_model"] == old_model
    assert report["recommendations"] == []
    assert state == "PAUSED"
    assert old_model in manifest["predecessor_model_ids"]
    assert manifest["risk_latch_sources"] == [
        {"model_id": old_model, "state": "PAUSED", "since_session": data.sessions[70]}
    ]
    assert manifest["provenance"]["investment_decision_contract_changed"] is False


def test_collection_failure_before_run_is_visible_with_prior_success(tmp_path, monkeypatch):
    path, _, _, _, prior = shadow_fixture(tmp_path)
    run_count_before = None
    with Store(path, read_only=True) as store:
        run_count_before = store.db.execute("SELECT COUNT(*) FROM runs").fetchone()[0]

    def offline(*args, **kwargs):
        raise ConnectionError("offline before collection")

    monkeypatch.setattr("richping.cli.yahoo_dataset", offline)
    root = tmp_path / "operations"
    assert main(["--db", str(path), "daily", "--output-dir", str(root)]) == 1
    report = json.loads((root / "latest.json").read_text(encoding="utf-8"))
    attempts = list((root / "attempts").glob("*.json"))
    with Store(path, read_only=True) as store:
        assert store.db.execute("SELECT COUNT(*) FROM runs").fetchone()[0] == run_count_before
    assert len(attempts) == 1
    assert report["execution"]["status"] == "FAILED"
    assert report["judgment"]["status"] == "DATA_FAILURE"
    assert report["judgment"]["data_failure_is_negative_expected_value"] is False
    assert report["prior_success_reference"]["run_id"] == prior["run_id"]
    assert report["execution"]["source_run_is_prior_success"] is True


def test_stale_holiday_redisplay_is_not_a_new_forward_observation(tmp_path):
    config = Config(tickers=("ALFA",))
    data = synthetic_dataset(n=100, symbols=("ALFA",))
    run = {
        "run_id": "holiday-run", "session": "2025-07-03", "cutoff": "2025-07-03T21:30:00+00:00",
        "mode": "shadow", "quality": "research", "model": config.model_id, "dataset_id": data.id,
        "regime": "RISK_ON_LOW_VOL", "state": "NORMAL", "state_reason": "risk_sample_warmup",
        "outcome_contract": "v3_cash_action_guard", "evaluation_policy": "cash_action_review_v1",
        "decision": "NO TRADE", "reason": "insufficient_evidence_or_edge", "recommendations": [],
        "excluded": {"ALFA": "weak_signal"}, "universe_size": 1,
        "outcomes": {"COMPLETE": 0, "PENDING": 0, "UNRESOLVED": 0,
                     "evaluation": {"policy": "cash_action_review_v1", "eligible_complete": 0,
                                    "excluded_complete": 0, "by_reason": {}}},
    }
    path = tmp_path / "empty.db"
    with Store(path) as store:
        derived = build_operational_report(
            store, config, run, attempt("2025-07-08T12:00:00+00:00"), tmp_path / "ops",
            now="2025-07-08T12:00:00+00:00", dataset=data, duplicate=True,
        )
    assert derived["freshness"]["status"] == "STALE"
    assert derived["freshness"]["market_closed_gap"] is True
    assert derived["execution"]["duplicate_run"] is True
    assert derived["execution"]["new_forward_observation"] is False


def test_atomic_generation_failure_keeps_previous_latest(tmp_path, monkeypatch):
    root = tmp_path / "ops"
    def value(session, attempt_id, marker):
        return {"schema": REPORT_SCHEMA,
            "freshness": {"target_session": session, "status": "CURRENT", "valid_until": None,
                          "latest_collection_at": None},
            "execution": {"attempt_id": attempt_id, "status": "SUCCEEDED", "stage": "COMPLETE",
                          "duplicate_run": False, "new_forward_observation": True},
            "judgment": {"status": "NORMAL_NO_TRADE", "reason": "fixture"},
            "identity": {"source": "fixture", "quality": "synthetic", "model_id": "fixture",
                         "dataset_id": "fixture"},
            "no_trade": {"reason": "fixture", "excluded_by_reason": {}},
            "candidates": [], "outcomes": {},
            "evidence": {"level": "SYNTHETIC", "alpha": "INSUFFICIENT_EVIDENCE"},
            "schedule": {"status": "ON_TIME", "delay_seconds": 0},
            "operations": {"unattended_multi_day_stability": "NOT_ESTABLISHED"},
            "marker": marker}
    old = value("2025-01-02", "old", "old")
    publish_report(old, root)
    before = (root / "latest.json").read_bytes()
    from richping import operations
    original = operations.atomic_write_text

    def fail_markdown(text, path):
        if str(path).endswith(".md"):
            raise OSError("simulated markdown replace failure")
        return original(text, path)

    monkeypatch.setattr(operations, "atomic_write_text", fail_markdown)
    new = value("2025-01-03", "new", "new")
    with pytest.raises(OSError, match="markdown replace failure"):
        publish_report(new, root)
    assert (root / "latest.json").read_bytes() == before


def test_report_cli_is_database_byte_read_only(tmp_path, capsys):
    path, _, _, _, _ = shadow_fixture(tmp_path)
    before = sha256(path.read_bytes()).hexdigest()
    assert main(["--db", str(path), "report", "--output-dir", str(tmp_path / "report")]) == 0
    capsys.readouterr()
    assert sha256(path.read_bytes()).hexdigest() == before


def test_operational_and_research_default_paths_are_separate(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert artifact_root("var/richping.db", "daily") == Path("var/operations")
    assert artifact_root("var/fixture.db", "daily") == Path("var/research/fixture/daily")
    assert artifact_root("var/richping.db", "scan") == Path("var/research/richping/scan")


def test_unversioned_historical_run_is_not_relabelled_as_current_contract(tmp_path):
    config = Config(tickers=("ALFA",))
    data = synthetic_dataset(n=100, symbols=("ALFA",))
    legacy_model = "baseline-v1-legacy-fixture"
    run = {
        "run_id": "legacy", "session": data.end, "cutoff": cutoff_at(data.end).isoformat(),
        "mode": "shadow", "quality": "synthetic", "model": legacy_model, "dataset_id": data.id,
        "regime": "RISK_OFF_LOW_VOL", "state": "PAUSED", "state_reason": "unsupported_market_regime",
        "decision": "NO TRADE", "reason": "unsupported_market_regime", "recommendations": [],
        "excluded": {"ALFA": "weak_signal"}, "universe_size": 1,
        "outcomes": {"COMPLETE": 0, "PENDING": 0, "UNRESOLVED": 0},
    }
    path = tmp_path / "legacy.db"
    with Store(path) as store:
        store.save_dataset(data)
        with store.db:
            store.db.execute("INSERT INTO model_versions VALUES(?,?)",
                             (legacy_model, canonical(config.payload())))
        derived = build_operational_report(
            store, config, run, root=tmp_path / "ops", now=cutoff_at(data.end), dataset=data,
        )
    assert derived["identity"]["feature_contract"] == "UNKNOWN_LEGACY_UNRECORDED"
    assert derived["identity"]["outcome_contract"] == "v1_price_only"
    assert derived["identity"]["evaluation_contract"] == "legacy_unversioned"
    assert derived["identity"]["model_code_hash"] is None
    assert derived["identity"]["report_code_hash"] is not None
