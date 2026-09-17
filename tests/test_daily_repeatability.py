"""Deterministic operational checks; these are not multi-day production evidence."""

import pytest

from richping.cli import main, write_report
from richping.core import Config, canonical, cutoff_at
from richping.data import synthetic_dataset
from richping.engine import Engine
from richping.pipeline import scan, track
from richping.store import Store


def test_pending_matures_then_immutable_outcomes_are_reused(tmp_path, monkeypatch):
    data = synthetic_dataset(n=110, symbols=("ALFA",))
    config = Config(tickers=("ALFA",))
    engine = Engine(data, config)
    signal = next(s for day in data.sessions[60:80] for s in engine.signals(day)["candidates"])
    with Store(tmp_path / "maturity.db") as store:
        store.save_dataset(data)
        report = scan(store, data, config, signal["session"], engine=engine)
        assert report["recommendations"] == []  # This short fixture cannot calibrate.
        with store.db:
            store.db.execute("INSERT INTO recommendations VALUES(?,?,?,?,?)",
                             ("fixture", report["run_id"], "ALFA", 1, canonical(signal)))
        snapshot_before = store.db.execute("SELECT snapshot FROM recommendations").fetchone()[0]
        counts, _ = track(store, data, signal["cutoff"])
        assert counts["PENDING"] == 5
        assert store.db.execute("SELECT COUNT(*) FROM outcomes").fetchone()[0] == 0
        as_of = cutoff_at(data.end).isoformat()
        counts, rows = track(store, data, as_of)
        assert counts["COMPLETE"] == 5
        assert counts["PENDING"] == 0
        assert len(rows) == 1  # Holding-period denominator, not all five horizons.
        before = [tuple(r) for r in store.db.execute("SELECT * FROM outcomes ORDER BY horizon")]

        def unexpected_recompute(*args, **kwargs):
            raise AssertionError("Finalized outcome must be reused")

        monkeypatch.setattr("richping.pipeline.observe", unexpected_recompute)
        assert track(store, data, as_of) == (counts, rows)
        assert [tuple(r) for r in store.db.execute("SELECT * FROM outcomes ORDER BY horizon")] == before
        assert store.db.execute("SELECT snapshot FROM recommendations").fetchone()[0] == snapshot_before


def test_running_run_blocks_until_explicit_recovery(tmp_path):
    data = synthetic_dataset(n=70, symbols=("ALFA",))
    config = Config(tickers=("ALFA",))
    path = tmp_path / "running.db"
    with Store(path) as store:
        store.save_dataset(data)
        report = scan(store, data, config, data.end)
        with store.db:
            store.db.execute("UPDATE runs SET status='RUNNING' WHERE id=?", (report["run_id"],))
        with pytest.raises(ValueError, match="already active"):
            scan(store, data, config, data.end)
    assert main(["--db", str(path), "recover-runs"]) == 0
    with Store(path) as store:
        scan(store, data, config, data.end)
        assert tuple(store.db.execute("SELECT status,attempts FROM runs").fetchone()) == ("SUCCEEDED", 2)
        assert store.db.execute("SELECT COUNT(*) FROM runs").fetchone()[0] == 1


def test_failed_report_replace_preserves_previous_complete_artifact(tmp_path, monkeypatch):
    from pathlib import Path
    path = tmp_path / "report.json"
    write_report({"complete": "old"}, path)
    before = path.read_bytes()

    def failed_replace(*args):
        raise OSError("simulated replace failure")

    monkeypatch.setattr(Path, "replace", failed_replace)
    with pytest.raises(OSError, match="replace failure"):
        write_report({"complete": "new"}, path)
    assert path.read_bytes() == before
