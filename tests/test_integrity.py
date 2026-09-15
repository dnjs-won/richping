from dataclasses import replace
from datetime import timedelta
import json
import sqlite3

import pytest

from richping.core import Config, close_at, cutoff_at, next_sessions, timestamp
from richping.data import Dataset, synthetic_dataset
from richping.engine import Engine, observe
from richping.pipeline import scan, track
from richping.store import Store


@pytest.fixture(scope="module")
def data():
    return synthetic_dataset(n=400)


@pytest.fixture
def config():
    return Config(tickers=("ALFA", "BETA", "GAMA", "DELT"), train_sessions=180)


def clone(data, bars=None, members=None):
    return Dataset(data.bars if bars is None else bars, data.metadata, data.members if members is None else members)


def snapshot(data, i=200):
    session = data.sessions[i]
    b = data.by_ticker["ALFA"][session]
    return {"ticker": "ALFA", "session": session, "entry_reference": b.close,
            "regime": "RISK_ON_LOW_VOL",
            "stop_reference": b.close * 0.95, "target_reference": b.close * 1.1,
            "cost": 0.002, "holding_period": 5, "cutoff": cutoff_at(session).isoformat()}


def test_timezone_required():
    with pytest.raises(ValueError, match="Timezone"):
        timestamp("2025-01-01T12:00:00")


def test_real_holiday_and_early_close():
    assert next_sessions("2024-11-27", 2) == ["2024-11-29", "2024-12-02"]
    assert close_at("2024-11-29").hour == 18


@pytest.mark.parametrize("field,value", [("close", float("nan")), ("volume", -1), ("high", 1)])
def test_invalid_bars_rejected(data, field, value):
    with pytest.raises(ValueError):
        replace(data.bars[0], **{field: value}).validate()


def test_early_known_at_rejected(data):
    b = data.bars[0]
    with pytest.raises(ValueError, match="known_at"):
        replace(b, known_at=close_at(b.session).isoformat()).validate()


def test_duplicate_input_rejected(data):
    with pytest.raises(ValueError, match="Duplicate"):
        clone(data, data.bars + [data.bars[0]])


def test_future_data_cannot_change_features_or_calibration(data, config):
    day = data.sessions[300]
    mutated = [replace(b, open=b.open * 7, high=b.high * 7, low=b.low * 7, close=b.close * 7)
               if b.session > day else b for b in data.bars]
    a, b = Engine(data, config), Engine(clone(data, mutated), config)
    assert a.signals(day) == b.signals(day)
    for signal in a.signals(day)["candidates"]:
        assert a.calibration(signal) == b.calibration(signal)


def test_shadow_cannot_see_unknown_bars(data, config):
    day = data.sessions[300]
    future = (cutoff_at(day) + timedelta(days=5)).isoformat()
    changed = [replace(b, known_at=future) if b.session == day and b.ticker == "SPY" else b for b in data.bars]
    engine = Engine(clone(data, changed), config)
    with pytest.raises(ValueError, match="benchmark"):
        engine.signals(day, cutoff_at(day).isoformat(), "shadow")


def test_future_membership_not_visible_in_shadow(data, config):
    day = data.sessions[300]
    members = [{**m, "known_at": (cutoff_at(day) + timedelta(days=1)).isoformat()} for m in data.members]
    result = Engine(clone(data, members=members), config).signals(day, mode="shadow")
    assert result["candidates"] == []
    assert set(result["excluded"].values()) == {"not_in_asof_universe"}


def test_same_close_entry_is_never_used(data):
    s = snapshot(data)
    days = next_sessions(s["session"], 5)
    result = observe(s, data, 5, cutoff_at(days[-1]).isoformat())
    entry = data.by_ticker["ALFA"][days[0]].open
    exit_price = data.by_ticker["ALFA"][days[-1]].close
    assert result["entry_price"] == entry
    assert result["net_return"] == pytest.approx(exit_price / entry - 1 - 0.002)


def test_immature_outcome_is_pending(data):
    s = snapshot(data)
    assert observe(s, data, 5, s["cutoff"])["status"] == "PENDING"


def test_missing_session_not_shifted_forward(data):
    s = snapshot(data)
    missing = next_sessions(s["session"], 3)[1]
    changed = [b for b in data.bars if (b.ticker, b.session) != ("ALFA", missing)]
    out = observe(s, clone(data, changed), 5, cutoff_at(data.end).isoformat())
    assert out["status"] == "UNRESOLVED"
    assert "missing" in out["reason"]


