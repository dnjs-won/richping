"""Deterministic tests for Corporate Action Ingestion Information Preservation (M2-1A-R2-1-R1).
Verifies action_capture schema, Capital Gains preservation, provenance, validation, store round-trip,
legacy backward compatibility, overlap revision, incremental merge, and synthetic determinism.
Zero live network calls.
"""

from dataclasses import replace
import json
import math
from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from richping.core import (
    ACTION_CAPTURE_SCHEMA_VERSION,
    VERIFIED_DIVIDEND_BASIS,
    cutoff_at,
    digest,
    sessions,
    utcnow,
)
from richping.data import (
    Bar,
    Dataset,
    create_action_capture,
    import_csv,
    is_verified_yfinance_adapter,
    synthetic_dataset,
    validate_action_capture,
    yahoo_dataset,
)
from richping.store import Store


def make_mock_yahoo(
    monkeypatch,
    frames_by_ticker=None,
    meta_by_ticker=None,
    fast_meta_by_ticker=None,
    info_by_ticker=None,
    default_has_cg=False,
    version="1.7.0",
):
    """Creates a mock yfinance module with per-ticker DataFrames, metadata, and configurable version."""
    calls = []
    frames_by_ticker = frames_by_ticker or {}
    meta_by_ticker = meta_by_ticker or {}
    fast_meta_by_ticker = fast_meta_by_ticker or {}
    info_by_ticker = info_by_ticker or {}

    def provider_result(mapping, symbol, default):
        result = mapping.get(symbol, default)
        if isinstance(result, Exception):
            raise result
        return result

    class MockTicker:
        def __init__(self, symbol):
            self.symbol = symbol

        def get_history_metadata(self):
            return provider_result(
                meta_by_ticker,
                self.symbol,
                {"instrumentType": "EQUITY", "currency": "USD"},
            )

        @property
        def fast_info(self):
            return provider_result(fast_meta_by_ticker, self.symbol, {})

        def get_info(self):
            return provider_result(info_by_ticker, self.symbol, {})

        def history(self, **kwargs):
            calls.append((self.symbol, kwargs))
            if self.symbol in frames_by_ticker:
                fn = frames_by_ticker[self.symbol]
                return fn(kwargs) if callable(fn) else fn
            # Generate sessions dynamically for kwargs["start"] to kwargs["end"]
            start_date = kwargs["start"]
            end_date = kwargs["end"]
            all_s = sessions(start_date, end_date)
            trading_sessions = [s for s in all_s if s < end_date]
            if not trading_sessions:
                trading_sessions = [start_date]
            dates = pd.to_datetime(trading_sessions)
            d = {
                "Open": [100.0] * len(dates),
                "High": [105.0] * len(dates),
                "Low": [95.0] * len(dates),
                "Close": [102.0] * len(dates),
                "Volume": [1000000.0] * len(dates),
                "Dividends": [0.0] * len(dates),
                "Stock Splits": [0.0] * len(dates),
            }
            if default_has_cg:
                d["Capital Gains"] = [0.0] * len(dates)
            return pd.DataFrame(d, index=dates)

    ns_kwargs = {
        "Ticker": MockTicker,
        "set_tz_cache_location": lambda _: None,
    }
    if version is not None:
        ns_kwargs["__version__"] = version

    monkeypatch.setitem(sys.modules, "yfinance", SimpleNamespace(**ns_kwargs))
    monkeypatch.setattr("richping.data.time.sleep", lambda _: None)
    return calls


# ============================================================================
# Provenance & Version Tests (R1 Requirements)
# ============================================================================
def test_version_missing_yields_unknown_adapter_and_unknown_status(monkeypatch):
    """yf.__version__ 부재 + EQUITY + 열 부재 → adapter unknown, status unknown"""
    make_mock_yahoo(
        monkeypatch,
        version=None,
        meta_by_ticker={"ALFA": {"instrumentType": "EQUITY", "currency": "USD"}},
        default_has_cg=False,
    )
    ds = yahoo_dataset(("ALFA",), "2024-01-02", "2024-01-05")
    cap = ds.metadata["action_capture"]
    assert cap["adapter_version"] == "yfinance-unknown"
    assert not is_verified_yfinance_adapter(cap["adapter_version"])
    assert cap["tickers"]["ALFA"]["capital_gains_status"] == "unknown"


def test_unverified_yfinance_version_yields_unknown_status(monkeypatch):
    """검수되지 않은 버전 + EQUITY + 열 부재 → status unknown"""
    make_mock_yahoo(
        monkeypatch,
        version="1.8.0",
        meta_by_ticker={"ALFA": {"instrumentType": "EQUITY", "currency": "USD"}},
        default_has_cg=False,
    )
    ds = yahoo_dataset(("ALFA",), "2024-01-02", "2024-01-05")
    cap = ds.metadata["action_capture"]
    assert cap["adapter_version"] == "yfinance-1.8.0"
    assert not is_verified_yfinance_adapter(cap["adapter_version"])
    assert cap["tickers"]["ALFA"]["instrument_type"] == "EQUITY"
    assert cap["tickers"]["ALFA"]["instrument_type_source"] == "get_history_metadata.instrumentType"
    assert cap["tickers"]["ALFA"]["capital_gains_status"] == "unknown"


def test_verified_1_7_0_equity_yields_not_applicable_by_provider(monkeypatch):
    """1.7.0 + EQUITY + 열 부재 → not_applicable_by_provider"""
    make_mock_yahoo(
        monkeypatch,
        version="1.7.0",
        meta_by_ticker={"ALFA": {"instrumentType": "EQUITY", "currency": "USD"}},
        default_has_cg=False,
    )
    ds = yahoo_dataset(("ALFA",), "2024-01-02", "2024-01-05")
    cap = ds.metadata["action_capture"]
    assert cap["adapter_version"] == "yfinance-1.7.0"
    assert is_verified_yfinance_adapter(cap["adapter_version"])
    assert cap["tickers"]["ALFA"]["instrument_type"] == "EQUITY"
    assert cap["tickers"]["ALFA"]["instrument_type_source"] == "get_history_metadata.instrumentType"
    assert cap["tickers"]["ALFA"]["capital_gains_status"] == "not_applicable_by_provider"


def test_instrument_type_uses_secondary_provider_metadata_when_primary_omits_it(monkeypatch):
    make_mock_yahoo(
        monkeypatch,
        meta_by_ticker={"ALFA": {"currency": "USD"}},
        info_by_ticker={"ALFA": {"quoteType": "EQUITY", "currency": "USD"}},
        version="1.7.0",
    )

    ds = yahoo_dataset(("ALFA",), "2024-01-02", "2024-01-05")
    info = ds.metadata["action_capture"]["tickers"]["ALFA"]

    assert info["instrument_type"] == "EQUITY"
    assert info["instrument_type_source"] == "get_info.quoteType"
    assert info["instrument_type_observations"] == [
        {"source": "get_info.quoteType", "value": "EQUITY"}
    ]
    assert info["capital_gains_status"] == "not_applicable_by_provider"


def test_instrument_type_stays_unknown_when_all_provider_metadata_fails(monkeypatch):
    failure = RuntimeError("metadata unavailable")
    make_mock_yahoo(
        monkeypatch,
        meta_by_ticker={"ALFA": failure},
        fast_meta_by_ticker={"ALFA": failure},
        info_by_ticker={"ALFA": failure},
        version="1.7.0",
    )

    ds = yahoo_dataset(("ALFA",), "2024-01-02", "2024-01-05")
    info = ds.metadata["action_capture"]["tickers"]["ALFA"]

    assert info["instrument_type"] is None
    assert info["instrument_type_source"] == "unresolved"
    assert info["instrument_type_observations"] == []
    assert info["capital_gains_status"] == "unknown"


