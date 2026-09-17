from dataclasses import replace
import sys
from types import SimpleNamespace

import pandas as pd
import pytest

from richping.core import cutoff_at
from richping.data import Dataset, synthetic_dataset, yahoo_dataset


def yahoo_fixture():
    data = synthetic_dataset(n=100, symbols=("ALFA",))
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
    meta = {
        "source": "yfinance",
        "quality": "research",
        "price_basis": "fixture",
        "action_capture": capture,
    }
    return Dataset(data.bars, meta, data.members)


def fake_yahoo(monkeypatch, data, error=False):
    calls = []
    class Ticker:
        def __init__(self, symbol):
            self.symbol = symbol
        def history(self, **kwargs):
            calls.append((self.symbol, kwargs))
            if error:
                raise OSError("offline")
            bars = [b for b in data.bars if b.ticker == self.symbol and b.session >= kwargs["start"]]
            return pd.DataFrame([{"Open": b.open, "High": b.high, "Low": b.low, "Close": b.close,
                                  "Volume": b.volume, "Dividends": b.dividend, "Stock Splits": b.split} for b in bars],
                                index=pd.to_datetime([b.session for b in bars]))
    monkeypatch.setitem(sys.modules, "yfinance", SimpleNamespace(Ticker=Ticker, set_tz_cache_location=lambda _: None, __version__="1.7.0"))
    monkeypatch.setattr("richping.data.time.sleep", lambda _: None)
    return calls


def test_incremental_fetch_preserves_first_seen_values(monkeypatch):
    data = yahoo_fixture()
    calls = fake_yahoo(monkeypatch, data)
    fresh = yahoo_dataset(("ALFA",), data.start, data.end, previous=data)
    assert calls[0][1]["start"] == data.sessions[-10]
    assert fresh.by_ticker["ALFA"][data.sessions[-1]].known_at == data.by_ticker["ALFA"][data.sessions[-1]].known_at
    assert len(fresh.bars) == len(data.bars)


def test_overlap_revision_forces_full_new_vintage(monkeypatch):
    old = yahoo_fixture()
    bars = [replace(b, volume=b.volume + 1) if b.ticker == "ALFA" else b for b in old.bars]
    revised = Dataset(bars, old.metadata, old.members)
    calls = fake_yahoo(monkeypatch, revised)
    fresh = yahoo_dataset(("ALFA",), old.start, old.end, previous=old)
    assert any(kwargs["start"] == old.start for _, kwargs in calls)
    assert fresh.id != old.id
    assert old.by_ticker["ALFA"][old.start].volume + 1 == fresh.by_ticker["ALFA"][old.start].volume


def test_network_retry_is_bounded(monkeypatch):
    data = yahoo_fixture()
    calls = fake_yahoo(monkeypatch, data, error=True)
    with pytest.raises(OSError, match="offline"):
        yahoo_dataset(("ALFA",), data.start, data.end)
    assert len(calls) == 3


def test_stale_ticker_prevents_dataset_acceptance(monkeypatch):
    data = yahoo_fixture()
    incomplete = Dataset([b for b in data.bars if (b.ticker, b.session) != ("ALFA", data.end)], data.metadata, data.members)
    fake_yahoo(monkeypatch, incomplete)
    with pytest.raises(ValueError, match="Stale"):
        yahoo_dataset(("ALFA",), data.start, data.end)


def test_yahoo_dataset_known_at_not_before_fetch_completion(monkeypatch):
    """Finding 3: Yahoo 실제 수집 완료 이전 known_at 기록 방지 검증
    - ticker 요청 시작 -> clock 전진 -> 응답 완료
    - 새 bar/event known_at이 실제 해당 fetch 완료보다 이르지 않음
    - 전체 captured_at이 전체 수집 완료 시점보다 이르지 않음
    - 응답 전 as_of에서 shadow 데이터로 사용되지 않음 (data_not_yet_known)
    """
    from datetime import timedelta
    from richping.core import timestamp
    from richping.data import inspect_action_capture

    data = yahoo_fixture()
    t0 = timestamp("2024-06-01T21:30:00+00:00")
    current_time = [t0]

    def mock_utcnow():
        return current_time[0].isoformat()

    monkeypatch.setattr("richping.data.utcnow", mock_utcnow)
    monkeypatch.setattr("richping.data.time.sleep", lambda _: None)

    fetch_finish_times = {}
    meta_finish_times = {}

    class AdvancingTicker:
        def __init__(self, symbol):
            self.symbol = symbol

        def history(self, **kwargs):
            # Advance clock during history fetch
            current_time[0] += timedelta(minutes=5)
            fetch_finish_times[self.symbol] = current_time[0].isoformat()
            bars = [b for b in data.bars if b.ticker == self.symbol and b.session >= kwargs["start"]]
            df = pd.DataFrame([{"Open": b.open, "High": b.high, "Low": b.low, "Close": b.close,
                                "Volume": b.volume, "Dividends": b.dividend, "Stock Splits": b.split,
                                "Capital Gains": 0.0} for b in bars],
                              index=pd.to_datetime([b.session for b in bars]))
            return df

        @property
        def instrument_type(self):
            # Lazy/network-backed property fallback access advances clock
            current_time[0] += timedelta(minutes=2)
            meta_finish_times[self.symbol] = current_time[0].isoformat()
            return "EQUITY"

        @property
        def quote_currency(self):
            current_time[0] += timedelta(minutes=1)
            meta_finish_times[self.symbol] = current_time[0].isoformat()
            return "USD"

    monkeypatch.setitem(sys.modules, "yfinance", SimpleNamespace(Ticker=AdvancingTicker, set_tz_cache_location=lambda _: None, __version__="1.7.0"))

    fresh = yahoo_dataset(("ALFA",), data.start, data.end)

    # 1. Bar known_at is not earlier than each ticker's final metadata fallback completion
    latest_sess = data.sessions[-1]
    alfa_bar = fresh.by_ticker["ALFA"][latest_sess]
    spy_bar = fresh.by_ticker["SPY"][latest_sess]

    assert alfa_bar.known_at >= meta_finish_times["ALFA"]
    assert alfa_bar.known_at > fetch_finish_times["ALFA"]
    assert spy_bar.known_at >= meta_finish_times["SPY"]
    assert spy_bar.known_at > fetch_finish_times["SPY"]

    # 2. Overall action_capture captured_at is not earlier than total fetch and metadata completion
    cap = fresh.metadata["action_capture"]
    assert cap["captured_at"] >= meta_finish_times["ALFA"]
    assert cap["captured_at"] >= max(meta_finish_times.values())

    # 3. Before fetch/meta completion (at t0), shadow inspection blocks data as not yet known
    ac_before = inspect_action_capture(fresh, "ALFA", [latest_sess], as_of=t0.isoformat(), mode="shadow")
    assert ac_before.is_pending is True
    assert ac_before.reason == "data_not_yet_known"

    # After total completion, shadow inspection succeeds
    after_time = (current_time[0] + timedelta(minutes=1)).isoformat()
    ac_after = inspect_action_capture(fresh, "ALFA", [latest_sess], as_of=after_time, mode="shadow")
    assert ac_after.is_pending is False