@pytest.mark.parametrize("action,value", [("split", 4.0), ("dividend", 1.2)])
def test_corporate_actions_fail_closed(data, action, value):
    s = snapshot(data)
    day = next_sessions(s["session"], 1)[0]
    changed = [replace(b, **{action: value}) if (b.ticker, b.session) == ("ALFA", day) else b for b in data.bars]
    assert observe(s, clone(data, changed), 5, cutoff_at(data.end).isoformat())["status"] == "UNRESOLVED"


def test_both_barriers_same_day_are_ambiguous(data):
    s = snapshot(data)
    day = next_sessions(s["session"], 1)[0]
    changed = [replace(b, low=min(b.low, s["stop_reference"] * 0.9), high=max(b.high, s["target_reference"] * 1.1))
               if (b.ticker, b.session) == ("ALFA", day) else b for b in data.bars]
    out = observe(s, clone(data, changed), 1, cutoff_at(day).isoformat())
    assert out["first_hit"] == "AMBIGUOUS"


def test_revised_price_units_not_mixed(data):
    s = {**snapshot(data), "entry_reference": 1.0}
    assert observe(s, data, 5, cutoff_at(data.end).isoformat())["reason"] == "price_vintage_changed"


def test_missing_feature_session_excludes_ticker(data, config):
    day = data.sessions[300]
    changed = [b for b in data.bars if (b.ticker, b.session) != ("ALFA", data.sessions[280])]
    result = Engine(clone(data, changed), config).signals(day)
    assert result["excluded"]["ALFA"] == "missing_or_unknown_history"


def test_store_snapshot_and_dataset_are_immutable(tmp_path, data, config):
    with Store(tmp_path / "test.db") as store:
        store.save_dataset(data)
        assert store.save_dataset(data) == data.id
        assert store.load_dataset().id == data.id
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            store.db.execute("UPDATE bars SET body='{}'")
        store.db.rollback()
        report = scan(store, data, config, data.sessions[300])
        run_id = report["run_id"]
        with store.db:
            store.db.execute("INSERT INTO recommendations VALUES('manual',?,'ZZZ',99,'{}')", (run_id,))
        for sql in ("UPDATE recommendations SET snapshot='{}'", "DELETE FROM recommendations"):
            with pytest.raises(sqlite3.IntegrityError, match="immutable"):
                store.db.execute(sql)
            store.db.rollback()


def test_repeat_scan_is_identical(tmp_path, data, config):
    with Store(tmp_path / "test.db") as store:
        store.save_dataset(data)
        first = scan(store, data, config, data.sessions[300])
        second = scan(store, data, config, data.sessions[300])
        assert first == second
        assert store.db.execute("SELECT count(*) FROM runs").fetchone()[0] == 1


def test_failed_run_is_retryable(tmp_path, data, config):
    class Broken:
        def signals(self, *args):
            raise ValueError("simulated failure")
    with Store(tmp_path / "test.db") as store:
        store.save_dataset(data)
        with pytest.raises(ValueError, match="simulated"):
            scan(store, data, config, data.sessions[300], engine=Broken())
        assert store.db.execute("SELECT status FROM runs").fetchone()[0] == "FAILED"
        scan(store, data, config, data.sessions[300])
        assert tuple(store.db.execute("SELECT status,attempts FROM runs").fetchone()) == ("SUCCEEDED", 2)


def test_observation_does_not_mutate_snapshot(tmp_path, data, config):
    from richping.core import canonical
    with Store(tmp_path / "test.db") as store:
        store.save_dataset(data)
        report = scan(store, data, config, data.sessions[200])
        snap = snapshot(data)
        with store.db:
            store.db.execute("INSERT INTO recommendations VALUES('manual',?,'ZZZ',99,?)", (report["run_id"], canonical(snap)))
        before = store.db.execute("SELECT snapshot FROM recommendations WHERE id='manual'").fetchone()[0]
        track(store, data, cutoff_at(data.end).isoformat())
        count = store.db.execute("SELECT count(*) FROM outcomes").fetchone()[0]
        track(store, data, cutoff_at(data.end).isoformat())
        assert store.db.execute("SELECT count(*) FROM outcomes").fetchone()[0] == count
        assert store.db.execute("SELECT snapshot FROM recommendations WHERE id='manual'").fetchone()[0] == before
        assert count >= 5


def test_scan_rejects_missed_shadow_entry(tmp_path, data, config):
    with Store(tmp_path / "test.db") as store:
        store.save_dataset(data)
        with pytest.raises(ValueError, match="Stale signal"):
            scan(store, data, config, data.sessions[200], "shadow", now=cutoff_at(data.sessions[201]).isoformat())