def test_conflicting_instrument_metadata_fails_closed(monkeypatch):
    make_mock_yahoo(
        monkeypatch,
        meta_by_ticker={"ALFA": {"instrumentType": "EQUITY", "currency": "USD"}},
        info_by_ticker={"ALFA": {"quoteType": "ETF", "currency": "USD"}},
        version="1.7.0",
    )

    ds = yahoo_dataset(("ALFA",), "2024-01-02", "2024-01-05")
    info = ds.metadata["action_capture"]["tickers"]["ALFA"]

    assert info["instrument_type"] is None
    assert info["instrument_type_source"] == "conflict"
    assert {item["value"] for item in info["instrument_type_observations"]} == {"EQUITY", "ETF"}
    assert info["capital_gains_status"] == "unknown"


@pytest.mark.parametrize("instrument_type", ["ETF", "MUTUALFUND"])
def test_fund_instrument_types_are_not_approved_as_equity(monkeypatch, instrument_type):
    make_mock_yahoo(
        monkeypatch,
        meta_by_ticker={"ALFA": {"instrumentType": instrument_type, "currency": "USD"}},
        info_by_ticker={"ALFA": {"quoteType": instrument_type, "currency": "USD"}},
        version="1.7.0",
    )

    ds = yahoo_dataset(("ALFA",), "2024-01-02", "2024-01-05")
    info = ds.metadata["action_capture"]["tickers"]["ALFA"]

    assert info["instrument_type"] == instrument_type
    assert info["capital_gains_status"] == "unknown"


def test_adapter_or_history_options_change_triggers_full_refetch(monkeypatch):
    """adapter/history options 변경 → 전체 재수집"""
    data = synthetic_dataset(n=20, symbols=("ALFA",))
    capture = dict(data.metadata["action_capture"])
    capture["adapter_version"] = "yfinance-1.6.0"
    capture["history_options"] = {
        "actions": True,
        "auto_adjust": False,
        "back_adjust": False,
        "repair": False,
    }
    prev_adapter = Dataset(
        data.bars,
        {"source": "yfinance", "quality": "research", "price_basis": "fixture", "action_capture": capture},
        data.members,
    )
    calls = make_mock_yahoo(monkeypatch, version="1.7.0")
    yahoo_dataset(("ALFA",), prev_adapter.start, prev_adapter.end, previous=prev_adapter)
    # Full refetch starts from prev_adapter.start
    assert all(kw["start"] == prev_adapter.start for _, kw in calls)

    # Previous dataset collected with different history_options (repair=True)
    capture2 = dict(capture)
    capture2["adapter_version"] = "yfinance-1.7.0"
    capture2["history_options"] = {
        "actions": True,
        "auto_adjust": False,
        "back_adjust": False,
        "repair": True,
    }
    prev_options = Dataset(
        data.bars,
        {"source": "yfinance", "quality": "research", "price_basis": "fixture", "action_capture": capture2},
        data.members,
    )
    calls2 = make_mock_yahoo(monkeypatch, version="1.7.0")
    yahoo_dataset(("ALFA",), prev_options.start, prev_options.end, previous=prev_options)
    assert all(kw["start"] == prev_options.start for _, kw in calls2)


@pytest.mark.parametrize(
    "prev_status,new_has_cg,new_type",
    [
        ("unknown", True, "EQUITY"),                      # unknown -> present
        ("present", False, None),                         # present -> unknown
        ("not_applicable_by_provider", True, "EQUITY"),   # not_applicable -> present
        ("present", False, "EQUITY"),                     # present -> not_applicable
    ],
)
def test_status_transitions_trigger_full_refetch(monkeypatch, prev_status, new_has_cg, new_type):
    """unknown ↔ present, not_applicable ↔ present → 전체 재수집 (15 session 기반 2회 호출 확인)"""
    all_s = sessions("2024-01-02", "2024-01-25")
    trading_sessions = all_s[:15]
    prev_start = trading_sessions[0]
    prev_end = trading_sessions[14]
    overlap_start = trading_sessions[5]
    new_end = all_s[15]
    old_known_at = "2024-01-23T22:00:00+00:00"

    bars = []
    for s in trading_sessions:
        for sym in ("SPY", "QQQ", "ALFA"):
            bars.append(Bar(sym, s, 100.0, 105.0, 95.0, 102.0, 1000000.0, old_known_at))
    cap = create_action_capture(
        adapter_version="yfinance-1.7.0",
        history_options={"actions": True, "auto_adjust": False, "back_adjust": False, "repair": False},
        captured_at=old_known_at,
        tickers_info={
            sym: {
                "capital_gains_status": prev_status,
                "instrument_type": "EQUITY" if prev_status == "not_applicable_by_provider" else None,
                "query_intervals": [{"start": prev_start, "end": prev_end, "capital_gains_status": prev_status}],
                "quote_currency": "USD",
            }
            for sym in ("SPY", "QQQ", "ALFA")
        },
        events=[],
    )
    prev = Dataset(
        bars,
        {"source": "yfinance", "quality": "research", "price_basis": "fixture", "action_capture": cap},
        [{"ticker": "ALFA", "active_from": prev_start, "active_to": "2035-12-31",
          "known_at": old_known_at, "sector": None, "industry": None}],
    )

    fetch_dates = pd.to_datetime(trading_sessions + [new_end])
    n_dates = len(fetch_dates)
    df_alfa = pd.DataFrame(
        {
            "Open": [100.0] * n_dates, "High": [105.0] * n_dates, "Low": [95.0] * n_dates, "Close": [102.0] * n_dates,
            "Volume": [1000000.0] * n_dates, "Dividends": [0.0] * n_dates, "Stock Splits": [0.0] * n_dates,
        },
        index=fetch_dates,
    )
    if new_has_cg:
        df_alfa["Capital Gains"] = [0.0] * n_dates

    calls = make_mock_yahoo(
        monkeypatch,
        frames_by_ticker={"ALFA": df_alfa},
        meta_by_ticker={"ALFA": {"instrumentType": new_type, "currency": "USD"}},
        default_has_cg=False,
        version="1.7.0",
    )
    yahoo_dataset(("ALFA",), prev_start, new_end, previous=prev)
    calls_alfa = [kw for sym, kw in calls if sym == "ALFA"]
    assert len(calls_alfa) == 2
    assert calls_alfa[0]["start"] == overlap_start
    assert calls_alfa[1]["start"] == prev_start


def test_conflicting_overlapping_intervals_rejected():
    """상충하는 겹침 interval은 거부"""
    cap = {
        "schema_version": ACTION_CAPTURE_SCHEMA_VERSION,
        "adapter_version": "test",
        "captured_at": "2024-01-05T22:00:00+00:00",
        "history_options": {},
        "tickers": {
            "ALFA": {
                "capital_gains_status": "unknown",
                "instrument_type": "EQUITY",
                "quote_currency": "USD",
                "query_intervals": [
                    {"start": "2024-01-02", "end": "2024-01-05", "capital_gains_status": "present"},
                    {"start": "2024-01-04", "end": "2024-01-08", "capital_gains_status": "unknown"},
                ],
            }
        },
        "events": [],
    }
    with pytest.raises(ValueError, match="Conflicting overlapping query intervals"):
        validate_action_capture(cap)

    # Non-overlapping intervals with different statuses are permitted
    cap_valid = dict(cap)
    cap_valid["tickers"] = {
        "ALFA": {
            "capital_gains_status": "unknown",
            "instrument_type": "EQUITY",
            "quote_currency": "USD",
            "query_intervals": [
                {"start": "2024-01-02", "end": "2024-01-03", "capital_gains_status": "present"},
                {"start": "2024-01-04", "end": "2024-01-08", "capital_gains_status": "unknown"},
            ],
        }
    }
    validate_action_capture(cap_valid)


