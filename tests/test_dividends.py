"""Tests for Richping M2-1A: Ordinary cash dividend outcome calculations."""

from dataclasses import replace
from datetime import timedelta
import json
import sqlite3

import pytest

from richping.core import (
    CASH_ACTION_REVIEW_POLICY,
    DEFAULT_OUTCOME_VERSION,
    LEGACY_OUTCOME_VERSION,
    OUTCOME_VERSION_V1,
    OUTCOME_VERSION_V2,
    OUTCOME_VERSION_V3,
    SUPPORTED_OUTCOME_VERSIONS,
    VERIFIED_DIVIDEND_BASIS,
    Config,
    cutoff_at,
    next_sessions,
    sessions,
    timestamp,
)
from richping.data import (
    Bar,
    Dataset,
    create_action_capture,
    inspect_action_capture,
    static_members,
    synthetic_dataset,
)
from richping.engine import Engine, observe
from richping.evaluation import evaluate_outcome_eligibility, metrics, risk_decision
from richping.pipeline import format_report, scan, track
from richping.store import Store
from richping.validation import validate


def create_mini_dataset(bars_spec, metadata=None, action_capture=None, include_action_capture=False):
    """Helper to create a small deterministic dataset with verified dividend basis."""
    trading_days = sessions("2024-01-02", "2024-01-15")
    meta = {
        "source": "deterministic-test",
        "quality": "synthetic",
        "price_basis": "unadjusted-OHLC-actions-verified",
        "dividend_basis": VERIFIED_DIVIDEND_BASIS,
    }
    if metadata:
        meta.update(metadata)
    bars = []
    for spec in bars_spec:
        symbol = spec["ticker"]
        session = spec["session"]
        b = Bar(
            ticker=symbol,
            session=session,
            open=float(spec["open"]),
            high=float(spec["high"]),
            low=float(spec["low"]),
            close=float(spec["close"]),
            volume=float(spec.get("volume", 1_000_000)),
            known_at=cutoff_at(session).isoformat(),
            dividend=float(spec.get("dividend", 0.0)),
            split=float(spec.get("split", 0.0)),
        )
        bars.append(b)
    symbols = sorted({b.ticker for b in bars})
    members = static_members(symbols, trading_days[0], "2035-12-31", cutoff_at(trading_days[0]).isoformat())

    if action_capture is not None:
        meta["action_capture"] = action_capture
    elif include_action_capture:
        meta["action_capture"] = create_action_capture(
            adapter_version="yfinance-1.7.0",
            history_options={"actions": True, "auto_adjust": False, "back_adjust": False, "repair": False},
            captured_at=cutoff_at(trading_days[-1]).isoformat(),
            tickers_info={
                sym: {
                    "capital_gains_status": "present",
                    "instrument_type": "EQUITY",
                    "query_intervals": [{"start": trading_days[0], "end": trading_days[-1], "capital_gains_status": "present"}],
                    "quote_currency": "USD",
                }
                for sym in symbols
            },
            events=[],
        )

    return Dataset(bars, meta, members)


@pytest.fixture
def five_session_dates():
    # 2024-01-02 is Tuesday. Next 5 sessions: 01-03, 01-04, 01-05, 01-08, 01-09.
    return next_sessions("2024-01-02", 5)


def make_test_bars(symbol, dates, opens, closes, dividends=None, splits=None):
    divs = dividends or [0.0] * len(dates)
    spls = splits or [0.0] * len(dates)
    bars = []
    for d, o, c, div, sp in zip(dates, opens, closes, divs, spls):
        high = max(o, c) * 1.02
        low = min(o, c) * 0.98
        bars.append({
            "ticker": symbol, "session": d, "open": o, "high": high, "low": low,
            "close": c, "dividend": div, "split": sp,
        })
    return bars


def base_snapshot(session="2024-01-02", ticker="ALFA", entry_ref=100.0, cost=0.002, horizon=5, version=OUTCOME_VERSION_V2):
    return {
        "ticker": ticker,
        "session": session,
        "regime": "RISK_ON_LOW_VOL",
        "entry_reference": entry_ref,
        "stop_reference": entry_ref * 0.90,
        "target_reference": entry_ref * 1.15,
        "cost": cost,
        "holding_period": horizon,
        "cutoff": cutoff_at(session).isoformat(),
        "outcome_version": version,
    }


def v3_snapshot(session="2024-01-02", ticker="ALFA", entry_ref=100.0, cost=0.002, horizon=5):
    return base_snapshot(session=session, ticker=ticker, entry_ref=entry_ref, cost=cost, horizon=horizon, version=OUTCOME_VERSION_V3)


