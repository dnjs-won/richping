"""M2-1B mathematical, production, PIT and diagnostic contracts (synthetic only)."""
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from richping.core import Config, canonical, cutoff_at, code_hash
from richping.coverage import coverage_report, window_reasons
from richping.data import Bar, Dataset, synthetic_dataset, _feature_dividend_events
from richping.engine import Engine, features, observe
from richping.feature_window import DIVIDEND_UNIT, FEATURE_VERSION, feature_window, normalize_dividends


def fixture(events=(), n=150):
    base = synthetic_dataset(n=n, symbols=("ALFA",))
    meta = deepcopy(base.metadata)
    meta.update(source="yfinance", price_basis="Yahoo split-adjusted OHLC; unadjusted for cash dividends")
    cap = meta["action_capture"]
    cap.update(adapter_version="yfinance-1.7.0", history_options={
        "actions": True, "auto_adjust": False, "back_adjust": False, "repair": False})
    for sym, info in cap["tickers"].items():
        info["instrument_type"] = "EQUITY" if sym == "ALFA" else "ETF"
    bars = []
    for sym in ("SPY", "QQQ", "ALFA"):
        price = 100.
        for i, day in enumerate(base.sessions):
            dividend = sum(d for s, index, d in events if s == sym and index == i)
            price = (price - dividend) * (1.004 if sym == "ALFA" else 1.001)
            bars.append(Bar(sym, day, price, price * 1.003, price * .997, price,
                            2_000_000., cutoff_at(day).isoformat(), dividend))
            if dividend:
                cap["events"].append({"ticker": sym, "session": day, "field": "Dividends",
                    "amount": dividend, "known_at": cutoff_at(day).isoformat(),
                    "unit_basis": DIVIDEND_UNIT, "currency": "USD"})
    return Dataset(bars, meta, base.members)


def mechanical(indices):
    base = fixture(n=80)
    price = 100.
    bars = []
    for i, b in enumerate(base.window("ALFA", base.sessions[60], 61, None)):
        d = 1. if i in indices else 0.
        price -= d
        bars.append(replace(b, open=price, close=price, high=price * 1.01, low=price * .99, dividend=d))
    return bars


def test_no_dividend_is_identity_and_deterministic():
    bars = mechanical([])
    assert normalize_dividends(bars) == bars
    assert all(a is b for a, b in zip(normalize_dividends(bars), bars))
    assert normalize_dividends(bars) == normalize_dividends(bars)


@pytest.mark.parametrize("indices", [[1], [40], [60], [1, 30, 60], [0], [0, 1, 60]])
def test_mechanical_gap_ohlc_and_latest_scale(indices):
    bars = mechanical(indices)
    original = list(bars)
    normalized = normalize_dividends(bars, 100.)
    assert bars == original
    assert normalized[-1] == bars[-1]
    assert [b.volume for b in normalized] == [b.volume for b in bars]
    assert [b.close for b in normalized] == pytest.approx([bars[-1].close] * 61)
    for b in normalized:
        assert b.low <= b.open == b.close <= b.high
        assert b.high / b.close == pytest.approx(1.01)
        assert b.low / b.close == pytest.approx(.99)
    f = features(normalized, normalized, bars)
    for name in ("return_1d", "return_5d", "return_20d", "relative_strength", "trend", "realized_vol"):
        assert f[name] == pytest.approx(0., abs=1e-12)
    assert f["ma20"] == pytest.approx(bars[-1].close)
    assert f["ma60"] == pytest.approx(bars[-1].close)
    assert f["atr"] == pytest.approx(.02 * bars[-1].close)
    assert f["breakout_distance"] == pytest.approx(1 / 1.01 - 1)
    assert f["dollar_volume"] == pytest.approx(np.mean([b.close * b.volume for b in bars[-20:]]))
    assert f["relative_volume"] == 1.


@pytest.mark.parametrize("amount,reason", [(float("nan"), "invalid_dividend_amount"),
    (float("inf"), "invalid_dividend_amount"), (-1., "invalid_dividend_amount"),
    (100., "impossible_dividend_adjustment"), (101., "impossible_dividend_adjustment"),
    (25., "large_cash_distribution"), (30., "large_cash_distribution")])