def test_revision_refetch_preserves_unchanged_events_first_seen_known_at(monkeypatch):
    """한 사건 revision으로 전체 재수집되어도 다른 unchanged 사건의 first-seen known-at 유지"""
    old_known_at = "2024-01-04T22:00:00+00:00"
    bars = []
    for s in ("2024-01-02", "2024-01-03", "2024-01-04"):
        for sym in ("SPY", "QQQ", "ALFA", "BETA"):
            bars.append(Bar(sym, s, 100.0, 105.0, 95.0, 102.0, 1000000.0, old_known_at))

    events = [
        {"ticker": "ALFA", "session": "2024-01-03", "field": "Capital Gains", "amount": 1.0, "known_at": old_known_at},
        {"ticker": "BETA", "session": "2024-01-03", "field": "Capital Gains", "amount": 2.0, "known_at": old_known_at},
    ]
    cap = create_action_capture(
        adapter_version="yfinance-1.7.0",
        history_options={"actions": True, "auto_adjust": False, "back_adjust": False, "repair": False},
        captured_at=old_known_at,
        tickers_info={
            sym: {
                "capital_gains_status": "present",
                "instrument_type": "ETF",
                "query_intervals": [{"start": "2024-01-02", "end": "2024-01-04", "capital_gains_status": "present"}],
                "quote_currency": "USD",
            }
            for sym in ("SPY", "QQQ", "ALFA", "BETA")
        },
        events=events,
    )
    members = [
        {"ticker": sym, "active_from": "2024-01-02", "active_to": "2035-12-31",
         "known_at": old_known_at, "sector": None, "industry": None}
        for sym in ("ALFA", "BETA")
    ]
    prev = Dataset(bars, {"source": "yfinance", "quality": "research", "price_basis": "fixture", "action_capture": cap}, members)

    dates = pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"])
    df_alfa = pd.DataFrame(
        {"Open": [100.0] * 4, "High": [105.0] * 4, "Low": [95.0] * 4, "Close": [102.0] * 4,
         "Volume": [1000000.0] * 4, "Dividends": [0.0] * 4, "Stock Splits": [0.0] * 4,
         "Capital Gains": [0.0, 1.50, 0.0, 0.0]},
        index=dates,
    )
    df_beta = pd.DataFrame(
        {"Open": [100.0] * 4, "High": [105.0] * 4, "Low": [95.0] * 4, "Close": [102.0] * 4,
         "Volume": [1000000.0] * 4, "Dividends": [0.0] * 4, "Stock Splits": [0.0] * 4,
         "Capital Gains": [0.0, 2.00, 0.0, 0.0]},
        index=dates,
    )

    calls = make_mock_yahoo(
        monkeypatch,
        frames_by_ticker={"ALFA": df_alfa, "BETA": df_beta},
        meta_by_ticker={"ALFA": {"instrumentType": "ETF", "currency": "USD"}, "BETA": {"instrumentType": "ETF", "currency": "USD"}},
        default_has_cg=True,
        version="1.7.0",
    )

    fresh = yahoo_dataset(("ALFA", "BETA"), "2024-01-02", "2024-01-05", previous=prev)

    assert any(kw["start"] == "2024-01-02" for sym, kw in calls if sym == "ALFA")

    fresh_events = fresh.metadata["action_capture"]["events"]
    beta_event = next(e for e in fresh_events if e["ticker"] == "BETA")
    alfa_event = next(e for e in fresh_events if e["ticker"] == "ALFA")

    # Unchanged BETA event preserves first-seen known_at
    assert beta_event["amount"] == 2.0
    assert beta_event["known_at"] == old_known_at

    # Modified ALFA event receives new known_at
    assert alfa_event["amount"] == 1.50
    assert alfa_event["known_at"] != old_known_at


def test_modified_event_gets_new_known_at_and_deleted_event_removed(monkeypatch):
    """수정 사건은 새 known-at, 삭제 사건은 제거"""
    old_known_at = "2024-01-04T22:00:00+00:00"
    bars = []
    for s in ("2024-01-02", "2024-01-03", "2024-01-04"):
        for sym in ("SPY", "QQQ", "ALFA", "BETA", "DELT"):
            bars.append(Bar(sym, s, 100.0, 105.0, 95.0, 102.0, 1000000.0, old_known_at))

    events = [
        {"ticker": "ALFA", "session": "2024-01-03", "field": "Capital Gains", "amount": 1.0, "known_at": old_known_at},
        {"ticker": "BETA", "session": "2024-01-03", "field": "Capital Gains", "amount": 2.0, "known_at": old_known_at},
        {"ticker": "DELT", "session": "2024-01-03", "field": "Capital Gains", "amount": 3.0, "known_at": old_known_at},
    ]
    cap = create_action_capture(
        adapter_version="yfinance-1.7.0",
        history_options={"actions": True, "auto_adjust": False, "back_adjust": False, "repair": False},
        captured_at=old_known_at,
        tickers_info={
            sym: {
                "capital_gains_status": "present",
                "instrument_type": "ETF",
                "query_intervals": [{"start": "2024-01-02", "end": "2024-01-04", "capital_gains_status": "present"}],
                "quote_currency": "USD",
            }
            for sym in ("SPY", "QQQ", "ALFA", "BETA", "DELT")
        },
        events=events,
    )
    members = [
        {"ticker": sym, "active_from": "2024-01-02", "active_to": "2035-12-31",
         "known_at": old_known_at, "sector": None, "industry": None}
        for sym in ("ALFA", "BETA", "DELT")
    ]
    prev = Dataset(bars, {"source": "yfinance", "quality": "research", "price_basis": "fixture", "action_capture": cap}, members)

    # In new fetch:
    # ALFA: 1.0 -> 1.5 (modified)
    # BETA: 2.0 -> 0.0 (deleted)
    # DELT: 3.0 -> 3.0 (unchanged)
    dates = pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"])
    df_alfa = pd.DataFrame(
        {"Open": [100.0] * 4, "High": [105.0] * 4, "Low": [95.0] * 4, "Close": [102.0] * 4,
         "Volume": [1000000.0] * 4, "Dividends": [0.0] * 4, "Stock Splits": [0.0] * 4,
         "Capital Gains": [0.0, 1.50, 0.0, 0.0]},
        index=dates,
    )
    df_beta = pd.DataFrame(
        {"Open": [100.0] * 4, "High": [105.0] * 4, "Low": [95.0] * 4, "Close": [102.0] * 4,
         "Volume": [1000000.0] * 4, "Dividends": [0.0] * 4, "Stock Splits": [0.0] * 4,
         "Capital Gains": [0.0, 0.0, 0.0, 0.0]},
        index=dates,
    )
    df_delt = pd.DataFrame(
        {"Open": [100.0] * 4, "High": [105.0] * 4, "Low": [95.0] * 4, "Close": [102.0] * 4,
         "Volume": [1000000.0] * 4, "Dividends": [0.0] * 4, "Stock Splits": [0.0] * 4,
         "Capital Gains": [0.0, 3.00, 0.0, 0.0]},
        index=dates,
    )

    make_mock_yahoo(
        monkeypatch,
        frames_by_ticker={"ALFA": df_alfa, "BETA": df_beta, "DELT": df_delt},
        meta_by_ticker={
            "ALFA": {"instrumentType": "ETF", "currency": "USD"},
            "BETA": {"instrumentType": "ETF", "currency": "USD"},
            "DELT": {"instrumentType": "ETF", "currency": "USD"},
        },
        default_has_cg=True,
        version="1.7.0",
    )

    fresh = yahoo_dataset(("ALFA", "BETA", "DELT"), "2024-01-02", "2024-01-05", previous=prev)

    fresh_events = fresh.metadata["action_capture"]["events"]
    # BETA was deleted -> no event
    assert not any(e["ticker"] == "BETA" for e in fresh_events)

    # ALFA was modified -> new known_at
    alfa_event = next(e for e in fresh_events if e["ticker"] == "ALFA")
    assert alfa_event["amount"] == 1.50
    assert alfa_event["known_at"] != old_known_at

    # DELT was unchanged -> old known_at preserved
    delt_event = next(e for e in fresh_events if e["ticker"] == "DELT")
    assert delt_event["amount"] == 3.00
    assert delt_event["known_at"] == old_known_at