# --------------------------------------------------------------------------
# Scenario 1: No dividend -> Matches legacy price return & cost exactly
# --------------------------------------------------------------------------
def test_scenario_1_no_dividend(five_session_dates):
    # Entry session 01-03 open = 100.0, exit 01-09 close = 106.0.
    # Hand-calc:
    # price_return = 106.0 / 100.0 - 1 = +0.06 (+6.00%)
    # dividend_return = 0.0
    # raw_return = +0.06
    # net_return = 0.06 - 0.002 = +0.058 (+5.80%)
    dates = five_session_dates
    origin_bar = [{"ticker": "ALFA", "session": "2024-01-02", "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0}]
    holding_bars = make_test_bars("ALFA", dates, [100.0, 101.0, 102.0, 104.0, 105.0], [101.0, 102.0, 103.0, 105.0, 106.0])
    ds = create_mini_dataset(origin_bar + holding_bars)

    snap = base_snapshot()
    out = observe(snap, ds, 5, cutoff_at(dates[-1]).isoformat())
    assert out["status"] == "COMPLETE"
    assert out["outcome_version"] == OUTCOME_VERSION_V2
    assert out["entry_price"] == 100.0
    assert out["exit_price"] == 106.0
    assert out["price_return"] == pytest.approx(0.06)
    assert out["dividend_cash"] == 0.0
    assert out["dividend_return"] == 0.0
    assert out["raw_return"] == pytest.approx(0.06)
    assert out["net_return"] == pytest.approx(0.058)
    assert out["price_net_return"] == pytest.approx(0.058)


# --------------------------------------------------------------------------
# Scenario 2: Entry day ex-dividend -> Dividend NOT included
# --------------------------------------------------------------------------
def test_scenario_2_entry_day_ex_dividend_excluded(five_session_dates):
    # Entry session 01-03 (dates[0]) has dividend = 2.0.
    # Open = 100.0, Exit close = 105.0. Cost = 0.002.
    # Buyer bought at open (after ex-dividend cutoff). Dividend must NOT be included!
    # Hand-calc:
    # dividend_cash = 0.0
    # dividend_return = 0.0
    # entry_day_dividend_excluded = 2.0
    # price_return = 105.0 / 100.0 - 1 = +0.05 (+5.00%)
    # raw_return = 0.05
    # net_return = 0.05 - 0.002 = 0.048 (+4.80%)
    dates = five_session_dates
    origin_bar = [{"ticker": "ALFA", "session": "2024-01-02", "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0}]
    holding_bars = make_test_bars(
        "ALFA", dates,
        [100.0, 101.0, 102.0, 103.0, 104.0],
        [101.0, 102.0, 103.0, 104.0, 105.0],
        dividends=[2.0, 0.0, 0.0, 0.0, 0.0],
    )
    ds = create_mini_dataset(origin_bar + holding_bars)

    snap = base_snapshot()
    out = observe(snap, ds, 5, cutoff_at(dates[-1]).isoformat())
    assert out["status"] == "COMPLETE"
    assert out["entry_day_dividend_excluded"] == 2.0
    assert out["dividend_cash"] == 0.0
    assert out["dividend_return"] == 0.0
    assert out["price_return"] == pytest.approx(0.05)
    assert out["raw_return"] == pytest.approx(0.05)
    assert out["net_return"] == pytest.approx(0.048)


# --------------------------------------------------------------------------
# Scenario 3: Ex-dividend during holding period -> Eligible dividend included
# --------------------------------------------------------------------------
def test_scenario_3_holding_period_ex_dividend_included(five_session_dates):
    # Entry open = 100.0 on dates[0].
    # Dividend = 2.50 on dates[2] (01-05).
    # Exit close = 97.50 on dates[4] (01-09). Cost = 0.002.
    # Hand-calc:
    # dividend_cash = 2.50
    # dividend_return = 2.50 / 100.0 = +0.025 (+2.50%)
    # price_return = 97.50 / 100.0 - 1 = -0.025 (-2.50%)
    # raw_return = -0.025 + 0.025 = 0.0000 (0.00%)
    # net_return = 0.0 - 0.002 = -0.002 (-0.20%)
    # price_net_return = -0.025 - 0.002 = -0.027 (-2.70%)
    dates = five_session_dates
    origin_bar = [{"ticker": "ALFA", "session": "2024-01-02", "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0}]
    holding_bars = make_test_bars(
        "ALFA", dates,
        [100.0, 99.0, 97.0, 97.0, 97.0],
        [99.0, 98.0, 97.0, 97.0, 97.50],
        dividends=[0.0, 0.0, 2.50, 0.0, 0.0],
    )
    ds = create_mini_dataset(origin_bar + holding_bars)

    snap = base_snapshot()
    out = observe(snap, ds, 5, cutoff_at(dates[-1]).isoformat())
    assert out["status"] == "COMPLETE"
    assert out["dividend_cash"] == 2.50
    assert out["dividend_return"] == pytest.approx(0.025)
    assert out["price_return"] == pytest.approx(-0.025)
    assert out["raw_return"] == pytest.approx(0.0)
    assert out["net_return"] == pytest.approx(-0.002)
    assert out["price_net_return"] == pytest.approx(-0.027)


# --------------------------------------------------------------------------
# Scenario 4: Final day dividend & Multiple dividends accumulated correctly
# --------------------------------------------------------------------------
def test_scenario_4_final_day_and_multiple_dividends(five_session_dates):
    # Entry open = 100.0.
    # Dividend 1: 1.20 on dates[1] (01-04).
    # Dividend 2: 0.80 on dates[4] (01-09, final session).
    # Exit close = 103.00 on dates[4]. Cost = 0.002.
    # Hand-calc:
    # dividend_cash = 1.20 + 0.80 = 2.00
    # dividend_return = 2.00 / 100.0 = +0.020 (+2.00%)
    # price_return = 103.00 / 100.0 - 1 = +0.030 (+3.00%)
    # raw_return = +0.030 + 0.020 = +0.050 (+5.00%)
    # net_return = 0.050 - 0.002 = +0.048 (+4.80%)
    # price_net_return = 0.030 - 0.002 = +0.028 (+2.80%)
    dates = five_session_dates
    origin_bar = [{"ticker": "ALFA", "session": "2024-01-02", "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0}]
    holding_bars = make_test_bars(
        "ALFA", dates,
        [100.0, 101.0, 101.0, 102.0, 102.0],
        [101.0, 101.0, 102.0, 102.0, 103.00],
        dividends=[0.0, 1.20, 0.0, 0.0, 0.80],
    )
    ds = create_mini_dataset(origin_bar + holding_bars)

    snap = base_snapshot()
    out = observe(snap, ds, 5, cutoff_at(dates[-1]).isoformat())
    assert out["status"] == "COMPLETE"
    assert out["dividend_cash"] == pytest.approx(2.00)
    assert out["dividend_return"] == pytest.approx(0.020)
    assert out["price_return"] == pytest.approx(0.030)
    assert out["raw_return"] == pytest.approx(0.050)
    assert out["net_return"] == pytest.approx(0.048)
    assert out["price_net_return"] == pytest.approx(0.028)


# --------------------------------------------------------------------------
# Scenario 5: Price drop + dividend + cost -> Deducted once, no double count
# --------------------------------------------------------------------------
def test_scenario_5_price_drop_dividend_and_cost(five_session_dates):
    # Entry open = 50.0.
    # Dividend = 1.00 on dates[2].
    # Exit close = 42.50. Cost = 0.002.
    # Hand-calc:
    # price_return = 42.50 / 50.0 - 1 = -0.15 (-15.00%)
    # dividend_cash = 1.00
    # dividend_return = 1.00 / 50.0 = +0.02 (+2.00%)
    # raw_return = -0.15 + 0.02 = -0.13 (-13.00%)
    # net_return = -0.13 - 0.002 = -0.132 (-13.20%)
    # price_net_return = -0.15 - 0.002 = -0.152 (-15.20%)
    # Transaction cost deducted exactly once.
    dates = five_session_dates
    origin_bar = [{"ticker": "ALFA", "session": "2024-01-02", "open": 50.0, "high": 51.0, "low": 49.0, "close": 50.0}]
    holding_bars = make_test_bars(
        "ALFA", dates,
        [50.0, 48.0, 46.0, 44.0, 43.0],
        [48.0, 46.0, 44.0, 43.0, 42.50],
        dividends=[0.0, 0.0, 1.00, 0.0, 0.0],
    )
    ds = create_mini_dataset(origin_bar + holding_bars)

    snap = base_snapshot(entry_ref=50.0)
    out = observe(snap, ds, 5, cutoff_at(dates[-1]).isoformat())
    assert out["status"] == "COMPLETE"
    assert out["price_return"] == pytest.approx(-0.15)
    assert out["dividend_cash"] == pytest.approx(1.00)
    assert out["dividend_return"] == pytest.approx(0.02)
    assert out["raw_return"] == pytest.approx(-0.13)
    assert out["net_return"] == pytest.approx(-0.132)
    assert out["price_net_return"] == pytest.approx(-0.152)


# --------------------------------------------------------------------------
# Scenario 6: Point-in-time invariant: Future prices/dividends do not alter past
# --------------------------------------------------------------------------
def test_scenario_6_future_changes_preserve_point_in_time_invariants():
    ds_base = synthetic_dataset(n=400, dividend_basis=VERIFIED_DIVIDEND_BASIS)
    config = Config(tickers=("ALFA", "BETA", "GAMA", "DELT"), train_sessions=180)
    day = ds_base.sessions[300]

    # Mutate future bars: 5x price and dividends after day 300
    mutated_bars = [
        replace(b, open=b.open * 5, close=b.close * 5, high=b.high * 5, low=b.low * 5, dividend=1.5)
        if b.session > day else b for b in ds_base.bars
    ]
    ds_mutated = Dataset(mutated_bars, ds_base.metadata, ds_base.members)

    eng_base = Engine(ds_base, config)
    eng_mutated = Engine(ds_mutated, config)

    # Signals and calibration at session 300 must be 100% identical
    assert eng_base.signals(day) == eng_mutated.signals(day)
    for sig in eng_base.signals(day)["candidates"]:
        assert eng_base.calibration(sig) == eng_mutated.calibration(sig)


# --------------------------------------------------------------------------
# Scenario 7: Conservative handling: Splits, missing, unverified, irregular
# --------------------------------------------------------------------------
def test_scenario_7_splits_missing_unverified_fail_closed(five_session_dates):
    dates = five_session_dates
    origin_bar = [{"ticker": "ALFA", "session": "2024-01-02", "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0}]

    # Case A: Stock split in holding window -> UNRESOLVED (reason: stock_split_requires_accounting)
    bars_split = make_test_bars("ALFA", dates, [100.0] * 5, [100.0] * 5, splits=[0.0, 2.0, 0.0, 0.0, 0.0])
    ds_split = create_mini_dataset(origin_bar + bars_split)
    out_split = observe(base_snapshot(), ds_split, 5, cutoff_at(dates[-1]).isoformat())
    assert out_split["status"] == "UNRESOLVED"
    assert out_split["reason"] == "stock_split_requires_accounting"

    # Case B: Missing bar in window -> UNRESOLVED (missing_or_delisted_session)
    bars_missing = make_test_bars("ALFA", dates[:4], [100.0] * 4, [100.0] * 4)
    ds_missing = create_mini_dataset(origin_bar + bars_missing)
    out_missing = observe(base_snapshot(), ds_missing, 5, cutoff_at(dates[-1]).isoformat())
    assert out_missing["status"] == "UNRESOLVED"
    assert out_missing["reason"] == "missing_or_delisted_session"

    # Case C: Unverified dividend basis (e.g. metadata without verified dividend contract)
    bars_unverified = make_test_bars("ALFA", dates, [100.0] * 5, [100.0] * 5, dividends=[0.0, 1.0, 0.0, 0.0, 0.0])
    ds_unverified = create_mini_dataset(origin_bar + bars_unverified, metadata={"dividend_basis": None})
    out_unverified = observe(base_snapshot(), ds_unverified, 5, cutoff_at(dates[-1]).isoformat())
    assert out_unverified["status"] == "UNRESOLVED"
    assert out_unverified["reason"] == "unverified_dividend_basis"

    # Case D: Single dividend >= 20% of close price indicates special/irregular distribution
    bars_special = make_test_bars("ALFA", dates, [100.0] * 5, [100.0] * 5, dividends=[0.0, 25.0, 0.0, 0.0, 0.0])
    ds_special = create_mini_dataset(origin_bar + bars_special)
    out_special = observe(base_snapshot(), ds_special, 5, cutoff_at(dates[-1]).isoformat())
    assert out_special["status"] == "UNRESOLVED"
    assert out_special["reason"] == "special_or_irregular_dividend_requires_accounting"

    # Case E: Price vintage changed -> UNRESOLVED
    bars_clean = make_test_bars("ALFA", dates, [100.0] * 5, [100.0] * 5)
    ds_clean = create_mini_dataset(origin_bar + bars_clean)
    out_vintage = observe(base_snapshot(entry_ref=999.0), ds_clean, 5, cutoff_at(dates[-1]).isoformat())
    assert out_vintage["status"] == "UNRESOLVED"
    assert out_vintage["reason"] == "price_vintage_changed"


# --------------------------------------------------------------------------
# Scenario 8: Existing snapshots and records preserved & backward compatible
# --------------------------------------------------------------------------
def test_scenario_8_legacy_snapshots_and_records_preserved(five_session_dates, tmp_path):
    dates = five_session_dates
    origin_bar = [{"ticker": "ALFA", "session": "2024-01-02", "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0}]
    holding_bars_div = make_test_bars("ALFA", dates, [100.0] * 5, [105.0] * 5, dividends=[0.0, 1.0, 0.0, 0.0, 0.0])
    ds_div = create_mini_dataset(origin_bar + holding_bars_div)

    # Legacy snapshot without outcome_version field (defaults to v1)
    legacy_snap = base_snapshot(version=LEGACY_OUTCOME_VERSION)
    legacy_snap.pop("outcome_version", None)

    # Case A: Legacy snapshot with dividends in holding window -> UNRESOLVED under v1
    out_legacy = observe(legacy_snap, ds_div, 5, cutoff_at(dates[-1]).isoformat())
    assert out_legacy["status"] == "UNRESOLVED"
    assert out_legacy["reason"] == "corporate_action_requires_accounting"
    assert out_legacy["outcome_version"] == LEGACY_OUTCOME_VERSION

    # Case B: Legacy snapshot without dividends in holding window -> COMPLETE under v1
    holding_bars_clean = make_test_bars("ALFA", dates, [100.0] * 5, [105.0] * 5)
    ds_clean = create_mini_dataset(origin_bar + holding_bars_clean)
    out_legacy_clean = observe(legacy_snap, ds_clean, 5, cutoff_at(dates[-1]).isoformat())
    assert out_legacy_clean["status"] == "COMPLETE"
    assert out_legacy_clean["outcome_version"] == LEGACY_OUTCOME_VERSION
    assert out_legacy_clean["raw_return"] == pytest.approx(105.0 / 100.0 - 1)
    assert out_legacy_clean["net_return"] == pytest.approx(105.0 / 100.0 - 1 - legacy_snap["cost"])
    assert "dividend_cash" not in out_legacy_clean
    assert "price_net_return" not in out_legacy_clean

    # Case C: Pre-existing outcomes in Store and immutability triggers
    with Store(tmp_path / "legacy.db") as store:
        store.save_dataset(ds_clean)
        config = Config(tickers=("ALFA",), train_sessions=180)
        store.save_model(config)
        with store.db:
            store.db.execute(
                "INSERT INTO runs VALUES('run-legacy', ?, ?, '2024-01-02', 'research', 'SUCCEEDED', 1, NULL, NULL, ?)",
                (ds_clean.id, config.model_id, cutoff_at("2024-01-02").isoformat()),
            )
            store.db.execute(
                "INSERT INTO recommendations VALUES('rec-legacy', 'run-legacy', 'ALFA', 1, ?)",
                (json.dumps(legacy_snap),),
            )
            store.db.execute(
                "INSERT INTO outcomes VALUES('rec-legacy', 5, ?, 'COMPLETE', ?)",
                (ds_clean.id, json.dumps(out_legacy_clean)),
            )

        # Immutability triggers reject modifications
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            store.db.execute("UPDATE bars SET body='{}'")
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            store.db.execute("UPDATE recommendations SET snapshot='{}'")
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            store.db.execute("UPDATE outcomes SET body='{}'")

        # Re-running track() does not mutate pre-existing outcome
        counts, rows = track(store, ds_clean, cutoff_at(dates[-1]).isoformat())
        row = store.db.execute("SELECT status, body FROM outcomes WHERE recommendation_id='rec-legacy' AND horizon=5").fetchone()
        assert row["status"] == "COMPLETE"
        saved_body = json.loads(row["body"])
        assert saved_body["outcome_version"] == LEGACY_OUTCOME_VERSION
        assert saved_body["net_return"] == out_legacy_clean["net_return"]


# --------------------------------------------------------------------------
# Scenario 8B: Unsupported or unknown outcome versions fail-closed
# --------------------------------------------------------------------------
@pytest.mark.parametrize("bad_version", ["v999_future", "", None, "v1_price_only_typo"])
def test_unsupported_or_unknown_outcome_version_fails_closed(five_session_dates, tmp_path, bad_version):
    dates = five_session_dates
    origin_bar = [{"ticker": "ALFA", "session": "2024-01-02", "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0}]
    holding_bars = make_test_bars("ALFA", dates, [100.0] * 5, [105.0] * 5)
    ds = create_mini_dataset(origin_bar + holding_bars)

    snap = base_snapshot(version=bad_version)
    out = observe(snap, ds, 5, cutoff_at(dates[-1]).isoformat())
    assert out["status"] == "UNRESOLVED"
    assert out["reason"] == "unsupported_outcome_version"
    assert "raw_return" not in out
    assert "net_return" not in out

    # Verify track() excludes unsupported versions from performance statistics
    safe_name = f"bad_{bad_version or 'empty'}.db"
    with Store(tmp_path / safe_name) as store:
        store.save_dataset(ds)
        config = Config(tickers=("ALFA",), train_sessions=180)
        store.save_model(config)
        with store.db:
            store.db.execute(
                "INSERT INTO runs VALUES('run-bad', ?, ?, '2024-01-02', 'research', 'SUCCEEDED', 1, NULL, NULL, ?)",
                (ds.id, config.model_id, cutoff_at("2024-01-02").isoformat()),
            )
            store.db.execute(
                "INSERT INTO recommendations VALUES('rec-bad', 'run-bad', 'ALFA', 1, ?)",
                (json.dumps(snap),),
            )
        counts, rows = track(store, ds, cutoff_at(dates[-1]).isoformat())
        assert counts["UNRESOLVED"] >= 1
        assert counts["COMPLETE"] == 0
        assert len(rows) == 0, "Unsupported version must never enter completed evaluation rows"


# --------------------------------------------------------------------------
# Scenario 8C: Report formatting contract for legacy, current, and unsupported
# --------------------------------------------------------------------------
def test_report_outcome_contract_formatting():
    base_report = {
        "session": "2024-01-02",
        "quality": "research",
        "mode": "research",
        "regime": "RISK_ON_LOW_VOL",
        "state": "NORMAL",
        "state_reason": "ok",
        "model": "model-1",
        "decision": "NO TRADE",
        "reason": "insufficient_evidence_or_edge",
        "recommendations": [],
        "outcomes": {},
        "recent_30": {"samples": 0, "expectancy": None},
    }

    # 1. Missing outcome_contract defaults to OUTCOME_VERSION_V1 (v1_price_only)
    report_missing = dict(base_report)
    text_missing = format_report(report_missing)
    assert f"Outcome Contract: {OUTCOME_VERSION_V1}" in text_missing

    # 2. Explicit OUTCOME_VERSION_V3 (default)
    report_v3 = dict(base_report, outcome_contract=OUTCOME_VERSION_V3)
    text_v3 = format_report(report_v3)
    assert f"Outcome Contract: {OUTCOME_VERSION_V3}" in text_v3

    # 3. Explicit OUTCOME_VERSION_V2
    report_v2 = dict(base_report, outcome_contract=OUTCOME_VERSION_V2)
    text_v2 = format_report(report_v2)
    assert f"Outcome Contract: {OUTCOME_VERSION_V2}" in text_v2

    # 4. Explicit OUTCOME_VERSION_V1
    report_v1 = dict(base_report, outcome_contract=OUTCOME_VERSION_V1)
    text_v1 = format_report(report_v1)
    assert f"Outcome Contract: {OUTCOME_VERSION_V1}" in text_v1

    # 5. Unknown explicit outcome_contract displays unsupported
    report_bad = dict(base_report, outcome_contract="v999_experimental")
    text_bad = format_report(report_bad)
    assert "Outcome Contract: v999_experimental (unsupported)" in text_bad

    # 6. Empty or None explicit outcome_contract displays unsupported (empty)
    report_empty = dict(base_report, outcome_contract="")
    text_empty = format_report(report_empty)
    assert "Outcome Contract: unsupported (empty)" in text_empty

    report_none = dict(base_report, outcome_contract=None)
    text_none = format_report(report_none)
    assert "Outcome Contract: unsupported (empty)" in text_none


# --------------------------------------------------------------------------
# Scenario 9: Deterministic rerun & No duplicate outcome records
# --------------------------------------------------------------------------
def test_scenario_9_rerun_determinism_and_no_duplicate_records(five_session_dates, tmp_path):
    dates = five_session_dates
    origin_bar = [{"ticker": "ALFA", "session": "2024-01-02", "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0}]
    holding_bars = make_test_bars("ALFA", dates, [100.0] * 5, [105.0] * 5, dividends=[0.0, 1.0, 0.0, 0.0, 0.0])
    ds = create_mini_dataset(origin_bar + holding_bars)

    snap = base_snapshot()
    out1 = observe(snap, ds, 5, cutoff_at(dates[-1]).isoformat())
    out2 = observe(snap, ds, 5, cutoff_at(dates[-1]).isoformat())
    assert out1 == out2

    with Store(tmp_path / "rerun.db") as store:
        store.save_dataset(ds)
        config = Config(tickers=("ALFA",), train_sessions=180)
        store.save_model(config)
        with store.db:
            store.db.execute(
                "INSERT INTO runs VALUES('run-1', ?, ?, '2024-01-02', 'research', 'SUCCEEDED', 1, NULL, NULL, ?)",
                (ds.id, config.model_id, cutoff_at("2024-01-02").isoformat()),
            )
            store.db.execute(
                "INSERT INTO recommendations VALUES('rec-1', 'run-1', 'ALFA', 1, ?)",
                (json.dumps(snap),),
            )
        # First track pass
        counts1, rows1 = track(store, ds, cutoff_at(dates[-1]).isoformat())
        assert counts1["COMPLETE"] >= 1
        num_outcomes = store.db.execute("SELECT count(*) FROM outcomes").fetchone()[0]

        # Second track pass -> Must not duplicate outcomes
        counts2, rows2 = track(store, ds, cutoff_at(dates[-1]).isoformat())
        num_outcomes_after = store.db.execute("SELECT count(*) FROM outcomes").fetchone()[0]
        assert num_outcomes == num_outcomes_after
        assert len(rows1) == len(rows2)


# --------------------------------------------------------------------------
# Scenario 10: Consistency: Expectation estimation and evaluation share return definition
# --------------------------------------------------------------------------
def test_scenario_10_expectation_and_evaluation_consistency(tmp_path):
    # Deterministic integration test:
    # 1. Dataset deterministically produces candidate signals on session 2022-03-30.
    # 2. Candidate holding period contains an eligible ordinary cash dividend on 2022-04-01.
    # 3. Candidates exist (asserted unconditionally).
    # 4. Engine.history and track() evaluate the identical ticker/session/holding_period/version.
    # 5. Assert v2 net_return matches exactly between Engine.history and track().
    # 6. Verify cost and dividend are consistently and deterministically reflected in net_return.
    ds_base = synthetic_dataset(n=350, dividend_basis=VERIFIED_DIVIDEND_BASIS, seed=7)
    config = Config(tickers=("ALFA", "BETA", "GAMA", "DELT"), train_sessions=180)

    # ALFA has holding window 2022-03-31 to 2022-04-06 for signal on 2022-03-30.
    # Add ordinary cash dividend on 2022-04-01 (eligible, day 2 of holding period).
    div_amount = 1.50
    div_day = "2022-04-01"
    bars = [replace(b, dividend=div_amount) if b.ticker == "ALFA" and b.session == div_day else b
            for b in ds_base.bars]
    ds = Dataset(bars, ds_base.metadata, ds_base.members)

    target_session = "2022-03-30"
    engine = Engine(ds, config, outcome_version=OUTCOME_VERSION_V2)
    sigs = engine.signals(target_session)
    assert sigs["supported"] is True
    candidates = [c for c in sigs["candidates"] if c["ticker"] == "ALFA"]
    assert len(candidates) == 1, "ALFA must be deterministically generated as a candidate"
    cand = candidates[0]
    assert cand["outcome_version"] == OUTCOME_VERSION_V2
    assert cand["holding_period"] == config.horizon

    # 1. Find matching row from Engine.history
    hist_matches = [r for r in engine.history if r["session"] == target_session and r["ticker"] == "ALFA"]
    assert len(hist_matches) == 1, "Engine.history must contain ALFA candidate outcome"
    hist_row = hist_matches[0]
    assert hist_row["outcome_version"] == OUTCOME_VERSION_V2

    # 2. Save recommendation in Store and evaluate via track()
    with Store(tmp_path / "consistency.db") as store:
        store.save_dataset(ds)
        store.save_model(config)
        with store.db:
            store.db.execute(
                "INSERT INTO runs VALUES('run-1', ?, ?, ?, 'research', 'SUCCEEDED', 1, NULL, NULL, ?)",
                (ds.id, config.model_id, target_session, cutoff_at(target_session).isoformat()),
            )
            store.db.execute(
                "INSERT INTO recommendations VALUES('rec-1', 'run-1', 'ALFA', 1, ?)",
                (json.dumps(cand),),
            )

        as_of = cutoff_at(ds.end).isoformat()
        counts, track_rows = track(store, ds, as_of)
        assert counts["COMPLETE"] >= 1
        matching_track = [r for r in track_rows if r["session"] == target_session and r["ticker"] == "ALFA"]
        assert len(matching_track) == 0, "v2 candidate must be excluded from evaluation rows under cash_action_review_v1"
        assert counts["evaluation"]["excluded_complete"] >= 1
        assert counts["evaluation"]["by_reason"]["legacy_v2_unverified_contract"] >= 1
        assert counts["evaluation"]["by_version"][OUTCOME_VERSION_V2] >= 1

        # Verify preserved v2 outcome in Store
        db_out = store.db.execute("SELECT status, body FROM outcomes WHERE recommendation_id='rec-1' AND horizon=5").fetchone()
        assert db_out["status"] == "COMPLETE"
        stored_row = json.loads(db_out["body"])

    # 3. Verify identical attributes on preserved v2 outcome
    assert hist_row["ticker"] == "ALFA"
    assert hist_row["session"] == target_session
    assert stored_row["end_session"] == hist_row["end_session"] == "2022-04-06"
    assert stored_row["outcome_version"] == hist_row["outcome_version"] == OUTCOME_VERSION_V2

    # 4. Direct comparison of net_return between Engine.history and stored v2 outcome
    assert hist_row["net_return"] == pytest.approx(stored_row["net_return"])

    # 5. Verify consistent reflection of both dividend and transaction cost
    assert stored_row["dividend_cash"] == pytest.approx(div_amount)
    assert stored_row["dividend_return"] > 0
    assert stored_row["cost"] == pytest.approx(config.cost)
    expected_net = stored_row["price_return"] + stored_row["dividend_return"] - config.cost
    assert stored_row["net_return"] == pytest.approx(expected_net)
    assert hist_row["net_return"] == pytest.approx(expected_net)

    # 6. Verify calibration calculation
    cal = engine.calibration(cand, boundary=ds.sessions[ds.positions["2022-04-06"] + 25])
    assert "expected_return" in cal


# ============================================================================
# M2-1A-R2-2: Section 6 Required v3 Tests (Items 1 to 15)
# ============================================================================

# Item 1: Backward compatibility: Explicit v1 and v2 match pre-change arithmetic
def test_v3_item01_explicit_v1_and_v2_match_pre_change_fixtures(five_session_dates):
    dates = five_session_dates
    origin_bar = [{"ticker": "ALFA", "session": "2024-01-02", "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0}]

    # Case A: Dataset with cash dividend
    # v1 rejects any dividend -> UNRESOLVED, corporate_action_requires_accounting
    # v2 accepts verified dividend -> COMPLETE, raw_return = price_return + dividend_return
    holding_bars_div = make_test_bars("ALFA", dates, [100.0] * 5, [106.0] * 5, dividends=[0.0, 1.5, 0.0, 0.0, 0.0])
    ds_div = create_mini_dataset(origin_bar + holding_bars_div, include_action_capture=True)

    snap_v1 = base_snapshot(version=OUTCOME_VERSION_V1)
    out_v1_div = observe(snap_v1, ds_div, 5, cutoff_at(dates[-1]).isoformat())
    assert out_v1_div["status"] == "UNRESOLVED"
    assert out_v1_div["reason"] == "corporate_action_requires_accounting"

    snap_v2 = base_snapshot(version=OUTCOME_VERSION_V2)
    out_v2_div = observe(snap_v2, ds_div, 5, cutoff_at(dates[-1]).isoformat())
    assert out_v2_div["status"] == "COMPLETE"
    assert out_v2_div["outcome_version"] == OUTCOME_VERSION_V2
    assert out_v2_div["dividend_return"] == pytest.approx(1.5 / 100.0)
    assert out_v2_div["price_return"] == pytest.approx(0.06)
    assert out_v2_div["net_return"] == pytest.approx(0.06 + 0.015 - 0.002)

    # Case B: Event-free dataset
    # Both v1 and v2 compute pure price return
    holding_bars_clean = make_test_bars("ALFA", dates, [100.0] * 5, [106.0] * 5)
    ds_clean = create_mini_dataset(origin_bar + holding_bars_clean, include_action_capture=True)

    out_v1_clean = observe(snap_v1, ds_clean, 5, cutoff_at(dates[-1]).isoformat())
    assert out_v1_clean["status"] == "COMPLETE"
    assert out_v1_clean["raw_return"] == pytest.approx(0.06)
    assert out_v1_clean["net_return"] == pytest.approx(0.06 - 0.002)

    out_v2_clean = observe(snap_v2, ds_clean, 5, cutoff_at(dates[-1]).isoformat())
    assert out_v2_clean["status"] == "COMPLETE"
    assert out_v2_clean["raw_return"] == pytest.approx(0.06)
    assert out_v2_clean["dividend_return"] == 0.0


# Item 2: Version resolution: Missing defaults to v1; unsupported becomes UNRESOLVED
def test_v3_item02_version_resolution_missing_and_unsupported(five_session_dates):
    dates = five_session_dates
    origin_bar = [{"ticker": "ALFA", "session": "2024-01-02", "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0}]
    holding_bars = make_test_bars("ALFA", dates, [100.0] * 5, [105.0] * 5)
    ds = create_mini_dataset(origin_bar + holding_bars, include_action_capture=True)

    # Missing outcome_version defaults to OUTCOME_VERSION_V1
    snap_missing = base_snapshot()
    del snap_missing["outcome_version"]
    out_missing = observe(snap_missing, ds, 5, cutoff_at(dates[-1]).isoformat())
    assert out_missing["status"] == "COMPLETE"
    assert out_missing["outcome_version"] == OUTCOME_VERSION_V1

    # Unsupported version returns UNRESOLVED with unsupported_outcome_version
    snap_bad = base_snapshot(version="v999_future_spec")
    out_bad = observe(snap_bad, ds, 5, cutoff_at(dates[-1]).isoformat())
    assert out_bad["status"] == "UNRESOLVED"
    assert out_bad["reason"] == "unsupported_outcome_version"


# Item 3: Event-free complete capture: Pure price return and single cost deduction
def test_v3_item03_event_free_complete_capture_price_return(five_session_dates):
    dates = five_session_dates
    origin_bar = [{"ticker": "ALFA", "session": "2024-01-02", "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0}]
    holding_bars = make_test_bars("ALFA", dates, [100.0] * 5, [108.0] * 5)
    ds = create_mini_dataset(origin_bar + holding_bars, include_action_capture=True)

    snap = v3_snapshot()
    out = observe(snap, ds, 5, cutoff_at(dates[-1]).isoformat())
    assert out["status"] == "COMPLETE"
    assert out["outcome_version"] == OUTCOME_VERSION_V3
    assert out["return_basis"] == "price_only_unadjusted_cash_dividends"
    assert out["price_return"] == pytest.approx(0.08)
    assert out["raw_return"] == pytest.approx(0.08)
    assert out["cost"] == pytest.approx(0.002)
    assert out["net_return"] == pytest.approx(0.08 - 0.002)
    assert "dividend_return" not in out


# Item 4: Dividend blocked at all scales and holding window sessions
@pytest.mark.parametrize("div_amount,session_idx", [
    (0.01, 1),
    (15.0, 1),
    (0.50, 0),
    (0.50, 4),
])
def test_v3_item04_dividend_blocked_at_all_scales_and_sessions(five_session_dates, div_amount, session_idx):
    dates = five_session_dates
    origin_bar = [{"ticker": "ALFA", "session": "2024-01-02", "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0}]
    divs = [0.0] * 5
    divs[session_idx] = div_amount
    holding_bars = make_test_bars("ALFA", dates, [100.0] * 5, [105.0] * 5, dividends=divs)
    ds = create_mini_dataset(origin_bar + holding_bars, include_action_capture=True)

    snap = v3_snapshot()
    out = observe(snap, ds, 5, cutoff_at(dates[-1]).isoformat())
    assert out["status"] == "UNRESOLVED"
    assert out["reason"] == "unverified_cash_dividend_event"


# Item 5: Legacy basis and synthetic quality cannot bypass v3 dividend guard
def test_v3_item05_legacy_basis_and_synthetic_quality_cannot_bypass(five_session_dates):
    dates = five_session_dates
    origin_bar = [{"ticker": "ALFA", "session": "2024-01-02", "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0}]
    holding_bars = make_test_bars("ALFA", dates, [100.0] * 5, [105.0] * 5, dividends=[0.0, 1.0, 0.0, 0.0, 0.0])
    ds = create_mini_dataset(origin_bar + holding_bars, metadata={"quality": "synthetic", "dividend_basis": VERIFIED_DIVIDEND_BASIS}, include_action_capture=True)

    snap = v3_snapshot()
    out = observe(snap, ds, 5, cutoff_at(dates[-1]).isoformat())
    assert out["status"] == "UNRESOLVED"
    assert out["reason"] == "unverified_cash_dividend_event"


# Item 6: Capital Gains event alone and priority over cash dividend
def test_v3_item06_capital_gains_event_and_priority_over_dividend(five_session_dates):
    dates = five_session_dates
    origin_bar = [{"ticker": "ALFA", "session": "2024-01-02", "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0}]

    # Case A: Capital Gains alone in holding window
    holding_bars_a = make_test_bars("ALFA", dates, [100.0] * 5, [105.0] * 5)
    ds_a = create_mini_dataset(origin_bar + holding_bars_a, include_action_capture=True)
    cap_a = dict(ds_a.metadata["action_capture"])
    cap_a["events"] = [{
        "ticker": "ALFA", "session": dates[2], "field": "Capital Gains", "amount": 1.25, "known_at": cutoff_at(dates[-1]).isoformat()
    }]
    ds_a = Dataset(ds_a.bars, {**ds_a.metadata, "action_capture": cap_a}, ds_a.members)

    snap = v3_snapshot()
    out_a = observe(snap, ds_a, 5, cutoff_at(dates[-1]).isoformat())
    assert out_a["status"] == "UNRESOLVED"
    assert out_a["reason"] == "unsupported_capital_gains_distribution"

    # Case B: Concurrent Capital Gains AND cash dividend -> Priority 2 (CG) > Priority 3 (dividend)
    holding_bars_b = make_test_bars("ALFA", dates, [100.0] * 5, [105.0] * 5, dividends=[0.0, 0.5, 0.0, 0.0, 0.0])
    ds_b = create_mini_dataset(origin_bar + holding_bars_b, include_action_capture=True)
    cap_b = dict(ds_b.metadata["action_capture"])
    cap_b["events"] = [{
        "ticker": "ALFA", "session": dates[1], "field": "Capital Gains", "amount": 0.80, "known_at": cutoff_at(dates[-1]).isoformat()
    }]
    ds_b = Dataset(ds_b.bars, {**ds_b.metadata, "action_capture": cap_b}, ds_b.members)

    out_b = observe(snap, ds_b, 5, cutoff_at(dates[-1]).isoformat())
    assert out_b["status"] == "UNRESOLVED"
    assert out_b["reason"] == "unsupported_capital_gains_distribution"


# Item 7: Split priority over Capital Gains and cash dividend
def test_v3_item07_split_priority_over_capital_gains_and_dividend(five_session_dates):
    dates = five_session_dates
    origin_bar = [{"ticker": "ALFA", "session": "2024-01-02", "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0}]
    holding_bars = make_test_bars("ALFA", dates, [100.0] * 5, [105.0] * 5, dividends=[0.0, 0.5, 0.0, 0.0, 0.0], splits=[0.0, 2.0, 0.0, 0.0, 0.0])
    ds = create_mini_dataset(origin_bar + holding_bars, include_action_capture=True)
    cap = dict(ds.metadata["action_capture"])
    cap["events"] = [{
        "ticker": "ALFA", "session": dates[1], "field": "Capital Gains", "amount": 0.80, "known_at": cutoff_at(dates[-1]).isoformat()
    }]
    ds = Dataset(ds.bars, {**ds.metadata, "action_capture": cap}, ds.members)

    snap = v3_snapshot()
    out = observe(snap, ds, 5, cutoff_at(dates[-1]).isoformat())
    assert out["status"] == "UNRESOLVED"
    assert out["reason"] == "stock_split_requires_accounting"


# Item 8: Action capture unknown reasons
def test_v3_item08_action_capture_unknown_reasons(five_session_dates):
    dates = five_session_dates
    origin_bar = [{"ticker": "ALFA", "session": "2024-01-02", "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0}]
    holding_bars = make_test_bars("ALFA", dates, [100.0] * 5, [105.0] * 5)
    snap = v3_snapshot()
    as_of = cutoff_at(dates[-1]).isoformat()

    # 1. No capture in dataset
    ds_no_cap = create_mini_dataset(origin_bar + holding_bars, include_action_capture=False)
    assert observe(snap, ds_no_cap, 5, as_of)["reason"] == "action_capture_unknown"

    # 2. Ticker missing from capture tickers
    ds_base = create_mini_dataset(origin_bar + holding_bars, include_action_capture=True)
    cap_missing_ticker = dict(ds_base.metadata["action_capture"])
    cap_missing_ticker["tickers"] = {}
    ds_missing_ticker = Dataset(ds_base.bars, {**ds_base.metadata, "action_capture": cap_missing_ticker}, ds_base.members)
    assert observe(snap, ds_missing_ticker, 5, as_of)["reason"] == "action_capture_unknown"

    # 3. Interval status is "unknown"
    cap_unknown_st = dict(ds_base.metadata["action_capture"])
    cap_unknown_st["tickers"] = {
        "ALFA": {
            "capital_gains_status": "unknown",
            "instrument_type": "EQUITY",
            "query_intervals": [{"start": dates[0], "end": dates[-1], "capital_gains_status": "unknown"}],
            "quote_currency": "USD",
        }
    }
    ds_unknown_st = Dataset(ds_base.bars, {**ds_base.metadata, "action_capture": cap_unknown_st}, ds_base.members)
    assert observe(snap, ds_unknown_st, 5, as_of)["reason"] == "action_capture_unknown"

    # 4. Insufficient interval range (ends early)
    cap_short = dict(ds_base.metadata["action_capture"])
    cap_short["tickers"] = {
        "ALFA": {
            "capital_gains_status": "present",
            "instrument_type": "EQUITY",
            "query_intervals": [{"start": dates[0], "end": dates[2], "capital_gains_status": "present"}],
            "quote_currency": "USD",
        }
    }
    ds_short = Dataset(ds_base.bars, {**ds_base.metadata, "action_capture": cap_short}, ds_base.members)
    assert observe(snap, ds_short, 5, as_of)["reason"] == "action_capture_unknown"

    # 5. Gap between intervals in holding window
    cap_gap = dict(ds_base.metadata["action_capture"])
    cap_gap["tickers"] = {
        "ALFA": {
            "capital_gains_status": "present",
            "instrument_type": "EQUITY",
            "query_intervals": [
                {"start": dates[0], "end": dates[1], "capital_gains_status": "present"},
                {"start": dates[3], "end": dates[-1], "capital_gains_status": "present"},
            ],
            "quote_currency": "USD",
        }
    }
    ds_gap = Dataset(ds_base.bars, {**ds_base.metadata, "action_capture": cap_gap}, ds_base.members)
    assert observe(snap, ds_gap, 5, as_of)["reason"] == "action_capture_unknown"


# Item 9: Events outside window and on other tickers are isolated
def test_v3_item09_events_outside_window_or_on_other_tickers_isolated(five_session_dates):
    dates = five_session_dates
    origin_bar = [{"ticker": "ALFA", "session": "2024-01-02", "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0, "dividend": 2.0}]
    holding_bars = make_test_bars("ALFA", dates, [100.0] * 5, [105.0] * 5)
    after_bar = [{"ticker": "ALFA", "session": "2024-01-10", "open": 105.0, "high": 106.0, "low": 104.0, "close": 105.0, "dividend": 3.0}]
    beta_bars = make_test_bars("BETA", dates, [50.0] * 5, [50.0] * 5, splits=[0.0, 2.0, 0.0, 0.0, 0.0])

    ds = create_mini_dataset(origin_bar + holding_bars + after_bar + beta_bars, include_action_capture=True)
    cap = dict(ds.metadata["action_capture"])
    cap["events"] = [{
        "ticker": "BETA", "session": dates[2], "field": "Capital Gains", "amount": 1.50, "known_at": cutoff_at(dates[-1]).isoformat()
    }]
    ds = Dataset(ds.bars, {**ds.metadata, "action_capture": cap}, ds.members)

    snap = v3_snapshot()
    out = observe(snap, ds, 5, cutoff_at(dates[-1]).isoformat())
    assert out["status"] == "COMPLETE"
    assert out["outcome_version"] == OUTCOME_VERSION_V3
    assert out["price_return"] == pytest.approx(0.05)


# Item 10: Shadow mode future events and capture return PENDING data_not_yet_known
def test_v3_item10_shadow_mode_future_events_and_capture_pending(five_session_dates):
    dates = five_session_dates
    origin_bar = [{"ticker": "ALFA", "session": "2024-01-02", "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0}]
    holding_bars = make_test_bars("ALFA", dates, [100.0] * 5, [105.0] * 5)
    as_of = cutoff_at(dates[-1]).isoformat()
    as_of_dt = timestamp(as_of)
    future_time = (as_of_dt + timedelta(days=1)).isoformat()

    # Case A: Future capture timestamp
    ds_a = create_mini_dataset(origin_bar + holding_bars, include_action_capture=True)
    cap_a = dict(ds_a.metadata["action_capture"])
    cap_a["captured_at"] = future_time
    ds_a = Dataset(ds_a.bars, {**ds_a.metadata, "action_capture": cap_a}, ds_a.members)

    snap = v3_snapshot()
    out_a = observe(snap, ds_a, 5, as_of, mode="shadow")
    assert out_a["status"] == "PENDING"
    assert out_a["reason"] == "data_not_yet_known"

    # Case B: Event with future known_at
    ds_b = create_mini_dataset(origin_bar + holding_bars, include_action_capture=True)
    cap_b = dict(ds_b.metadata["action_capture"])
    cap_b["events"] = [{
        "ticker": "ALFA", "session": dates[2], "field": "Capital Gains", "amount": 0.50, "known_at": future_time
    }]
    ds_b = Dataset(ds_b.bars, {**ds_b.metadata, "action_capture": cap_b}, ds_b.members)

    out_b = observe(snap, ds_b, 5, as_of, mode="shadow")
    assert out_b["status"] == "PENDING"
    assert out_b["reason"] == "data_not_yet_known"

    # Case C: Research mode permits historical access (does not pend for known_at)
    out_c = observe(snap, ds_b, 5, as_of, mode="research")
    assert out_c["status"] == "UNRESOLVED"
    assert out_c["reason"] == "unsupported_capital_gains_distribution"


# Item 11: Candidate and SPY/QQQ feature window blocking
def test_v3_item11_engine_signals_feature_window_blocking():
    ds_base = synthetic_dataset(n=200, seed=42)
    config = Config(tickers=("ALFA", "BETA"), train_sessions=120)
    target_session = ds_base.sessions[100]

    # Case A: Candidate ALFA has corporate action in feature window -> ALFA excluded
    bars_alfa_div = [replace(b, dividend=1.0) if b.ticker == "ALFA" and b.session == ds_base.sessions[90] else b
                     for b in ds_base.bars]
    ds_alfa_div = Dataset(bars_alfa_div, ds_base.metadata, ds_base.members)
    engine_alfa = Engine(ds_alfa_div, config)
    sigs_alfa = engine_alfa.signals(target_session)
    assert "ALFA" in sigs_alfa["excluded"]
    assert sigs_alfa["excluded"]["ALFA"] == "corporate_action_in_feature_window"

    # Case B: Benchmark SPY has dividend in feature window -> Engine.signals() raises ValueError (fail closed)
    bars_spy_div = [replace(b, dividend=1.0) if b.ticker == "SPY" and b.session == ds_base.sessions[90] else b
                    for b in ds_base.bars]
    ds_spy_div = Dataset(bars_spy_div, ds_base.metadata, ds_base.members)
    engine_spy = Engine(ds_spy_div, config)
    with pytest.raises(ValueError, match="Corporate action in SPY benchmark history"):
        engine_spy.signals(target_session)


# Item 12: Event-free candidate has exact net_return match between Engine.history and track()
def test_v3_item12_engine_history_and_track_exact_consistency_event_free(tmp_path):
    ds = synthetic_dataset(n=350, seed=7)
    config = Config(tickers=("ALFA", "BETA", "GAMA", "DELT"), train_sessions=180)
    target_session = "2022-03-30"

    engine = Engine(ds, config, outcome_version=OUTCOME_VERSION_V3)
    sigs = engine.signals(target_session)
    assert sigs["supported"] is True
    candidates = [c for c in sigs["candidates"] if c["ticker"] == "ALFA"]
    assert len(candidates) == 1
    cand = candidates[0]
    assert cand["outcome_version"] == OUTCOME_VERSION_V3

    hist_matches = [r for r in engine.history if r["session"] == target_session and r["ticker"] == "ALFA"]
    assert len(hist_matches) == 1
    hist_row = hist_matches[0]
    assert hist_row["outcome_version"] == OUTCOME_VERSION_V3

    with Store(tmp_path / "consistency_v3.db") as store:
        store.save_dataset(ds)
        store.save_model(config)
        with store.db:
            store.db.execute(
                "INSERT INTO runs VALUES('run-v3', ?, ?, ?, 'research', 'SUCCEEDED', 1, NULL, NULL, ?)",
                (ds.id, config.model_id, target_session, cutoff_at(target_session).isoformat()),
            )
            store.db.execute(
                "INSERT INTO recommendations VALUES('rec-v3', 'run-v3', 'ALFA', 1, ?)",
                (json.dumps(cand),),
            )
        as_of = cutoff_at(ds.end).isoformat()
        counts, track_rows = track(store, ds, as_of)
        assert counts["COMPLETE"] >= 1
        matching_track = [r for r in track_rows if r["session"] == target_session and r["ticker"] == "ALFA"]
        assert len(matching_track) == 1
        track_row = matching_track[0]

    assert track_row["net_return"] == pytest.approx(hist_row["net_return"])
    assert track_row["outcome_version"] == OUTCOME_VERSION_V3
    assert track_row["cost"] == pytest.approx(config.cost)
    assert track_row["price_return"] - config.cost == pytest.approx(track_row["net_return"])


# Item 13: Candidate with holding period action excluded from Engine.history and in track() UNRESOLVED denominator
def test_v3_item13_holding_period_action_excluded_from_history_and_in_unresolved_denominator(tmp_path):
    ds_base = synthetic_dataset(n=350, seed=7)
    config = Config(tickers=("ALFA", "BETA", "GAMA", "DELT"), train_sessions=180)
    target_session = "2022-03-30"

    # Add dividend on 2022-04-01 during ALFA holding period
    bars = [replace(b, dividend=1.0) if b.ticker == "ALFA" and b.session == "2022-04-01" else b
            for b in ds_base.bars]
    ds = Dataset(bars, ds_base.metadata, ds_base.members)

    engine = Engine(ds, config, outcome_version=OUTCOME_VERSION_V3)
    sigs = engine.signals(target_session)
    candidates = [c for c in sigs["candidates"] if c["ticker"] == "ALFA"]
    assert len(candidates) == 1
    cand = candidates[0]
    assert cand["outcome_version"] == OUTCOME_VERSION_V3

    # Excluded from Engine.history and recorded in excluded_history
    hist_matches = [r for r in engine.history if r["session"] == target_session and r["ticker"] == "ALFA"]
    assert len(hist_matches) == 0, "Non-COMPLETE outcome must be excluded from Engine.history"

    ex_matches = [r for r in engine.excluded_history if r["session"] == target_session and r["ticker"] == "ALFA"]
    assert len(ex_matches) == 1
    assert ex_matches[0]["status"] == "UNRESOLVED"
    assert ex_matches[0]["reason"] == "unverified_cash_dividend_event"

    # In track(), recorded as UNRESOLVED and remains in denominator
    with Store(tmp_path / "action_unresolved.db") as store:
        store.save_dataset(ds)
        store.save_model(config)
        with store.db:
            store.db.execute(
                "INSERT INTO runs VALUES('run-ex', ?, ?, ?, 'research', 'SUCCEEDED', 1, NULL, NULL, ?)",
                (ds.id, config.model_id, target_session, cutoff_at(target_session).isoformat()),
            )
            store.db.execute(
                "INSERT INTO recommendations VALUES('rec-ex', 'run-ex', 'ALFA', 1, ?)",
                (json.dumps(cand),),
            )
        as_of = cutoff_at(ds.end).isoformat()
        counts, track_rows = track(store, ds, as_of)
        # Candidate holding period is 5; with dividend in holding window, no complete row is produced
        assert len(track_rows) == 0, "Candidate with action in holding window must not appear in completed track rows"
        assert counts["UNRESOLVED"] >= 1
        db_out = store.db.execute("SELECT status, body FROM outcomes WHERE recommendation_id='rec-ex' AND horizon=5").fetchone()
        assert db_out[0] == "UNRESOLVED"
        res_json = json.loads(db_out[1])
        assert res_json["reason"] == "unverified_cash_dividend_event"


# Item 14: Future price, dividend, and Capital Gains mutations do not leak into past features/calibration
def test_v3_item14_future_price_and_action_leakage_prevented():
    ds_base = synthetic_dataset(n=350, seed=7)
    config = Config(tickers=("ALFA", "BETA", "GAMA", "DELT"), train_sessions=180)
    target_session = ds_base.sessions[200]

    engine_base = Engine(ds_base, config, outcome_version=OUTCOME_VERSION_V3)
    sigs_base = engine_base.signals(target_session)
    cand_base = [c for c in sigs_base["candidates"] if c["ticker"] == "ALFA"][0]
    cal_base = engine_base.calibration(cand_base, boundary=target_session)

    # Mutate future sessions (strictly after target_session): change prices, add splits, dividends, CG events
    future_sessions = set(ds_base.sessions[201:])
    mutated_bars = []
    for b in ds_base.bars:
        if b.session in future_sessions:
            mutated_bars.append(replace(b, open=b.open * 2, high=b.high * 2, low=b.low * 2, close=b.close * 2,
                                        dividend=5.0, split=2.0))
        else:
            mutated_bars.append(b)

    cap_mut = dict(ds_base.metadata["action_capture"])
    cap_mut["events"] = [{
        "ticker": "ALFA", "session": ds_base.sessions[250], "field": "Capital Gains", "amount": 10.0,
        "known_at": cutoff_at(ds_base.sessions[250]).isoformat()
    }]
    ds_mut = Dataset(mutated_bars, {**ds_base.metadata, "action_capture": cap_mut}, ds_base.members)

    engine_mut = Engine(ds_mut, config, outcome_version=OUTCOME_VERSION_V3)
    sigs_mut = engine_mut.signals(target_session)
    cand_mut = [c for c in sigs_mut["candidates"] if c["ticker"] == "ALFA"][0]
    cal_mut = engine_mut.calibration(cand_mut, boundary=target_session)

    assert cand_base["score"] == pytest.approx(cand_mut["score"])
    assert cand_base["features"] == cand_mut["features"]
    assert cal_base["samples"] == cal_mut["samples"]
    assert cal_base["expected_return"] == pytest.approx(cal_mut["expected_return"])


# Item 15: Existing dataset/snapshot/outcomes immutability and rerun idempotency in Store
def test_v3_item15_immutability_and_rerun_idempotency_in_store(tmp_path, five_session_dates):
    dates = five_session_dates
    origin_bar = [{"ticker": "ALFA", "session": "2024-01-02", "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0}]
    holding_bars = make_test_bars("ALFA", dates, [100.0] * 5, [105.0] * 5)
    ds = create_mini_dataset(origin_bar + holding_bars, include_action_capture=True)
    config = Config(tickers=("ALFA",), train_sessions=180)

    snap = v3_snapshot()
    snap_json_before = json.dumps(snap, sort_keys=True)

    with Store(tmp_path / "idempotency_v3.db") as store:
        store.save_dataset(ds)
        store.save_model(config)
        with store.db:
            store.db.execute(
                "INSERT INTO runs VALUES('run-15', ?, ?, ?, 'research', 'SUCCEEDED', 1, NULL, NULL, ?)",
                (ds.id, config.model_id, "2024-01-02", cutoff_at("2024-01-02").isoformat()),
            )
            store.db.execute(
                "INSERT INTO recommendations VALUES('rec-15', 'run-15', 'ALFA', 1, ?)",
                (json.dumps(snap),),
            )

        as_of = cutoff_at(dates[-1]).isoformat()
        counts1, rows1 = track(store, ds, as_of)
        assert counts1["COMPLETE"] >= 1
        assert len(rows1) == 1
        num_outcomes1 = store.db.execute("SELECT count(*) FROM outcomes").fetchone()[0]
        assert num_outcomes1 >= 1

        # Verify recommendation snapshot immutability
        snap_in_db = store.db.execute("SELECT snapshot FROM recommendations WHERE id='rec-15'").fetchone()[0]
        assert json.dumps(json.loads(snap_in_db), sort_keys=True) == snap_json_before

        # Run track() second time: idempotent, no duplicate outcome records
        counts2, rows2 = track(store, ds, as_of)
        num_outcomes2 = store.db.execute("SELECT count(*) FROM outcomes").fetchone()[0]
        assert num_outcomes1 == num_outcomes2
        assert len(rows1) == len(rows2)
        assert rows1[0]["net_return"] == rows2[0]["net_return"]


# ============================================================================
# M2-1A-R2-2-R1: Synthetic shadow point-in-time action_capture inspection tests
# ============================================================================

def test_r2_2_r1_case1_synthetic_shadow_future_captured_at_pending():
    """Case 1: captured_at > as_of + event-free complete coverage.
    observe(mode='shadow') must return PENDING / data_not_yet_known without any return fields.
    """
    ds = synthetic_dataset(n=30, symbols=("ALFA", "BETA"), seed=42)
    session = ds.sessions[10]
    holding_sessions = next_sessions(session, 5)
    as_of = cutoff_at(holding_sessions[-1]).isoformat()
    future_time = (timestamp(as_of) + timedelta(days=2)).isoformat()

    cap = dict(ds.metadata["action_capture"])
    cap["captured_at"] = future_time
    ds_future = Dataset(ds.bars, {**ds.metadata, "action_capture": cap}, ds.members)

    origin_bar = ds.by_ticker["ALFA"][session]
    snap = v3_snapshot(session=session, ticker="ALFA", entry_ref=origin_bar.close)

    out = observe(snap, ds_future, 5, as_of=as_of, mode="shadow")
    assert out["status"] == "PENDING"
    assert out["reason"] == "data_not_yet_known"
    assert "raw_return" not in out
    assert "net_return" not in out
    assert "price_return" not in out
    assert "price_net_return" not in out


def test_r2_2_r1_case2_synthetic_shadow_equal_captured_at_complete():
    """Case 2: captured_at == as_of + event-free complete coverage.
    observe(mode='shadow') must return COMPLETE with hand-calculated exact return.
    """
    ds = synthetic_dataset(n=30, symbols=("ALFA", "BETA"), seed=42)
    session = ds.sessions[10]
    holding_sessions = next_sessions(session, 5)
    as_of = cutoff_at(holding_sessions[-1]).isoformat()

    cap = dict(ds.metadata["action_capture"])
    cap["captured_at"] = as_of
    ds_eq = Dataset(ds.bars, {**ds.metadata, "action_capture": cap}, ds.members)

    origin_bar = ds.by_ticker["ALFA"][session]
    snap = v3_snapshot(session=session, ticker="ALFA", entry_ref=origin_bar.close)

    out = observe(snap, ds_eq, 5, as_of=as_of, mode="shadow")
    assert out["status"] == "COMPLETE"
    assert out.get("reason") is None

    entry = ds.by_ticker["ALFA"][holding_sessions[0]].open
    exit_p = ds.by_ticker["ALFA"][holding_sessions[-1]].close
    expected_price_return = exit_p / entry - 1
    expected_net_return = expected_price_return - snap["cost"]
    assert out["entry_price"] == pytest.approx(entry)
    assert out["exit_price"] == pytest.approx(exit_p)
    assert out["raw_return"] == pytest.approx(expected_price_return)
    assert out["net_return"] == pytest.approx(expected_net_return)
    assert out["price_return"] == pytest.approx(expected_price_return)
    assert out["price_net_return"] == pytest.approx(expected_net_return)


def test_r2_2_r1_case3_synthetic_shadow_past_captured_at_complete():
    """Case 3: captured_at < as_of + event-free complete coverage.
    observe(mode='shadow') must return COMPLETE.
    """
    ds = synthetic_dataset(n=30, symbols=("ALFA", "BETA"), seed=42)
    session = ds.sessions[10]
    holding_sessions = next_sessions(session, 5)
    as_of = cutoff_at(holding_sessions[-1]).isoformat()
    past_time = (timestamp(as_of) - timedelta(days=2)).isoformat()

    cap = dict(ds.metadata["action_capture"])
    cap["captured_at"] = past_time
    ds_past = Dataset(ds.bars, {**ds.metadata, "action_capture": cap}, ds.members)

    origin_bar = ds.by_ticker["ALFA"][session]
    snap = v3_snapshot(session=session, ticker="ALFA", entry_ref=origin_bar.close)

    out = observe(snap, ds_past, 5, as_of=as_of, mode="shadow")
    assert out["status"] == "COMPLETE"
    assert out.get("reason") is None
    entry = ds.by_ticker["ALFA"][holding_sessions[0]].open
    exit_p = ds.by_ticker["ALFA"][holding_sessions[-1]].close
    expected_price_return = exit_p / entry - 1
    expected_net_return = expected_price_return - snap["cost"]
    assert out["net_return"] == pytest.approx(expected_net_return)


def test_r2_2_r1_case4_synthetic_shadow_future_event_known_at_pending():
    """Case 4: captured_at <= as_of, but event in holding window has known_at > as_of.
    observe(mode='shadow') must return PENDING / data_not_yet_known without return fields.
    """
    ds = synthetic_dataset(n=30, symbols=("ALFA", "BETA"), seed=42)
    session = ds.sessions[10]
    holding_sessions = next_sessions(session, 5)
    as_of = cutoff_at(holding_sessions[-1]).isoformat()
    future_time = (timestamp(as_of) + timedelta(days=1)).isoformat()

    cap = dict(ds.metadata["action_capture"])
    cap["captured_at"] = as_of
    cap["events"] = [{
        "ticker": "ALFA",
        "session": holding_sessions[2],
        "field": "Capital Gains",
        "amount": 0.50,
        "known_at": future_time,
    }]
    ds_ev = Dataset(ds.bars, {**ds.metadata, "action_capture": cap}, ds.members)

    origin_bar = ds.by_ticker["ALFA"][session]
    snap = v3_snapshot(session=session, ticker="ALFA", entry_ref=origin_bar.close)

    out = observe(snap, ds_ev, 5, as_of=as_of, mode="shadow")
    assert out["status"] == "PENDING"
    assert out["reason"] == "data_not_yet_known"
    assert "raw_return" not in out
    assert "net_return" not in out
    assert "price_return" not in out
    assert "price_net_return" not in out


def test_r2_2_r1_case5_synthetic_shadow_missing_captured_at_inspect_unit():
    """Case 5: Capture exists, but captured_at is missing (None or empty).
    Tested via pure unit test calling inspect_action_capture directly without
    bypassing Dataset validator. Must return is_pending=True, reason='data_not_yet_known'.
    """
    ds = synthetic_dataset(n=20, symbols=("ALFA", "BETA"), seed=42)
    holding_sessions = ds.sessions[5:10]
    as_of = cutoff_at(holding_sessions[-1]).isoformat()

    # Sub-case A: captured_at is None
    cap_none = dict(ds.metadata["action_capture"])
    cap_none["captured_at"] = None
    mock_ds_none = type("MockDataset", (), {"metadata": {"action_capture": cap_none}})()
    insp_none = inspect_action_capture(mock_ds_none, "ALFA", holding_sessions, as_of=as_of, mode="shadow")
    assert insp_none.is_pending is True
    assert insp_none.reason == "data_not_yet_known"
    assert insp_none.is_confirmed is False

    # Sub-case B: captured_at is empty string
    cap_empty = dict(ds.metadata["action_capture"])
    cap_empty["captured_at"] = ""
    mock_ds_empty = type("MockDataset", (), {"metadata": {"action_capture": cap_empty}})()
    insp_empty = inspect_action_capture(mock_ds_empty, "ALFA", holding_sessions, as_of=as_of, mode="shadow")
    assert insp_empty.is_pending is True
    assert insp_empty.reason == "data_not_yet_known"
    assert insp_empty.is_confirmed is False


def test_r2_2_r1_case6_synthetic_shadow_future_benchmark_capture_blocks_candidates():
    """Case 6: Synthetic benchmark with future capture.
    In shadow mode, Engine.signals cannot generate normal candidates and fails closed.
    """
    ds = synthetic_dataset(n=100, symbols=("ALFA", "BETA"), seed=42)
    config = Config(tickers=("ALFA", "BETA"), train_sessions=60)
    session = ds.sessions[70]
    cutoff = cutoff_at(session).isoformat()
    future_time = (timestamp(cutoff) + timedelta(days=5)).isoformat()

    cap = dict(ds.metadata["action_capture"])
    cap["captured_at"] = future_time
    ds_future_bench = Dataset(ds.bars, {**ds.metadata, "action_capture": cap}, ds.members)

    engine = Engine(ds_future_bench, config)
    with pytest.raises(ValueError, match="Benchmark SPY history not yet known"):
        engine.signals(session, mode="shadow")


def test_r2_2_r1_case7_synthetic_research_history_and_calibration_unaffected():
    """Case 7: Existing research synthetic history and calibration.
    Reconfirm that research mode operations are completely unaffected by capture timestamps.
    """
    ds = synthetic_dataset(n=250, symbols=("ALFA", "BETA"), seed=7)
    config = Config(tickers=("ALFA", "BETA"), train_sessions=120)

    future_time = "2099-01-01T00:00:00+00:00"
    cap = dict(ds.metadata["action_capture"])
    cap["captured_at"] = future_time
    ds_future = Dataset(ds.bars, {**ds.metadata, "action_capture": cap}, ds.members)

    engine_res = Engine(ds_future, config, outcome_version=OUTCOME_VERSION_V3)
    target_session = ds.sessions[150]
    sigs = engine_res.signals(target_session, mode="research")
    assert isinstance(sigs["candidates"], list)
    assert len(sigs["candidates"]) > 0

    cand = sigs["candidates"][0]
    cal = engine_res.calibration(cand, boundary=target_session)
    assert cal["samples"] >= 0
    assert "expected_return" in cal

    hist = engine_res.history
    assert len(hist) > 0
    assert all(r["outcome_version"] == OUTCOME_VERSION_V3 for r in hist)


# ============================================================================
# M2-1A-R2-3: cash_action_review_v1 evaluation policy isolation tests
# ============================================================================

def test_r2_3_v2_complete_preserved_in_db_but_excluded_from_evaluation(tmp_path, five_session_dates):
    """1. v2 COMPLETE가 DB에는 COMPLETE로 보존되지만 evaluation rows에서는 제외됨
    2. 제외 reason = legacy_v2_unverified_contract
    5. excluded COMPLETE만 존재하는 경우 이를 0건처럼 숨기지 않음
    """
    dates = five_session_dates
    origin_bar = [{"ticker": "ALFA", "session": "2024-01-02", "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0}]
    holding_bars = make_test_bars("ALFA", dates, [100.0] * 5, [105.0] * 5, dividends=[0.0, 1.0, 0.0, 0.0, 0.0])
    ds = create_mini_dataset(origin_bar + holding_bars, include_action_capture=True)

    snap = base_snapshot(version=OUTCOME_VERSION_V2)
    config = Config(tickers=("ALFA",), train_sessions=180)

    with Store(tmp_path / "v2_eval.db") as store:
        store.save_dataset(ds)
        store.save_model(config)
        with store.db:
            store.db.execute(
                "INSERT INTO runs VALUES('run-v2', ?, ?, '2024-01-02', 'research', 'SUCCEEDED', 1, NULL, NULL, ?)",
                (ds.id, config.model_id, cutoff_at("2024-01-02").isoformat()),
            )
            store.db.execute(
                "INSERT INTO recommendations VALUES('rec-v2', 'run-v2', 'ALFA', 1, ?)",
                (json.dumps(snap),),
            )
        as_of = cutoff_at(dates[-1]).isoformat()
        counts, rows = track(store, ds, as_of)

        # 1. Horizon observation denominator remains COMPLETE
        assert counts["COMPLETE"] >= 1
        # 2. Excluded from evaluation rows
        assert len(rows) == 0, "v2 COMPLETE must be excluded from evaluation rows"
        # 3. Evaluation counts reflect policy, reason, version, and are NOT hidden as 0
        ev = counts["evaluation"]
        assert ev["policy"] == CASH_ACTION_REVIEW_POLICY
        assert ev["eligible_complete"] == 0
        assert ev["excluded_complete"] == 1
        assert ev["by_reason"]["legacy_v2_unverified_contract"] == 1
        assert ev["by_version"][OUTCOME_VERSION_V2] == 1
        assert len(ev["excluded_groups"]) == 1

        # 4. DB record is preserved as COMPLETE with original v2 arithmetic
        db_out = store.db.execute("SELECT status, body FROM outcomes WHERE recommendation_id='rec-v2' AND horizon=5").fetchone()
        assert db_out["status"] == "COMPLETE"
        body = json.loads(db_out["body"])
        assert body["outcome_version"] == OUTCOME_VERSION_V2
        assert body["dividend_cash"] == 1.0


def test_r2_3_v3_eligible_and_concurrent_v2_metrics_isolation(tmp_path, five_session_dates):
    """3. v3 적격 COMPLETE는 rows에 포함됨
    4. v2 + v3가 동시에 존재해도 risk/recent metrics에는 v3 적격 결과만 들어감
    """
    dates = five_session_dates
    origin_alfa = [{"ticker": "ALFA", "session": "2024-01-02", "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0}]
    origin_beta = [{"ticker": "BETA", "session": "2024-01-02", "open": 50.0, "high": 51.0, "low": 49.0, "close": 50.0}]
    # ALFA: event-free (eligible for v3)
    holding_alfa = make_test_bars("ALFA", dates, [100.0] * 5, [105.0] * 5)
    # BETA: v2 ordinary cash dividend (excluded)
    holding_beta = make_test_bars("BETA", dates, [50.0] * 5, [55.0] * 5, dividends=[0.0, 2.0, 0.0, 0.0, 0.0])
    ds = create_mini_dataset(origin_alfa + origin_beta + holding_alfa + holding_beta, include_action_capture=True)

    config = Config(tickers=("ALFA", "BETA"), train_sessions=180)
    snap_alfa_v3 = v3_snapshot(session="2024-01-02", ticker="ALFA", entry_ref=100.0)
    snap_beta_v2 = base_snapshot(session="2024-01-02", ticker="BETA", entry_ref=50.0, version=OUTCOME_VERSION_V2)

    with Store(tmp_path / "concurrent.db") as store:
        store.save_dataset(ds)
        store.save_model(config)
        with store.db:
            store.db.execute(
                "INSERT INTO runs VALUES('run-multi', ?, ?, '2024-01-02', 'research', 'SUCCEEDED', 1, NULL, NULL, ?)",
                (ds.id, config.model_id, cutoff_at("2024-01-02").isoformat()),
            )
            store.db.execute(
                "INSERT INTO recommendations VALUES('rec-alfa', 'run-multi', 'ALFA', 1, ?)",
                (json.dumps(snap_alfa_v3),),
            )
            store.db.execute(
                "INSERT INTO recommendations VALUES('rec-beta', 'run-multi', 'BETA', 2, ?)",
                (json.dumps(snap_beta_v2),),
            )

        as_of = cutoff_at(dates[-1]).isoformat()
        counts, rows = track(store, ds, as_of)

        # Both completed calculation in horizon counts
        assert counts["COMPLETE"] >= 2
        # Only v3 is in evaluation rows
        assert len(rows) == 1
        assert rows[0]["ticker"] == "ALFA"
        assert rows[0]["outcome_version"] == OUTCOME_VERSION_V3

        # Evaluation breakdown
        ev = counts["evaluation"]
        assert ev["eligible_complete"] == 1
        assert ev["excluded_complete"] == 1
        assert ev["by_reason"]["legacy_v2_unverified_contract"] == 1
        assert ev["by_version"][OUTCOME_VERSION_V2] == 1

        # Verify metrics only include ALFA
        m = metrics(rows)
        assert m["samples"] == 1
        expected_alfa_net = (105.0 / 100.0 - 1) - snap_alfa_v3["cost"]
        assert m["expectancy"] == pytest.approx(expected_alfa_net)

        # risk_decision only sees ALFA
        state, reason = risk_decision(rows)
        assert state == "NORMAL"


def test_r2_3_excluded_complete_only_pauses_scan_and_format_report(tmp_path):
    """5. excluded COMPLETE만 존재하는 경우 0건처럼 숨기지 않고 보수적으로 pause 및 리포트 표시"""
    ds = synthetic_dataset(n=120, symbols=("ALFA", "BETA"), seed=7)
    config = Config(tickers=("ALFA", "BETA"), train_sessions=60)
    rec_session = ds.sessions[70]
    origin_bar = ds.by_ticker["ALFA"][rec_session]

    snap = base_snapshot(session=rec_session, ticker="ALFA", entry_ref=origin_bar.close, version=OUTCOME_VERSION_V2)

    with Store(tmp_path / "scan_pause.db") as store:
        store.save_dataset(ds)
        store.save_model(config)
        with store.db:
            store.db.execute(
                "INSERT INTO runs VALUES('run-old', ?, ?, ?, 'research', 'SUCCEEDED', 1, NULL, NULL, ?)",
                (ds.id, config.model_id, rec_session, cutoff_at(rec_session).isoformat()),
            )
            store.db.execute(
                "INSERT INTO recommendations VALUES('rec-old', 'run-old', 'ALFA', 1, ?)",
                (json.dumps(snap),),
            )

        # Operational scan on subsequent session: having excluded outcomes in track triggers conservative pause
        scan_session = ds.sessions[80]
        report = scan(store, ds, config, scan_session, mode="research")
        assert report["state"] == "PAUSED"
        assert report["state_reason"] == "unresolved_outcome_data"
        assert report["evaluation_policy"] == CASH_ACTION_REVIEW_POLICY
        assert report["outcomes"]["evaluation"]["excluded_complete"] >= 1

        formatted = format_report(report)
        assert "Evaluation Policy: cash_action_review_v1" in formatted
        assert "Excluded:" in formatted
        assert "legacy_v2_unverified_contract:" in formatted

        # Format historical report with v2 contract
        hist_report = dict(report, outcome_contract=OUTCOME_VERSION_V2)
        formatted_hist = format_report(hist_report)
        assert f"Outcome Contract: {OUTCOME_VERSION_V2}" in formatted_hist
        assert "Historical v2 calculation record; excluded from current cash_action_review_v1" in formatted_hist


def test_r2_3_outcome_version_mismatch_excluded(tmp_path, five_session_dates):
    """6. snapshot/result version mismatch가 평가 제외됨"""
    dates = five_session_dates
    origin_bar = [{"ticker": "ALFA", "session": "2024-01-02", "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0}]
    holding_bars = make_test_bars("ALFA", dates, [100.0] * 5, [105.0] * 5)
    ds = create_mini_dataset(origin_bar + holding_bars, include_action_capture=True)

    # Snapshot is v3, but pre-stored outcome in DB is v1
    snap = v3_snapshot()
    config = Config(tickers=("ALFA",), train_sessions=180)

    stored_v1_body = {
        "horizon": 5, "end_session": dates[-1], "observed_at": cutoff_at(dates[-1]).isoformat(),
        "outcome_version": OUTCOME_VERSION_V1, "status": "COMPLETE", "raw_return": 0.05, "net_return": 0.048,
    }

    with Store(tmp_path / "mismatch.db") as store:
        store.save_dataset(ds)
        store.save_model(config)
        with store.db:
            store.db.execute(
                "INSERT INTO runs VALUES('run-mm', ?, ?, '2024-01-02', 'research', 'SUCCEEDED', 1, NULL, NULL, ?)",
                (ds.id, config.model_id, cutoff_at("2024-01-02").isoformat()),
            )
            store.db.execute(
                "INSERT INTO recommendations VALUES('rec-mm', 'run-mm', 'ALFA', 1, ?)",
                (json.dumps(snap),),
            )
            store.db.execute(
                "INSERT INTO outcomes VALUES('rec-mm', 5, ?, 'COMPLETE', ?)",
                (ds.id, json.dumps(stored_v1_body)),
            )

        as_of = cutoff_at(dates[-1]).isoformat()
        counts, rows = track(store, ds, as_of)

        assert counts["evaluation"]["excluded_complete"] == 1
        assert counts["evaluation"]["by_reason"]["outcome_version_mismatch"] == 1
        assert len(rows) == 0


def test_r2_3_existing_outcome_not_overwritten_by_rerun(tmp_path, five_session_dates):
    """7. 기존 outcome을 재실행해 다른 버전으로 덮어쓰지 않음"""
    dates = five_session_dates
    origin_bar = [{"ticker": "ALFA", "session": "2024-01-02", "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0}]
    holding_bars = make_test_bars("ALFA", dates, [100.0] * 5, [105.0] * 5, dividends=[0.0, 1.0, 0.0, 0.0, 0.0])
    ds = create_mini_dataset(origin_bar + holding_bars, include_action_capture=True)

    snap = base_snapshot(version=OUTCOME_VERSION_V2)
    config = Config(tickers=("ALFA",), train_sessions=180)

    with Store(tmp_path / "no_overwrite.db") as store:
        store.save_dataset(ds)
        store.save_model(config)
        with store.db:
            store.db.execute(
                "INSERT INTO runs VALUES('run-no', ?, ?, '2024-01-02', 'research', 'SUCCEEDED', 1, NULL, NULL, ?)",
                (ds.id, config.model_id, cutoff_at("2024-01-02").isoformat()),
            )
            store.db.execute(
                "INSERT INTO recommendations VALUES('rec-no', 'run-no', 'ALFA', 1, ?)",
                (json.dumps(snap),),
            )

        as_of = cutoff_at(dates[-1]).isoformat()
        # First track creates v2 outcome in outcomes table
        track(store, ds, as_of)
        before_body = store.db.execute("SELECT body FROM outcomes WHERE recommendation_id='rec-no' AND horizon=5").fetchone()[0]

        # Second track call must not overwrite or mutate
        track(store, ds, as_of)
        after_body = store.db.execute("SELECT body FROM outcomes WHERE recommendation_id='rec-no' AND horizon=5").fetchone()[0]
        assert before_body == after_body
        assert json.loads(after_body)["outcome_version"] == OUTCOME_VERSION_V2


def test_r2_3_future_stored_outcome_not_used_at_past_as_of(tmp_path, five_session_dates):
    """8. historical as_of보다 미래의 저장 outcome을 사용하지 않음"""
    dates = five_session_dates
    origin_bar = [{"ticker": "ALFA", "session": "2024-01-02", "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0}]
    holding_bars = make_test_bars("ALFA", dates, [100.0] * 5, [105.0] * 5)
    ds = create_mini_dataset(origin_bar + holding_bars, include_action_capture=True)

    snap = v3_snapshot()
    config = Config(tickers=("ALFA",), train_sessions=180)

    # Future stored outcome finalized at dates[-1]
    future_time = cutoff_at(dates[-1]).isoformat()
    future_body = {
        "horizon": 5, "end_session": dates[-1], "observed_at": future_time,
        "outcome_version": OUTCOME_VERSION_V3, "status": "COMPLETE", "raw_return": 0.05, "net_return": 0.048,
    }

    with Store(tmp_path / "pit_stored.db") as store:
        store.save_dataset(ds)
        store.save_model(config)
        with store.db:
            store.db.execute(
                "INSERT INTO runs VALUES('run-pit', ?, ?, '2024-01-02', 'research', 'SUCCEEDED', 1, NULL, NULL, ?)",
                (ds.id, config.model_id, cutoff_at("2024-01-02").isoformat()),
            )
            store.db.execute(
                "INSERT INTO recommendations VALUES('rec-pit', 'run-pit', 'ALFA', 1, ?)",
                (json.dumps(snap),),
            )
            store.db.execute(
                "INSERT INTO outcomes VALUES('rec-pit', 5, ?, 'COMPLETE', ?)",
                (ds.id, json.dumps(future_body)),
            )

        # Query at past as_of (session 2 of holding period)
        past_as_of = cutoff_at(dates[1]).isoformat()
        counts, rows = track(store, ds, past_as_of)

        # Horizon 5 was not mature at past_as_of; stored future complete must NOT be used
        assert len(rows) == 0
        assert counts["PENDING"] >= 1


def test_r2_3_validation_oos_excludes_v2(tmp_path, monkeypatch):
    """9. validation/OOS 통계에도 부적격 v2가 섞이지 않음
    - 계산 자체는 v2 COMPLETE일 수 있음
    - evaluation에서는 legacy_v2_unverified_contract로 제외
    - OOS metrics samples에는 포함되지 않음
    - exclusion denominator/reason/version에는 남음
    - matched SPY에 대해서도 동일한 정책 결과가 확인됨
    """
    import richping.validation
    # Supply v2 COMPLETE signals and labels via Engine outcome_version=OUTCOME_VERSION_V2
    monkeypatch.setattr(richping.validation, "Engine", lambda ds, cfg: Engine(ds, cfg, outcome_version=OUTCOME_VERSION_V2))

    ds = synthetic_dataset(n=350)
    config = Config(tickers=tuple(m["ticker"] for m in ds.members), train_sessions=180)

    with Store(tmp_path / "validate_eval_v2.db") as store:
        store.save_dataset(ds)
        result = validate(store, ds, config, train=180, validation=30, oos=30)
        assert result["trial"] is not None
        assert "folds" in result
        assert len(result["folds"]) >= 1

        # OOS aggregated samples must be 0 because all v2 are excluded
        assert result["oos"]["samples"] == 0

        for fold in result["folds"]:
            for phase in ("validation", "oos"):
                outcomes = fold[phase]["outcomes"]
                # 1. Calculation itself was COMPLETE
                assert outcomes["COMPLETE"] > 0
                # 2. Evaluation excluded all v2 COMPLETEs
                ev = outcomes["evaluation"]
                assert ev["policy"] == CASH_ACTION_REVIEW_POLICY
                assert ev["eligible_complete"] == 0
                assert ev["excluded_complete"] == outcomes["COMPLETE"]
                assert ev["by_reason"]["legacy_v2_unverified_contract"] == outcomes["COMPLETE"]
                assert ev["by_version"][OUTCOME_VERSION_V2] == outcomes["COMPLETE"]

                # 3. Metrics samples are 0 (ineligible results do NOT enter OOS metrics)
                assert fold[phase]["metrics"]["samples"] == 0

                # 4. matched SPY also evaluates to legacy_v2_unverified_contract exclusion
                spy_ev = fold[phase]["matched_SPY_evaluation"]
                assert spy_ev["eligible_complete"] == 0
                assert spy_ev["excluded_complete"] > 0
                assert spy_ev["by_reason"]["legacy_v2_unverified_contract"] == spy_ev["excluded_complete"]
                assert spy_ev["by_version"][OUTCOME_VERSION_V2] == spy_ev["excluded_complete"]
                assert fold[phase]["matched_SPY"]["samples"] == 0


def test_r2_3_stored_buggy_v3_with_future_captured_at_excluded(tmp_path, five_session_dates):
    """과거 계약상 잘못 생성됐다고 가정한 stored v3 COMPLETE + 당시 미래 captured_at -> 현재 evaluation에서 제외"""
    dates = five_session_dates
    origin_bar = [{"ticker": "ALFA", "session": "2024-01-02", "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0}]
    holding_bars = make_test_bars("ALFA", dates, [100.0] * 5, [105.0] * 5)
    ds_clean = create_mini_dataset(origin_bar + holding_bars, include_action_capture=True)

    # In dataset action capture, captured_at was in the future relative to when outcome was observed
    obs_time = cutoff_at(dates[-1]).isoformat()
    future_captured_at = (timestamp(obs_time) + timedelta(days=2)).isoformat()

    cap = dict(ds_clean.metadata["action_capture"])
    cap["captured_at"] = future_captured_at
    ds = Dataset(ds_clean.bars, {**ds_clean.metadata, "action_capture": cap}, ds_clean.members)

    snap = v3_snapshot()
    config = Config(tickers=("ALFA",), train_sessions=180)

    # Pre-stored buggy v3 outcome in Store with status COMPLETE (as if generated before R2-2-R1)
    stored_v3_body = {
        "horizon": 5, "end_session": dates[-1], "observed_at": obs_time,
        "outcome_version": OUTCOME_VERSION_V3, "status": "COMPLETE", "raw_return": 0.05, "net_return": 0.048,
    }

    with Store(tmp_path / "buggy_v3.db") as store:
        store.save_dataset(ds)
        store.save_model(config)
        with store.db:
            store.db.execute(
                "INSERT INTO runs VALUES('run-buggy', ?, ?, '2024-01-02', 'shadow', 'SUCCEEDED', 1, NULL, NULL, ?)",
                (ds.id, config.model_id, cutoff_at("2024-01-02").isoformat()),
            )
            store.db.execute(
                "INSERT INTO recommendations VALUES('rec-buggy', 'run-buggy', 'ALFA', 1, ?)",
                (json.dumps(snap),),
            )
            store.db.execute(
                "INSERT INTO outcomes VALUES('rec-buggy', 5, ?, 'COMPLETE', ?)",
                (ds.id, json.dumps(stored_v3_body)),
            )

        # In shadow mode, track evaluates stored outcome at as_of
        as_of = (timestamp(obs_time) + timedelta(days=3)).isoformat()
        counts, rows = track(store, ds, as_of)

        # Buggy stored v3 COMPLETE must be excluded because captured_at was in the future at obs_time!
        assert len(rows) == 0
        assert counts["evaluation"]["excluded_complete"] == 1
        assert counts["evaluation"]["by_reason"]["data_not_yet_known"] == 1
        assert counts["evaluation"]["by_version"][OUTCOME_VERSION_V3] == 1

        # Original DB outcome record is preserved unchanged
        db_out = store.db.execute("SELECT status, body FROM outcomes WHERE recommendation_id='rec-buggy' AND horizon=5").fetchone()
        assert db_out["status"] == "COMPLETE"
        assert json.loads(db_out["body"])["outcome_version"] == OUTCOME_VERSION_V3


def test_r2_3_normal_v3_complete_remains_eligible(tmp_path, five_session_dates):
    """정상 v3 COMPLETE -> 그대로 eligible"""
    dates = five_session_dates
    origin_bar = [{"ticker": "ALFA", "session": "2024-01-02", "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0}]
    holding_bars = make_test_bars("ALFA", dates, [100.0] * 5, [105.0] * 5)
    ds = create_mini_dataset(origin_bar + holding_bars, include_action_capture=True)

    snap = v3_snapshot()
    config = Config(tickers=("ALFA",), train_sessions=180)

    with Store(tmp_path / "normal_v3.db") as store:
        store.save_dataset(ds)
        store.save_model(config)
        with store.db:
            store.db.execute(
                "INSERT INTO runs VALUES('run-norm', ?, ?, '2024-01-02', 'shadow', 'SUCCEEDED', 1, NULL, NULL, ?)",
                (ds.id, config.model_id, cutoff_at("2024-01-02").isoformat()),
            )
            store.db.execute(
                "INSERT INTO recommendations VALUES('rec-norm', 'run-norm', 'ALFA', 1, ?)",
                (json.dumps(snap),),
            )

        as_of = cutoff_at("2024-01-12").isoformat()
        counts, rows = track(store, ds, as_of)

        assert counts["COMPLETE"] >= 1
        assert len(rows) == 1
        assert rows[0]["ticker"] == "ALFA"
        assert rows[0]["outcome_version"] == OUTCOME_VERSION_V3
        assert counts["evaluation"]["eligible_complete"] == 1
        assert counts["evaluation"]["excluded_complete"] == 0


def test_r2_stored_v3_complete_future_bar_known_at_excluded(tmp_path, five_session_dates):
    """Finding 1: stored v3 COMPLETE라도 보유 bar known_at > stored observed_at이면 data_not_yet_known으로 제외
    - DB COMPLETE 원본 유지
    - evaluation rows 제외
    - excluded_complete 증가
    - reason = data_not_yet_known
    - 현재 as_of가 충분히 늦더라도 당시 미래였던 데이터를 소급 적격화하지 않음
    """
    dates = five_session_dates
    origin_bar = [{"ticker": "ALFA", "session": "2024-01-02", "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0}]
    holding_bars = make_test_bars("ALFA", dates, [100.0] * 5, [105.0] * 5)
    obs_time = cutoff_at(dates[-1]).isoformat()

    # action_capture was normal at obs_time
    ds_clean = create_mini_dataset(origin_bar + holding_bars, include_action_capture=True)
    cap = dict(ds_clean.metadata["action_capture"])
    cap["captured_at"] = obs_time

    # But one holding bar's known_at was in the future relative to obs_time
    future_bar_known = (timestamp(obs_time) + timedelta(days=1)).isoformat()
    modified_bars = []
    for b in ds_clean.bars:
        if b.session == dates[-1]:
            b = Bar(b.ticker, b.session, b.open, b.high, b.low, b.close, b.volume, future_bar_known, b.dividend, b.split)
        modified_bars.append(b)
    ds = Dataset(modified_bars, {**ds_clean.metadata, "action_capture": cap}, ds_clean.members)

    snap = v3_snapshot()
    config = Config(tickers=("ALFA",), train_sessions=180)

    stored_v3_body = {
        "horizon": 5, "end_session": dates[-1], "observed_at": obs_time,
        "outcome_version": OUTCOME_VERSION_V3, "status": "COMPLETE", "raw_return": 0.05, "net_return": 0.048,
    }

    with Store(tmp_path / "bar_known_future.db") as store:
        store.save_dataset(ds)
        store.save_model(config)
        with store.db:
            store.db.execute(
                "INSERT INTO runs VALUES('run-bar-fut', ?, ?, '2024-01-02', 'shadow', 'SUCCEEDED', 1, NULL, NULL, ?)",
                (ds.id, config.model_id, cutoff_at("2024-01-02").isoformat()),
            )
            store.db.execute(
                "INSERT INTO recommendations VALUES('rec-bar-fut', 'run-bar-fut', 'ALFA', 1, ?)",
                (json.dumps(snap),),
            )
            store.db.execute(
                "INSERT INTO outcomes VALUES('rec-bar-fut', 5, ?, 'COMPLETE', ?)",
                (ds.id, json.dumps(stored_v3_body)),
            )

        # Even if current as_of is far in the future, past observation at obs_time must not retroactively qualify!
        late_as_of = (timestamp(obs_time) + timedelta(days=10)).isoformat()
        counts, rows = track(store, ds, late_as_of)

        # Excluded from evaluation rows
        assert len(rows) == 0
        assert counts["evaluation"]["excluded_complete"] == 1
        assert counts["evaluation"]["by_reason"]["data_not_yet_known"] == 1
        assert counts["evaluation"]["by_version"][OUTCOME_VERSION_V3] == 1

        # Original DB outcome record is preserved unchanged
        db_out = store.db.execute("SELECT status, body FROM outcomes WHERE recommendation_id='rec-bar-fut' AND horizon=5").fetchone()
        assert db_out["status"] == "COMPLETE"
        saved = json.loads(db_out["body"])
        assert saved["outcome_version"] == OUTCOME_VERSION_V3
        assert saved["observed_at"] == obs_time


@pytest.mark.parametrize("corrupt_field,corrupt_value,expected_reason", [
    ("observed_at", None, "missing_observed_at"),
    ("observed_at", "", "missing_observed_at"),
    ("observed_at", "not-a-valid-timestamp", "invalid_observed_at"),
    ("horizon", 10, "horizon_mismatch"),
    ("end_session", "2024-01-99", "end_session_mismatch"),
])
def test_r2_stored_outcome_structural_integrity_fail_closed(five_session_dates, corrupt_field, corrupt_value, expected_reason):
    """Finding 1: stored outcome의 구조적 정합성(observed_at 누락/비정상, horizon/end mismatch) 실패 폐쇄 검증"""
    dates = five_session_dates
    origin_bar = [{"ticker": "ALFA", "session": "2024-01-02", "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0}]
    holding_bars = make_test_bars("ALFA", dates, [100.0] * 5, [105.0] * 5)
    ds = create_mini_dataset(origin_bar + holding_bars, include_action_capture=True)

    snap = v3_snapshot()
    outcome = {
        "horizon": 5,
        "end_session": dates[-1],
        "observed_at": cutoff_at(dates[-1]).isoformat(),
        "outcome_version": OUTCOME_VERSION_V3,
        "status": "COMPLETE",
        "raw_return": 0.05,
        "net_return": 0.048,
    }

    if corrupt_value is None:
        outcome.pop(corrupt_field, None)
    else:
        outcome[corrupt_field] = corrupt_value

    as_of = cutoff_at("2024-01-16").isoformat()
    is_eligible, reason = evaluate_outcome_eligibility(snap, outcome, dataset=ds, as_of=as_of, mode="shadow")
    assert is_eligible is False
    assert reason == expected_reason


def test_r2_matched_spy_pairing_and_unresolved_denominator(tmp_path):
    """Finding 2: matched SPY의 UNRESOLVED/PENDING 분모 보존 및 signal-date 기준 pairing 검증
    - 후보 종목은 event-free COMPLETE
    - 동일 signal date의 SPY 보유 기간에 현금배당 주입
    - SPY UNRESOLVED 존재 & reason = unverified_cash_dividend_event
    - matched_SPY_evaluation 분모(UNRESOLVED 카운트)에서 사라지지 않음
    - 해당 날짜는 paired benchmark metric에서 제외
    - 후보 전체 strategy metric은 정상 유지
    - paired candidate와 paired SPY가 동일 signal-date 집합을 사용
    """
    ds = synthetic_dataset(n=350)
    # Inject cash dividend specifically into SPY on an OOS holding session
    mod_bars = []
    for b in ds.bars:
        if b.ticker == "SPY" and b.session == "2023-03-07":
            b = Bar(b.ticker, b.session, b.open, b.high, b.low, b.close, b.volume, b.known_at, 1.0, b.split)
        mod_bars.append(b)
    ds_mod = Dataset(mod_bars, ds.metadata, ds.members)

    config = Config(tickers=tuple(m["ticker"] for m in ds.members), train_sessions=180)

    with Store(tmp_path / "validate_spy_unresolved.db") as store:
        store.save_dataset(ds_mod)
        result = validate(store, ds_mod, config, train=180, validation=30, oos=30)
        assert len(result["folds"]) >= 1

        for fold in result["folds"]:
            oos = fold["oos"]
            spy_ev = oos["matched_SPY_evaluation"]

            # 1. SPY UNRESOLVED exists with unverified_cash_dividend_event reason
            assert spy_ev["UNRESOLVED"] >= 1
            assert spy_ev["by_reason"].get("unverified_cash_dividend_event", 0) >= 1

            # 2. Denominator preserves all attempts
            total_spy_attempts = spy_ev["COMPLETE"] + spy_ev["PENDING"] + spy_ev["UNRESOLVED"]
            assert total_spy_attempts == spy_ev["attempted_signal_dates"]
            assert spy_ev["candidate_only_signal_dates"] >= 1

            # 3. Strategy candidate metric is preserved
            candidate_samples = oos["metrics"]["samples"]
            assert candidate_samples > 0

            # 4. Paired benchmark metric excludes the dividend date
            spy_samples = oos["matched_SPY"]["samples"]
            assert spy_samples < candidate_samples
            assert spy_samples == spy_ev["paired_signal_dates"]

            # 5. matched_candidate has exactly the same paired signal dates as matched_SPY
            matched_cand = oos["matched_candidate"]
            assert matched_cand["samples"] == spy_samples
            assert matched_cand["samples"] == spy_ev["paired_signal_dates"]
            # Candidate predictions contains the unresolved signal date 2023-03-06, but paired metrics exclude it
            oos_sessions = {r["session"] for r in result["oos_predictions"]}
            assert "2023-03-06" in oos_sessions