def test_invalid_and_large_distributions_fail_closed(amount, reason):
    bars = mechanical([])
    bars[-1] = replace(bars[-1], dividend=amount)
    with pytest.raises(ValueError, match=reason):
        normalize_dividends(bars)


def test_large_distribution_boundary_and_missing_pre_window_reference():
    bars = mechanical([])
    bars[-1] = replace(bars[-1], dividend=24.99)
    assert normalize_dividends(bars)[-1] == bars[-1]
    bars[0] = replace(bars[0], dividend=1.)
    with pytest.raises(ValueError, match="missing_dividend_reference"):
        normalize_dividends(bars)


@pytest.mark.parametrize("symbols", [("SPY",), ("QQQ",), ("SPY", "QQQ"), ("ALFA",)])
def test_production_dividend_windows_and_raw_stop_target(symbols):
    data = fixture([(s, 80, 1.) for s in symbols])
    before = data.id, canonical(data.metadata), list(data.bars)
    engine = Engine(data, Config(tickers=("ALFA",)))
    signal = engine.signals(data.sessions[85])["candidates"][0]
    window = feature_window(data, "ALFA", data.sessions[85])
    assert signal["features"] == features(window.bars, feature_window(data, "SPY", data.sessions[85]).bars, window.raw)
    price = data.by_ticker["ALFA"][data.sessions[85]].close
    assert signal["entry_reference"] == signal["features"]["price"] == price
    assert signal["stop_reference"] == price - 2 * signal["features"]["atr"]
    assert signal["target_reference"] == price + 4 * signal["features"]["atr"]
    assert signal["feature_normalization"] == FEATURE_VERSION
    outcome = observe(signal, data, 5, cutoff_at(data.end))
    assert outcome["entry_price"] == data.by_ticker["ALFA"][data.sessions[86]].open
    assert outcome["status"] == "COMPLETE"
    assert (data.id, canonical(data.metadata), data.bars) == before


@pytest.mark.parametrize("symbol", ["SPY", "QQQ", "ALFA"])
@pytest.mark.parametrize("kind", ["split", "capital_gains", "capture_unknown", "unknown_action", "basis_unknown"])
def test_unsupported_actions_stay_closed(symbol, kind):
    data = fixture([(symbol, 80, 1.)])
    meta, bars = deepcopy(data.metadata), data.bars
    cap = meta["action_capture"]
    if kind == "split":
        bars = [replace(b, split=2.) if b.ticker == symbol and b.session == data.sessions[80] else b for b in bars]
    elif kind in {"capital_gains", "unknown_action"}:
        cap["events"].append({"ticker": symbol, "session": data.sessions[80], "amount": 1.,
            "known_at": cutoff_at(data.sessions[80]).isoformat(),
            "field": "Capital Gains" if kind == "capital_gains" else "Return of Capital"})
    elif kind == "capture_unknown":
        cap["tickers"].pop(symbol)
    else:
        cap["events"] = []
    altered = Dataset(bars, meta, data.members)
    engine = Engine(altered, Config(tickers=("ALFA",)))
    window = feature_window(altered, symbol, data.sessions[85])
    assert window.blockers and not window.bars
    assert "dividend_unsupported" in window.observations
    if symbol == "ALFA":
        assert symbol in engine.signals(data.sessions[85])["excluded"]
    else:
        with pytest.raises(ValueError):
            engine.signals(data.sessions[85])


def test_exact_window_boundary_and_first_session_dividend():
    data = fixture([("ALFA", 80, 1.)])
    for i in (80, 139, 140):
        assert "dividend_normalized" in feature_window(data, "ALFA", data.sessions[i]).observations
    assert not feature_window(data, "ALFA", data.sessions[141]).observations
    assert feature_window(data, "ALFA", data.sessions[59]).blockers == ("missing_or_unknown_history",)