# ============================================================================
# Scenario 1: Non-zero amounts preserved for Capital Gains alone & concurrent
# ============================================================================
def test_scenario_1_capital_gains_alone_and_concurrent_with_dividends(monkeypatch):
    dates = pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"])
    df_alfa = pd.DataFrame(
        {
            "Open": [100.0, 101.0, 102.0, 103.0],
            "High": [105.0, 106.0, 107.0, 108.0],
            "Low": [95.0, 96.0, 97.0, 98.0],
            "Close": [102.0, 103.0, 104.0, 105.0],
            "Volume": [1000000.0] * 4,
            "Dividends": [0.0, 0.0, 0.50, 0.0],
            "Stock Splits": [0.0] * 4,
            "Capital Gains": [0.0, 2.50, 1.75, 0.0],
        },
        index=dates,
    )

    make_mock_yahoo(
        monkeypatch,
        frames_by_ticker={"ALFA": df_alfa},
        meta_by_ticker={"ALFA": {"instrumentType": "ETF", "currency": "USD"}},
        version="1.7.0",
    )

    ds = yahoo_dataset(("ALFA",), "2024-01-02", "2024-01-05")
    cap = ds.metadata.get("action_capture")
    assert cap is not None
    events = cap["events"]

    alfa_events = [e for e in events if e["ticker"] == "ALFA"]
    assert len(alfa_events) == 2

    e1 = next(e for e in alfa_events if e["session"] == "2024-01-03")
    assert e1["amount"] == 2.50
    assert e1["field"] == "Capital Gains"
    assert ds.by_ticker["ALFA"]["2024-01-03"].dividend == 0.0

    e2 = next(e for e in alfa_events if e["session"] == "2024-01-04")
    assert e2["amount"] == 1.75
    assert e2["field"] == "Capital Gains"
    assert ds.by_ticker["ALFA"]["2024-01-04"].dividend == 0.50


# ============================================================================
# Scenario 2: Status matrix
# ============================================================================
def test_scenario_2_status_matrix(monkeypatch):
    dates = pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"])

    def base_df(has_cg):
        d = {
            "Open": [100.0] * 4,
            "High": [105.0] * 4,
            "Low": [95.0] * 4,
            "Close": [102.0] * 4,
            "Volume": [1000000.0] * 4,
            "Dividends": [0.0] * 4,
            "Stock Splits": [0.0] * 4,
        }
        if has_cg:
            d["Capital Gains"] = [0.0] * 4
        return pd.DataFrame(d, index=dates)

    frames = {
        "ALFA": base_df(has_cg=False),
        "BETA": base_df(has_cg=False),
        "GAMA": base_df(has_cg=False),
        "DELT": base_df(has_cg=True),
    }
    metas = {
        "ALFA": {"instrumentType": "EQUITY", "currency": "USD"},
        "BETA": {"instrumentType": "ETF", "currency": "USD"},
        "GAMA": {"instrumentType": None, "currency": "USD"},
        "DELT": {"instrumentType": "EQUITY", "currency": "USD"},
    }

    make_mock_yahoo(monkeypatch, frames_by_ticker=frames, meta_by_ticker=metas, version="1.7.0")

    ds = yahoo_dataset(("ALFA", "BETA", "GAMA", "DELT"), "2024-01-02", "2024-01-05")
    tickers_info = ds.metadata["action_capture"]["tickers"]

    assert tickers_info["ALFA"]["capital_gains_status"] == "not_applicable_by_provider"
    assert tickers_info["BETA"]["capital_gains_status"] == "unknown"
    assert tickers_info["GAMA"]["capital_gains_status"] == "unknown"
    assert tickers_info["DELT"]["capital_gains_status"] == "present"


# ============================================================================
# Scenario 3: Negative, NaN, Inf, invalid values raise ValueError
# ============================================================================
@pytest.mark.parametrize(
    "invalid_val",
    [-1.0, -0.001, float("nan"), float("inf"), float("-inf"), "corrupt", None],
)
def test_scenario_3_invalid_capital_gains_values_rejected(monkeypatch, invalid_val):
    dates = pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"])
    df = pd.DataFrame(
        {
            "Open": [100.0] * 4,
            "High": [105.0] * 4,
            "Low": [95.0] * 4,
            "Close": [102.0] * 4,
            "Volume": [1000000.0] * 4,
            "Dividends": [0.0] * 4,
            "Stock Splits": [0.0] * 4,
            "Capital Gains": [0.0, invalid_val, 0.0, 0.0],
        },
        index=dates,
    )
    make_mock_yahoo(monkeypatch, frames_by_ticker={"ALFA": df}, version="1.7.0")

    with pytest.raises(ValueError, match="Capital Gains"):
        yahoo_dataset(("ALFA",), "2024-01-02", "2024-01-05")


