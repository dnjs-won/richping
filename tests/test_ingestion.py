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