def test_future_dividend_does_not_change_past_features_or_calibration():
    data, changed = fixture(), fixture([("ALFA", 120, 2.), ("SPY", 125, 1.)])
    config = Config(tickers=("ALFA",))
    a, b = Engine(data, config), Engine(changed, config)
    signal = a.signals(data.sessions[100])["candidates"][0]
    assert a.signals(data.sessions[100]) == b.signals(data.sessions[100])
    assert a.calibration(signal) == b.calibration(signal)


@pytest.mark.parametrize("target", ["bar", "capture", "event", "previous_bar"])
def test_shadow_cutoff_rejects_future_known_inputs(target):
    data = fixture([("ALFA", 80, 1.)])
    day = data.sessions[140]  # Event is at first window session: prior close is also PIT checked.
    meta, bars = deepcopy(data.metadata), data.bars
    cap = meta["action_capture"]
    cap["captured_at"] = cutoff_at(day).isoformat()
    future = cutoff_at(data.sessions[141]).isoformat()
    if target == "capture":
        cap["captured_at"] = future
    elif target == "event":
        cap["events"][0]["known_at"] = future
    else:
        index = 79 if target == "previous_bar" else 140
        bars = [replace(b, known_at=future) if b.ticker == "ALFA" and b.session == data.sessions[index] else b for b in bars]
    changed = Dataset(bars, meta, data.members)
    assert "data_not_yet_known" in feature_window(changed, "ALFA", day, mode="shadow").blockers
    assert not feature_window(changed, "ALFA", day).blockers


def test_history_uses_same_signal_contract_but_v3_labels_still_guarded():
    data = fixture([("ALFA", 80, 1.), ("ALFA", 88, 1.), ("SPY", 80, 1.)])
    engine = Engine(data, Config(tickers=("ALFA",)))
    signal = engine.signals(data.sessions[85])["candidates"][0]
    out = observe(signal, data, 5, cutoff_at(data.end))
    assert out["status"] == "UNRESOLVED" and out["reason"] == "unverified_cash_dividend_event"
    assert not any(r["session"] == signal["session"] for r in engine.history)
    assert any(r["session"] == signal["session"] and r["reason"] == out["reason"] for r in engine.excluded_history)
    later = engine.signals(data.sessions[95])["candidates"][0]
    label = next(r for r in engine.history if r["session"] == later["session"])
    assert label["score"] == later["score"]
    assert label["net_return"] == observe(later, data, 5, cutoff_at(data.end))["net_return"]


def test_coverage_observed_normalized_blocked_and_engine_agree():
    data = fixture([("ALFA", 80, 1.), ("SPY", 80, 1.), ("QQQ", 80, 1.)])
    config = Config(tickers=("ALFA",))
    report = coverage_report(data, config, data.sessions[80], data.sessions[141])
    assert report["trading_days"]["signal_supported"]["count"] == 62
    assert report["signal_blocks"]["by_reason"]["dividend"]["count"] == 0
    assert report["signal_blocks"]["both_benchmarks_dividend"]["count"] == 61
    for symbol in ("SPY", "QQQ"):
        counts = report["benchmark"][symbol]["by_reason"]
        assert counts["dividend"]["count"] == counts["dividend_normalized"]["count"] == 61
        assert counts["dividend_unsupported"]["count"] == 0
    counts = report["candidate_evaluations"]
    assert counts["supported"]["count"] == 62
    assert counts["by_reason"]["dividend_normalized"]["count"] == 61
    assert report["decision_funnel"]["calibration_attempts"]["count"] == 62


@pytest.mark.parametrize("currency,amount,expected", [("USD", 1., 1), ("EUR", 1., 0), ("USD", 100., 0)])
def test_ingestion_preserves_only_matching_cash_units(currency, amount, expected):
    index = pd.to_datetime(["2024-01-02"])
    frame = pd.DataFrame({"Dividends": [1.]}, index=index)
    actions = pd.DataFrame({"Dividends": [amount], "currency": [currency]}, index=index)
    ticker = SimpleNamespace(get_dividends=lambda **kwargs: actions)
    events = _feature_dividend_events(ticker, frame, "ALFA", "USD", "yfinance-1.7.0")
    assert len(events) == expected
    if expected:
        assert events[0]["unit_basis"] == DIVIDEND_UNIT