# ============================================================================
# Scenario 4: CSV column present, absent (unknown), and invalid/empty values
# ============================================================================
def test_scenario_4_csv_import_present_absent_and_invalid(tmp_path):
    members_file = tmp_path / "members.csv"
    members_file.write_text(
        "ticker,active_from,active_to,known_at,sector,industry\n"
        "ALFA,2024-01-02,2024-01-05,2024-01-02T22:00:00+00:00,Tech,Software\n",
        encoding="utf-8",
    )

    # 4a: Column present with valid non-zero capital_gains
    csv_present = tmp_path / "bars_present.csv"
    csv_present.write_text(
        "ticker,session,open,high,low,close,volume,known_at,dividend,split,capital_gains\n"
        "ALFA,2024-01-02,100,105,95,102,1000000,2024-01-02T22:00:00+00:00,0,0,0\n"
        "ALFA,2024-01-03,101,106,96,103,1000000,2024-01-03T22:00:00+00:00,0,0,1.50\n"
        "ALFA,2024-01-04,102,107,97,104,1000000,2024-01-04T22:00:00+00:00,0.25,0,0\n"
        "ALFA,2024-01-05,103,108,98,105,1000000,2024-01-05T22:00:00+00:00,0,0,0\n",
        encoding="utf-8",
    )
    ds_present = import_csv(csv_present, members_file)
    cap = ds_present.metadata["action_capture"]
    assert cap["tickers"]["ALFA"]["capital_gains_status"] == "present"
    assert len(cap["events"]) == 1
    assert cap["events"][0]["session"] == "2024-01-03"
    assert cap["events"][0]["amount"] == 1.50
    assert cap["events"][0]["field"] == "capital_gains"
    assert not hasattr(ds_present.bars[0], "capital_gains")
    assert "dividend_basis" not in ds_present.metadata

    # 4b: Column absent -> status unknown, events empty
    csv_absent = tmp_path / "bars_absent.csv"
    csv_absent.write_text(
        "ticker,session,open,high,low,close,volume,known_at,dividend,split\n"
        "ALFA,2024-01-02,100,105,95,102,1000000,2024-01-02T22:00:00+00:00,0,0\n"
        "ALFA,2024-01-03,101,106,96,103,1000000,2024-01-03T22:00:00+00:00,0,0\n",
        encoding="utf-8",
    )
    ds_absent = import_csv(csv_absent, members_file)
    assert ds_absent.metadata["action_capture"]["tickers"]["ALFA"]["capital_gains_status"] == "unknown"
    assert ds_absent.metadata["action_capture"]["events"] == []

    # 4c: Column present but contains invalid value (empty, negative, non-numeric)
    for bad_val in ("", "  ", "-2.0", "NaN", "null", "invalid"):
        csv_bad = tmp_path / f"bars_bad_{bad_val.strip()}.csv"
        csv_bad.write_text(
            "ticker,session,open,high,low,close,volume,known_at,dividend,split,capital_gains\n"
            f"ALFA,2024-01-02,100,105,95,102,1000000,2024-01-02T22:00:00+00:00,0,0,{bad_val}\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError):
            import_csv(csv_bad, members_file)


# ============================================================================
# Scenario 5: Store save & reload preserves event info and Dataset.id
# ============================================================================
def test_scenario_5_store_save_and_reload(tmp_path):
    ds = synthetic_dataset(n=50, symbols=("ALFA",))
    cap = dict(ds.metadata["action_capture"])
    cap["events"] = [
        {
            "ticker": "ALFA",
            "session": ds.sessions[5],
            "field": "Capital Gains",
            "amount": 3.25,
            "known_at": ds.bars[5].known_at,
        }
    ]
    meta = dict(ds.metadata)
    meta["action_capture"] = cap
    ds_with_events = Dataset(ds.bars, meta, ds.members)

    db_path = tmp_path / "test.db"
    with Store(db_path) as store:
        saved_id = store.save_dataset(ds_with_events)
        assert saved_id == ds_with_events.id

        reloaded = store.load_dataset(saved_id)
        assert reloaded.id == ds_with_events.id
        assert reloaded.metadata == ds_with_events.metadata
        assert reloaded.metadata["action_capture"] == cap
        assert len(reloaded.bars) == len(ds_with_events.bars)


# ============================================================================
# Scenario 6: Legacy format dataset ID, metadata, and bars unchanged without action_capture
# ============================================================================
def test_scenario_6_legacy_dataset_compatibility(tmp_path):
    ds_raw = synthetic_dataset(n=50, symbols=("ALFA",))
    legacy_meta = {
        "source": "legacy-supplier",
        "quality": "research",
        "price_basis": "legacy-prices",
    }
    legacy_ds = Dataset(ds_raw.bars, legacy_meta, ds_raw.members)

    assert "action_capture" not in legacy_ds.metadata

    db_path = tmp_path / "legacy_test.db"
    with Store(db_path) as store:
        store.save_dataset(legacy_ds)
        reloaded = store.load_dataset(legacy_ds.id)
        assert reloaded.id == legacy_ds.id
        assert "action_capture" not in reloaded.metadata
        assert reloaded.metadata == legacy_meta


# ============================================================================
# Scenario 7: Previous vintage without action_capture triggers full re-collection
# ============================================================================
def test_scenario_7_missing_action_capture_triggers_full_refetch(monkeypatch):
    data = synthetic_dataset(n=20, symbols=("ALFA",))
    legacy_meta = {"source": "yfinance", "quality": "research", "price_basis": "fixture"}
    legacy_prev = Dataset(data.bars, legacy_meta, data.members)

    calls = make_mock_yahoo(monkeypatch, version="1.7.0")
    fresh = yahoo_dataset(("ALFA",), legacy_prev.start, legacy_prev.end, previous=legacy_prev)

    assert all(kw["start"] == legacy_prev.start for _, kw in calls)
    assert "action_capture" in fresh.metadata


# ============================================================================
# Scenario 8: Overlap revision on event addition, modification, deletion, disappearance
# ============================================================================
def test_scenario_8_overlap_revisions_trigger_full_refresh(monkeypatch):
    all_s = sessions("2024-01-02", "2024-01-25")
    trading_sessions = all_s[:15]
    prev_start = trading_sessions[0]
    prev_end = trading_sessions[14]
    overlap_start = trading_sessions[5]
    new_end = all_s[15]
    old_known_at = "2024-01-23T22:00:00+00:00"
    event_session = trading_sessions[6]

    all_dates = pd.to_datetime(trading_sessions + [new_end])
    n_dates = len(all_dates)
    idx_ev = trading_sessions.index(event_session)

    def make_prev(event_amt=None, has_cg_col=True):
        bars = []
        for s in trading_sessions:
            for sym in ("SPY", "QQQ", "ALFA"):
                bars.append(Bar(sym, s, 100.0, 105.0, 95.0, 102.0, 1000000.0, old_known_at))
        events = []
        status = "present" if has_cg_col else "not_applicable_by_provider"
        if event_amt is not None and event_amt > 0:
            events.append({
                "ticker": "ALFA",
                "session": event_session,
                "field": "Capital Gains",
                "amount": event_amt,
                "known_at": old_known_at,
            })
        cap = create_action_capture(
            adapter_version="yfinance-1.7.0",
            history_options={"actions": True, "auto_adjust": False, "back_adjust": False, "repair": False},
            captured_at=old_known_at,
            tickers_info={
                sym: {
                    "capital_gains_status": status,
                    "instrument_type": "EQUITY",
                    "query_intervals": [{"start": prev_start, "end": prev_end, "capital_gains_status": status}],
                    "quote_currency": "USD",
                }
                for sym in ("SPY", "QQQ", "ALFA")
            },
            events=events,
        )
        meta = {"source": "yfinance", "quality": "research", "price_basis": "fixture", "action_capture": cap}
        members = [{"ticker": "ALFA", "active_from": prev_start, "active_to": "2035-12-31",
                    "known_at": old_known_at, "sector": None, "industry": None}]
        return Dataset(bars, meta, members)

    def make_frame(cg_series=None):
        d = {
            "Open": [100.0] * n_dates, "High": [105.0] * n_dates, "Low": [95.0] * n_dates, "Close": [102.0] * n_dates,
            "Volume": [1000000.0] * n_dates, "Dividends": [0.0] * n_dates, "Stock Splits": [0.0] * n_dates,
        }
        if cg_series is not None:
            d["Capital Gains"] = cg_series
        return pd.DataFrame(d, index=all_dates)

    # 8a: Event addition in overlap (prev had 0/none, new has 1.50 on event_session)
    prev_a = make_prev(event_amt=None, has_cg_col=True)
    cg_add = [0.0] * n_dates
    cg_add[idx_ev] = 1.50
    df_add = make_frame(cg_add)
    calls_a = make_mock_yahoo(monkeypatch, frames_by_ticker={"ALFA": df_add}, default_has_cg=True, version="1.7.0")
    yahoo_dataset(("ALFA",), prev_start, new_end, previous=prev_a)
    calls_a_alfa = [kw for sym, kw in calls_a if sym == "ALFA"]
    assert len(calls_a_alfa) == 2
    assert calls_a_alfa[0]["start"] == overlap_start
    assert calls_a_alfa[1]["start"] == prev_start

    # 8b: Event modification in overlap (prev had 1.0, new has 2.0 on event_session)
    prev_b = make_prev(event_amt=1.0, has_cg_col=True)
    cg_mod = [0.0] * n_dates
    cg_mod[idx_ev] = 2.0
    df_mod = make_frame(cg_mod)
    calls_b = make_mock_yahoo(monkeypatch, frames_by_ticker={"ALFA": df_mod}, default_has_cg=True, version="1.7.0")
    yahoo_dataset(("ALFA",), prev_start, new_end, previous=prev_b)
    calls_b_alfa = [kw for sym, kw in calls_b if sym == "ALFA"]
    assert len(calls_b_alfa) == 2
    assert calls_b_alfa[0]["start"] == overlap_start
    assert calls_b_alfa[1]["start"] == prev_start

    # 8c: Event deletion (0.0) in overlap (prev had 1.0, new has 0.0 on event_session)
    prev_c = make_prev(event_amt=1.0, has_cg_col=True)
    cg_del = [0.0] * n_dates
    df_del = make_frame(cg_del)
    calls_c = make_mock_yahoo(monkeypatch, frames_by_ticker={"ALFA": df_del}, default_has_cg=True, version="1.7.0")
    yahoo_dataset(("ALFA",), prev_start, new_end, previous=prev_c)
    calls_c_alfa = [kw for sym, kw in calls_c if sym == "ALFA"]
    assert len(calls_c_alfa) == 2
    assert calls_c_alfa[0]["start"] == overlap_start
    assert calls_c_alfa[1]["start"] == prev_start

    # 8d: Field disappearance (prev had column present, new frame omits Capital Gains column)
    prev_d = make_prev(event_amt=None, has_cg_col=True)
    df_disappear = make_frame(None)
    calls_d = make_mock_yahoo(monkeypatch, frames_by_ticker={"ALFA": df_disappear}, default_has_cg=True, version="1.7.0")
    yahoo_dataset(("ALFA",), prev_start, new_end, previous=prev_d)
    calls_d_alfa = [kw for sym, kw in calls_d if sym == "ALFA"]
    assert len(calls_d_alfa) == 2
    assert calls_d_alfa[0]["start"] == overlap_start
    assert calls_d_alfa[1]["start"] == prev_start


# ============================================================================
# Scenario 9: Incremental merge preserves first-seen known_at
# ============================================================================
def test_scenario_9_incremental_merge_preserves_first_seen_known_at(monkeypatch):
    old_known_at = "2024-01-04T22:00:00+00:00"
    bars = []
    for s in ("2024-01-02", "2024-01-03", "2024-01-04"):
        for sym in ("SPY", "QQQ", "ALFA"):
            bars.append(Bar(sym, s, 100.0, 105.0, 95.0, 102.0, 1000000.0, old_known_at))

    old_event = {
        "ticker": "ALFA",
        "session": "2024-01-03",
        "field": "Capital Gains",
        "amount": 1.20,
        "known_at": old_known_at,
    }
    cap = create_action_capture(
        adapter_version="yfinance-1.7.0",
        history_options={"actions": True, "auto_adjust": False, "back_adjust": False, "repair": False},
        captured_at=old_known_at,
        tickers_info={
            sym: {
                "capital_gains_status": "present",
                "instrument_type": "ETF",
                "query_intervals": [{"start": "2024-01-02", "end": "2024-01-04", "capital_gains_status": "present"}],
                "quote_currency": "USD",
            }
            for sym in ("SPY", "QQQ", "ALFA")
        },
        events=[old_event],
    )
    prev = Dataset(
        bars,
        {"source": "yfinance", "quality": "research", "price_basis": "fixture", "action_capture": cap},
        [{"ticker": "ALFA", "active_from": "2024-01-02", "active_to": "2035-12-31",
          "known_at": old_known_at, "sector": None, "industry": None}],
    )

    dates = pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"])
    df_fresh = pd.DataFrame(
        {
            "Open": [100.0] * 4, "High": [105.0] * 4, "Low": [95.0] * 4, "Close": [102.0] * 4,
            "Volume": [1000000.0] * 4, "Dividends": [0.0] * 4, "Stock Splits": [0.0] * 4,
            "Capital Gains": [0.0, 1.20, 0.0, 2.40],
        },
        index=dates,
    )
    make_mock_yahoo(
        monkeypatch,
        frames_by_ticker={"ALFA": df_fresh},
        meta_by_ticker={"ALFA": {"instrumentType": "ETF", "currency": "USD"}},
        default_has_cg=True,
        version="1.7.0",
    )

    fresh = yahoo_dataset(("ALFA",), "2024-01-02", "2024-01-05", previous=prev)
    fresh_events = fresh.metadata["action_capture"]["events"]
    assert len(fresh_events) == 2

    e_overlap = next(e for e in fresh_events if e["session"] == "2024-01-03")
    assert e_overlap["known_at"] == old_known_at

    e_new = next(e for e in fresh_events if e["session"] == "2024-01-05")
    assert e_new["known_at"] != old_known_at
    assert e_new["amount"] == 2.40


# ============================================================================
# Scenario 10: New Yahoo dataset does NOT have dividend_basis created or inherited
# ============================================================================
def test_scenario_10_no_dividend_basis_created_or_inherited(monkeypatch):
    data = synthetic_dataset(n=20, symbols=("ALFA",))
    make_mock_yahoo(monkeypatch, version="1.7.0")
    fresh = yahoo_dataset(("ALFA",), data.start, data.end, previous=None)
    assert "dividend_basis" not in fresh.metadata

    capture = dict(data.metadata["action_capture"])
    capture["adapter_version"] = "yfinance-1.7.0"
    capture["history_options"] = {
        "actions": True,
        "auto_adjust": False,
        "back_adjust": False,
        "repair": False,
    }
    capture["tickers"] = {
        sym: {
            "capital_gains_status": "unknown",
            "instrument_type": None,
            "query_intervals": [{"start": data.start, "end": data.end, "capital_gains_status": "unknown"}],
            "quote_currency": "USD",
        }
        for sym in ("SPY", "QQQ", "ALFA")
    }
    prev_with_basis = Dataset(
        data.bars,
        {
            "source": "yfinance",
            "quality": "research",
            "price_basis": "fixture",
            "dividend_basis": VERIFIED_DIVIDEND_BASIS,
            "action_capture": capture,
        },
        data.members,
    )
    fresh_incremental = yahoo_dataset(("ALFA",), data.start, data.end, previous=prev_with_basis)
    assert "dividend_basis" not in fresh_incremental.metadata


# ============================================================================
# Scenario 11: Synthetic action capture determinism and synthetic marking
# ============================================================================
def test_scenario_11_synthetic_action_capture_determinism_and_marking():
    ds1 = synthetic_dataset(n=60, symbols=("ALFA", "BETA"), seed=123)
    ds2 = synthetic_dataset(n=60, symbols=("ALFA", "BETA"), seed=123)

    assert ds1.id == ds2.id
    assert ds1.metadata == ds2.metadata

    cap = ds1.metadata.get("action_capture")
    assert cap is not None
    assert cap["schema_version"] == ACTION_CAPTURE_SCHEMA_VERSION
    assert cap["adapter_version"] == "synthetic"
    assert cap["events"] == []
    assert cap["captured_at"] == cutoff_at(ds1.sessions[-1]).isoformat()

    for sym in ("SPY", "QQQ", "ALFA", "BETA"):
        tinfo = cap["tickers"][sym]
        assert tinfo["instrument_type"] == "SYNTHETIC"
        assert tinfo["capital_gains_status"] == "not_applicable_by_provider"
        assert tinfo["query_intervals"] == [
            {"start": ds1.sessions[0], "end": ds1.sessions[-1], "capital_gains_status": "not_applicable_by_provider"}
        ]


# ============================================================================
# Scenario 12: Ticker metadata changes and provenance (R2-1-R2 Requirements)
# ============================================================================
@pytest.mark.parametrize(
    "old_type,old_curr,new_type,new_curr",
    [
        ("ETF", "USD", "MUTUALFUND", "EUR"),   # both change
        ("ETF", "USD", "MUTUALFUND", "USD"),   # instrument_type change
        ("ETF", "USD", "ETF", "EUR"),          # quote_currency change
        (None, "USD", "EQUITY", "USD"),        # None -> value (type)
        ("EQUITY", "USD", None, "USD"),        # value -> None (type)
        ("EQUITY", None, "EQUITY", "USD"),     # None -> value (curr)
        ("EQUITY", "USD", "EQUITY", None),     # value -> None (curr)
    ],
)
def test_ticker_metadata_change_triggers_full_refetch(monkeypatch, old_type, old_curr, new_type, new_curr):
    """Ticker metadata 변경 시 overlap 1회 + full 1회 총 2회 호출, 새 메타데이터 저장, 불변 사건 known_at 보존, 이전 dataset 불변"""
    all_s = sessions("2024-01-02", "2024-01-25")
    trading_sessions = all_s[:15]
    prev_start = trading_sessions[0]
    prev_end = trading_sessions[14]
    overlap_start = trading_sessions[5]
    new_end = all_s[15]
    old_known_at = "2024-01-23T22:00:00+00:00"
    event_session = trading_sessions[2]

    bars = []
    for s in trading_sessions:
        for sym in ("SPY", "QQQ", "ALFA"):
            bars.append(Bar(sym, s, 100.0, 105.0, 95.0, 102.0, 1000000.0, old_known_at))

    old_event = {
        "ticker": "ALFA",
        "session": event_session,
        "field": "Capital Gains",
        "amount": 1.25,
        "known_at": old_known_at,
    }
    cap = create_action_capture(
        adapter_version="yfinance-1.7.0",
        history_options={"actions": True, "auto_adjust": False, "back_adjust": False, "repair": False},
        captured_at=old_known_at,
        tickers_info={
            "ALFA": {
                "capital_gains_status": "present",
                "instrument_type": old_type,
                "query_intervals": [{"start": prev_start, "end": prev_end, "capital_gains_status": "present"}],
                "quote_currency": old_curr,
            },
            "SPY": {
                "capital_gains_status": "present",
                "instrument_type": "EQUITY",
                "query_intervals": [{"start": prev_start, "end": prev_end, "capital_gains_status": "present"}],
                "quote_currency": "USD",
            },
            "QQQ": {
                "capital_gains_status": "present",
                "instrument_type": "EQUITY",
                "query_intervals": [{"start": prev_start, "end": prev_end, "capital_gains_status": "present"}],
                "quote_currency": "USD",
            },
        },
        events=[old_event],
    )
    prev = Dataset(
        bars,
        {"source": "yfinance", "quality": "research", "price_basis": "fixture", "action_capture": cap},
        [{"ticker": "ALFA", "active_from": prev_start, "active_to": "2035-12-31",
          "known_at": old_known_at, "sector": None, "industry": None}],
    )

    fetch_dates = pd.to_datetime(trading_sessions + [new_end])
    n_dates = len(fetch_dates)
    cg = [0.0] * n_dates
    cg[trading_sessions.index(event_session)] = 1.25
    df_alfa = pd.DataFrame(
        {
            "Open": [100.0] * n_dates, "High": [105.0] * n_dates, "Low": [95.0] * n_dates, "Close": [102.0] * n_dates,
            "Volume": [1000000.0] * n_dates, "Dividends": [0.0] * n_dates, "Stock Splits": [0.0] * n_dates,
            "Capital Gains": cg,
        },
        index=fetch_dates,
    )

    calls = make_mock_yahoo(
        monkeypatch,
        frames_by_ticker={"ALFA": df_alfa},
        meta_by_ticker={
            "ALFA": {"instrumentType": new_type, "currency": new_curr},
            "SPY": {"instrumentType": "EQUITY", "currency": "USD"},
            "QQQ": {"instrumentType": "EQUITY", "currency": "USD"},
        },
        default_has_cg=True,
        version="1.7.0",
    )
    fresh = yahoo_dataset(("ALFA",), prev_start, new_end, previous=prev)

    # 1. 2회 호출 검증 (1회: overlap, 2회: start부터 full refetch)
    calls_alfa = [kw for sym, kw in calls if sym == "ALFA"]
    assert len(calls_alfa) == 2
    assert calls_alfa[0]["start"] == overlap_start
    assert calls_alfa[1]["start"] == prev_start

    # 2. 신규 응답의 metadata 기록 (과거 값으로 fallback 안함)
    fresh_alfa_info = fresh.metadata["action_capture"]["tickers"]["ALFA"]
    assert fresh_alfa_info["instrument_type"] == new_type
    assert fresh_alfa_info["quote_currency"] == new_curr

    # 3. 이전 dataset 불변성 확인
    assert prev.metadata["action_capture"]["tickers"]["ALFA"]["instrument_type"] == old_type
    assert prev.metadata["action_capture"]["tickers"]["ALFA"]["quote_currency"] == old_curr

    # 4. 불변 사건의 최초 발견 known_at 보존
    fresh_events = fresh.metadata["action_capture"]["events"]
    alfa_ev = next(e for e in fresh_events if e["ticker"] == "ALFA")
    assert alfa_ev["amount"] == 1.25
    assert alfa_ev["known_at"] == old_known_at


def test_identical_metadata_normal_incremental_fetch_single_call(monkeypatch):
    """Metadata와 사건이 동일할 때 단 1회 호출(overlap만) 및 기존 병합 유지 확인"""
    all_s = sessions("2024-01-02", "2024-01-25")
    trading_sessions = all_s[:15]
    prev_start = trading_sessions[0]
    prev_end = trading_sessions[14]
    overlap_start = trading_sessions[5]
    new_end = all_s[15]
    old_known_at = "2024-01-23T22:00:00+00:00"

    bars = []
    for s in trading_sessions:
        for sym in ("SPY", "QQQ", "ALFA"):
            bars.append(Bar(sym, s, 100.0, 105.0, 95.0, 102.0, 1000000.0, old_known_at))
    cap = create_action_capture(
        adapter_version="yfinance-1.7.0",
        history_options={"actions": True, "auto_adjust": False, "back_adjust": False, "repair": False},
        captured_at=old_known_at,
        tickers_info={
            sym: {
                "capital_gains_status": "present",
                "instrument_type": "EQUITY",
                "query_intervals": [{"start": prev_start, "end": prev_end, "capital_gains_status": "present"}],
                "quote_currency": "USD",
            }
            for sym in ("SPY", "QQQ", "ALFA")
        },
        events=[],
    )
    prev = Dataset(
        bars,
        {"source": "yfinance", "quality": "research", "price_basis": "fixture", "action_capture": cap},
        [{"ticker": "ALFA", "active_from": prev_start, "active_to": "2035-12-31",
          "known_at": old_known_at, "sector": None, "industry": None}],
    )

    fetch_dates = pd.to_datetime(trading_sessions + [new_end])
    n_dates = len(fetch_dates)
    df_alfa = pd.DataFrame(
        {
            "Open": [100.0] * n_dates, "High": [105.0] * n_dates, "Low": [95.0] * n_dates, "Close": [102.0] * n_dates,
            "Volume": [1000000.0] * n_dates, "Dividends": [0.0] * n_dates, "Stock Splits": [0.0] * n_dates,
            "Capital Gains": [0.0] * n_dates,
        },
        index=fetch_dates,
    )

    calls = make_mock_yahoo(
        monkeypatch,
        frames_by_ticker={"ALFA": df_alfa},
        meta_by_ticker={"ALFA": {"instrumentType": "EQUITY", "currency": "USD"}},
        default_has_cg=True,
        version="1.7.0",
    )
    fresh = yahoo_dataset(("ALFA",), prev_start, new_end, previous=prev)

    # 단 1회 호출 (overlap만)
    calls_alfa = [kw for sym, kw in calls if sym == "ALFA"]
    assert len(calls_alfa) == 1
    assert calls_alfa[0]["start"] == overlap_start

    fresh_alfa_info = fresh.metadata["action_capture"]["tickers"]["ALFA"]
    assert fresh_alfa_info["instrument_type"] == "EQUITY"
    assert fresh_alfa_info["quote_currency"] == "USD"
    # 병합된 바 수: 16 trading days * 3 symbols = 48
    assert len(fresh.bars) == 16 * 3


def test_metadata_revision_modified_and_deleted_events(monkeypatch):
    """Metadata 변경으로 전체 재수집 발생 시: 수정 사건은 새 known-at, 삭제 사건 제거, 불변 사건 known-at 유지"""
    all_s = sessions("2024-01-02", "2024-01-25")
    trading_sessions = all_s[:15]
    prev_start = trading_sessions[0]
    prev_end = trading_sessions[14]
    overlap_start = trading_sessions[5]
    new_end = all_s[15]
    old_known_at = "2024-01-23T22:00:00+00:00"
    ev_session = trading_sessions[2]

    bars = []
    for s in trading_sessions:
        for sym in ("SPY", "QQQ", "ALFA", "BETA", "DELT"):
            bars.append(Bar(sym, s, 100.0, 105.0, 95.0, 102.0, 1000000.0, old_known_at))

    events = [
        {"ticker": "ALFA", "session": ev_session, "field": "Capital Gains", "amount": 1.0, "known_at": old_known_at},
        {"ticker": "BETA", "session": ev_session, "field": "Capital Gains", "amount": 2.0, "known_at": old_known_at},
        {"ticker": "DELT", "session": ev_session, "field": "Capital Gains", "amount": 3.0, "known_at": old_known_at},
    ]
    cap = create_action_capture(
        adapter_version="yfinance-1.7.0",
        history_options={"actions": True, "auto_adjust": False, "back_adjust": False, "repair": False},
        captured_at=old_known_at,
        tickers_info={
            "ALFA": {
                "capital_gains_status": "present",
                "instrument_type": "ETF",
                "query_intervals": [{"start": prev_start, "end": prev_end, "capital_gains_status": "present"}],
                "quote_currency": "USD",
            },
            "BETA": {
                "capital_gains_status": "present",
                "instrument_type": "ETF",
                "query_intervals": [{"start": prev_start, "end": prev_end, "capital_gains_status": "present"}],
                "quote_currency": "USD",
            },
            "DELT": {
                "capital_gains_status": "present",
                "instrument_type": "ETF",
                "query_intervals": [{"start": prev_start, "end": prev_end, "capital_gains_status": "present"}],
                "quote_currency": "USD",
            },
            "SPY": {
                "capital_gains_status": "present",
                "instrument_type": "ETF",
                "query_intervals": [{"start": prev_start, "end": prev_end, "capital_gains_status": "present"}],
                "quote_currency": "USD",
            },
            "QQQ": {
                "capital_gains_status": "present",
                "instrument_type": "ETF",
                "query_intervals": [{"start": prev_start, "end": prev_end, "capital_gains_status": "present"}],
                "quote_currency": "USD",
            },
        },
        events=events,
    )
    prev = Dataset(
        bars,
        {"source": "yfinance", "quality": "research", "price_basis": "fixture", "action_capture": cap},
        [{"ticker": sym, "active_from": prev_start, "active_to": "2035-12-31",
          "known_at": old_known_at, "sector": None, "industry": None}
         for sym in ("ALFA", "BETA", "DELT")],
    )

    fetch_dates = pd.to_datetime(trading_sessions + [new_end])
    n_dates = len(fetch_dates)
    idx_ev = trading_sessions.index(ev_session)

    cg_alfa = [0.0] * n_dates
    cg_alfa[idx_ev] = 1.50  # modified

    cg_beta = [0.0] * n_dates
    cg_beta[idx_ev] = 0.00  # deleted

    cg_delt = [0.0] * n_dates
    cg_delt[idx_ev] = 3.00  # unchanged

    def make_df(cg):
        return pd.DataFrame(
            {
                "Open": [100.0] * n_dates, "High": [105.0] * n_dates, "Low": [95.0] * n_dates, "Close": [102.0] * n_dates,
                "Volume": [1000000.0] * n_dates, "Dividends": [0.0] * n_dates, "Stock Splits": [0.0] * n_dates,
                "Capital Gains": cg,
            },
            index=fetch_dates,
        )

    # ALFA's metadata changes: ETF/USD -> MUTUALFUND/EUR
    calls = make_mock_yahoo(
        monkeypatch,
        frames_by_ticker={"ALFA": make_df(cg_alfa), "BETA": make_df(cg_beta), "DELT": make_df(cg_delt)},
        meta_by_ticker={
            "ALFA": {"instrumentType": "MUTUALFUND", "currency": "EUR"},
            "BETA": {"instrumentType": "ETF", "currency": "USD"},
            "DELT": {"instrumentType": "ETF", "currency": "USD"},
            "SPY": {"instrumentType": "ETF", "currency": "USD"},
            "QQQ": {"instrumentType": "ETF", "currency": "USD"},
        },
        default_has_cg=True,
        version="1.7.0",
    )
    fresh = yahoo_dataset(("ALFA", "BETA", "DELT"), prev_start, new_end, previous=prev)

    # Calls check: revision triggered -> 2 calls
    calls_alfa = [kw for sym, kw in calls if sym == "ALFA"]
    assert len(calls_alfa) == 2
    assert calls_alfa[0]["start"] == overlap_start
    assert calls_alfa[1]["start"] == prev_start

    fresh_events = fresh.metadata["action_capture"]["events"]
    # BETA deleted -> no event
    assert not any(e["ticker"] == "BETA" for e in fresh_events)

    # ALFA modified -> new known_at
    alfa_event = next(e for e in fresh_events if e["ticker"] == "ALFA")
    assert alfa_event["amount"] == 1.50
    assert alfa_event["known_at"] != old_known_at

    # DELT unchanged -> old known_at preserved
    delt_event = next(e for e in fresh_events if e["ticker"] == "DELT")
    assert delt_event["amount"] == 3.00
    assert delt_event["known_at"] == old_known_at

    # New metadata recorded for ALFA
    assert fresh.metadata["action_capture"]["tickers"]["ALFA"]["instrument_type"] == "MUTUALFUND"
    assert fresh.metadata["action_capture"]["tickers"]["ALFA"]["quote_currency"] == "EUR"

