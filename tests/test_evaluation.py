from dataclasses import replace

import pytest

from richping.core import Config
from richping.evaluation import block_ci, estimate, metrics, promotion_gate, risk_decision
from richping.validation import walk_forward_folds


def rows(values):
    return [{"session": f"{i:04d}", "net_return": x} for i, x in enumerate(values)]


def test_expectancy_prefers_economics_over_win_rate():
    high_win = metrics(rows([0.01] * 70 + [-0.04] * 30))
    lower_win = metrics(rows([0.08] * 45 + [-0.02] * 55))
    assert high_win["expectancy"] == pytest.approx(-0.005)
    assert lower_win["expectancy"] == pytest.approx(0.025)
    assert lower_win["expectancy"] > high_win["expectancy"]


def test_no_fake_portfolio_metrics():
    result = metrics(rows([0.03, -0.02]))
    assert result["sharpe"] is None
    assert result["portfolio_max_drawdown"] is None


def test_statistical_insufficiency_is_no_trade():
    result = estimate(rows([0.1] * 20), Config())
    assert not result["eligible"]
    assert result["expected_return"] is None


def test_all_wins_do_not_manufacture_risk():
    result = estimate(rows([0.1] * 100), Config())
    assert not result["eligible"]
    assert result["expected_loss"] is None


def test_positive_supported_edge_can_pass():
    result = estimate(rows([0.06, 0.04, -0.01] * 40), Config())
    assert result["eligible"]
    assert result["edge_ci"][0] > 0


def test_same_date_stocks_are_clustered():
    clustered = [{"session": "2024-01-02", "net_return": 0.1} for _ in range(100)]
    assert block_ci(clustered) is None
    assert not estimate(clustered, Config())["eligible"]


def test_bootstrap_is_reproducible():
    assert block_ci(rows([0.02, -0.01] * 40)) == block_ci(rows([0.02, -0.01] * 40))


def test_risk_reduction_and_pause_latch():
    assert risk_decision(rows([-0.001] * 30))[0] == "REDUCED_EXPOSURE"
    assert risk_decision(rows([-0.03] * 30))[0] == "PAUSED"
    assert risk_decision(rows([0.1] * 30), "PAUSED")[0] == "PAUSED"


def test_missing_promotion_evidence_is_rejection():
    assert promotion_gate({})["decision"] == "REJECT"
    assert "fresh_shadow" in promotion_gate({})["reasons"]


def test_nan_promotion_evidence_never_passes():
    assert "profit_factor" in promotion_gate({"profit_factor": float("nan")})["reasons"]


def test_time_splits_have_purge_and_disjoint_oos():
    folds = list(walk_forward_folds(1000))
    assert len(folds) > 1
    for f in folds:
        assert f.train_end - f.train_start + 1 == 504
        assert f.train_end + 21 < f.validation_start
        assert f.validation_end < f.oos_start
    assert folds[0].oos_end < folds[1].oos_start


@pytest.mark.parametrize("change", [{"top_k": 0}, {"horizon": 2}, {"min_edge": -1}, {"min_score": float("nan")}, {"tickers": ("AAPL", "AAPL")}])
def test_config_fails_closed(change):
    with pytest.raises(ValueError):
        replace(Config(), **change)