def test_code_identity_includes_feature_module(monkeypatch):
    from pathlib import Path
    before = code_hash()
    original = Path.read_text
    monkeypatch.setattr(Path, "read_text", lambda p, **kw: original(p, **kw) + ("\n# changed" if p.name == "feature_window.py" else ""))
    assert code_hash() != before


@pytest.mark.parametrize("change", ["adapter", "options", "price_basis", "currency", "unit", "instrument", "duplicate", "amount"])
def test_uncertain_provider_or_unit_evidence_is_not_approved(change):
    data = fixture([("ALFA", 80, 1.)])
    meta = deepcopy(data.metadata)
    cap = meta["action_capture"]
    if change == "adapter":
        cap["adapter_version"] = "yfinance-unknown"
    elif change == "options":
        cap["history_options"]["auto_adjust"] = True
    elif change == "price_basis":
        meta["price_basis"] = "adjusted close"
    elif change == "instrument":
        cap["tickers"]["ALFA"]["instrument_type"] = "MUTUALFUND"
    elif change == "duplicate":
        cap["events"].append(dict(cap["events"][0]))
    else:
        cap["events"][0][{"currency": "currency", "unit": "unit_basis", "amount": "amount"}[change]] = 2. if change == "amount" else "unknown"
    assert feature_window(Dataset(data.bars, meta, data.members), "ALFA", data.sessions[85]).blockers


def test_sidecar_cash_event_without_raw_cash_is_integrity_failure():
    data = fixture([("ALFA", 80, 1.)])
    altered = Dataset([replace(b, dividend=0.) for b in data.bars], data.metadata, data.members)
    assert feature_window(altered, "ALFA", data.sessions[85]).blockers == ("unsupported_corporate_action",)


def test_ingestion_unit_evidence_roundtrip_revision_and_capture_timing(monkeypatch, tmp_path):
    import sys
    from datetime import timedelta
    from richping import data as module
    from richping.store import Store
    source = fixture([("ALFA", 80, 1.)], n=90)
    calls, state = [], {"currency": "USD", "time": cutoff_at(source.end) + timedelta(days=1)}
    class Ticker:
        def __init__(self, symbol):
            self.symbol = symbol
        def history(self, **kw):
            calls.append(kw["start"])
            bars = [b for b in source.by_ticker[self.symbol].values() if kw["start"] <= b.session < kw["end"]]
            return pd.DataFrame([{"Open": b.open, "High": b.high, "Low": b.low, "Close": b.close,
                "Volume": b.volume, "Dividends": b.dividend, "Stock Splits": b.split, "Capital Gains": 0.}
                for b in bars], index=pd.to_datetime([b.session for b in bars]))
        def get_history_metadata(self):
            return {"instrumentType": "EQUITY", "currency": "USD"}
        def get_dividends(self, **kw):
            state["time"] += timedelta(minutes=1)
            return pd.DataFrame({"Dividends": [1.], "currency": [state["currency"]]},
                index=pd.to_datetime([source.sessions[80]]))
    monkeypatch.setitem(sys.modules, "yfinance", SimpleNamespace(Ticker=Ticker, __version__="1.7.0", set_tz_cache_location=lambda _: None))
    monkeypatch.setattr(module, "utcnow", lambda: state["time"].isoformat())
    first = module.yahoo_dataset(("ALFA",), source.start, source.end)
    event = first.metadata["action_capture"]["events"][0]
    assert event["known_at"] == state["time"].isoformat()
    assert not feature_window(first, "ALFA", source.end).blockers
    with Store(tmp_path / "unit.db") as store:
        store.save_dataset(first)
        assert store.load_dataset(first.id).metadata == first.metadata
    state["currency"] = "EUR"
    calls.clear()
    revised = module.yahoo_dataset(("ALFA",), source.start, source.end, previous=first)
    assert source.start in calls  # Lost unit evidence requires a full new vintage.
    assert revised.id != first.id
    assert revised.metadata["action_capture"]["events"] == []
    assert feature_window(revised, "ALFA", source.end).blockers
    assert first.metadata["action_capture"]["events"] == [event]
