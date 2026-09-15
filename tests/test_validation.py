from dataclasses import replace
import json

import pytest

from richping.core import Config
from richping.data import synthetic_dataset
from richping.engine import Engine
from richping.store import Store
from richping.validation import validate, walk_forward_folds


def test_fold_calibration_matches_declared_train_window():
    data = synthetic_dataset(n=350)
    config = Config(tickers=tuple(m["ticker"] for m in data.members), train_sessions=180)
    engine = Engine(data, config)
    fold = next(walk_forward_folds(len(data.sessions), train=180, validation=30, oos=30))
    boundary = data.sessions[fold.validation_start]
    # Calibration contract is independent of whether this day's candidate passes.
    signal = {"session": data.sessions[fold.oos_start], "regime": "RISK_ON_LOW_VOL", "score": 75}
    result = engine.calibration(signal, boundary)
    assert result["training_start"] == data.sessions[fold.train_start]
    assert result["training_end"] == data.sessions[fold.train_end]
    assert result["label_cutoff"] == boundary


def test_walk_forward_records_oos_and_rejects_unverified_promotion(tmp_path):
    data = synthetic_dataset(n=350)
    config = Config(tickers=tuple(m["ticker"] for m in data.members))
    with Store(tmp_path / "validation.db") as store:
        store.save_dataset(data)
        result = validate(store, data, config, train=180, validation=30, oos=30)
        assert len(result["folds"]) == 1
        assert result["promotion"]["decision"] == "REJECT"
        assert result["specification"]["kind"] == "research_OOS"
        assert result["oos"]["samples"] > 0
        assert store.db.execute("SELECT status FROM experiments").fetchone()[0] == "SUCCEEDED"
        for fold in result["folds"]:
            assert fold["train_end"] < fold["validation"]["start"] < fold["oos"]["start"]
            assert fold["oos"]["outcomes"]["COMPLETE"] == fold["oos"]["metrics"]["samples"]


def test_failed_validation_keeps_trial(tmp_path):
    data = synthetic_dataset(n=100)
    with Store(tmp_path / "failed.db") as store:
        store.save_dataset(data)
        with pytest.raises(ValueError, match="Insufficient"):
            validate(store, data, Config())
        trial = store.db.execute("SELECT * FROM experiments").fetchone()
        assert trial["status"] == "FAILED"
        assert "Insufficient" in json.loads(trial["result"])["error"]
