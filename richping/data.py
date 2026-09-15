"""Versioned input contract. No implicit forward filling or ticker substitution."""

from dataclasses import asdict, dataclass
from datetime import timedelta
import csv
import math
from pathlib import Path
import time

import numpy as np

from .core import cutoff_at, digest, sessions, ticker, timestamp, utcnow


@dataclass(frozen=True)
class Bar:
    ticker: str
    session: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    known_at: str
    dividend: float = 0.0
    split: float = 0.0

    def validate(self):
        if ticker(self.ticker) != self.ticker:
            raise ValueError("Ticker must be normalized")
        if self.session not in sessions(self.session, self.session):
            raise ValueError(f"Non-trading session: {self.session}")
        values = [self.open, self.high, self.low, self.close, self.volume, self.dividend, self.split]
        if not all(math.isfinite(x) for x in values):
            raise ValueError("Non-finite bar")
        if min(self.open, self.high, self.low, self.close) <= 0 or min(self.volume, self.dividend, self.split) < 0:
            raise ValueError("Invalid price/volume/action")
        if not self.low <= min(self.open, self.close) <= max(self.open, self.close) <= self.high:
            raise ValueError("Inconsistent OHLC")
        if timestamp(self.known_at) < cutoff_at(self.session):
            raise ValueError("Daily bar known_at precedes close + publication buffer")


class Dataset:
    def __init__(self, bars, metadata, members):
        self.metadata = dict(metadata)
        if self.metadata.get("quality") not in {"synthetic", "research"}:
            raise ValueError("MVP accepts only explicit synthetic/research quality")
        if not self.metadata.get("source") or not self.metadata.get("price_basis"):
            raise ValueError("Source and price_basis required")
        self.members = sorted([dict(m) for m in members], key=lambda m: m["ticker"])
        names = [m["ticker"] for m in self.members]
        if len(names) != len(set(names)) or not names:
            raise ValueError("Unique members required")
        for m in self.members:
            ticker(m["ticker"])
            timestamp(m["known_at"])
            if m["active_from"] > m["active_to"]:
                raise ValueError("Invalid membership interval")
        self.bars = sorted(bars, key=lambda b: (b.ticker, b.session))
        self.by_ticker = {}
        seen = set()
        for b in self.bars:
            b.validate()
            key = (b.ticker, b.session)
            if key in seen:
                raise ValueError(f"Duplicate bar: {key}")
            seen.add(key)
            self.by_ticker.setdefault(b.ticker, {})[b.session] = b
        if not self.bars:
            raise ValueError("Empty dataset")
        self.start = min(b.session for b in self.bars)
        self.end = max(b.session for b in self.bars)
        self.sessions = sessions(self.start, self.end)
        self.positions = {s: i for i, s in enumerate(self.sessions)}
        self.id = digest({"metadata": self.metadata, "members": self.members, "bars": [asdict(b) for b in self.bars]})

    def active(self, symbol, session, cutoff, mode):
        return any(m["ticker"] == symbol and m["active_from"] <= session <= m["active_to"]
                   and (mode == "research" or timestamp(m["known_at"]) <= timestamp(cutoff)) for m in self.members)

    def window(self, symbol, session, n, cutoff, mode="research"):
        index = self.positions.get(session, -1)
        if index < n - 1:
            return None
        bars = [self.by_ticker.get(symbol, {}).get(s) for s in self.sessions[index - n + 1:index + 1]]
        if any(b is None or (mode == "shadow" and timestamp(b.known_at) > timestamp(cutoff)) for b in bars):
            return None
        return bars


def static_members(symbols, start, end, known_at):
    return [{"ticker": ticker(s), "active_from": start, "active_to": end,
             "known_at": known_at, "sector": None, "industry": None} for s in symbols]


def synthetic_dataset(n=900, symbols=("ALFA", "BETA", "GAMA", "DELT"), seed=7):
    """Artificial upward drift exercises mechanics, never investment evidence."""
    days = sessions("2022-01-03", "2026-09-01")[:n]
    rng = np.random.default_rng(seed)
    bars = []
    for j, symbol in enumerate(("SPY", "QQQ") + tuple(symbols)):
        price = 100.0
        for i, day in enumerate(days):
            drift = 0.0015 if j < 2 else 0.0025 + (j - 2) * 0.00015
            # Correlated trend cycles and idiosyncratic returns; losses still occur.
            move = drift + 0.0005 * math.sin(i / 35) + rng.normal(0, 0.003 if j < 2 else 0.013)
            opening = price * (1 + rng.normal(0, 0.002))
            closing = opening * (1 + move)
            spread = abs(rng.normal(0.008, 0.003))
            bars.append(Bar(symbol, day, opening, max(opening, closing) * (1 + spread),
                            min(opening, closing) * (1 - spread), closing,
                            float(rng.integers(1_000_000, 4_000_000)), cutoff_at(day).isoformat()))
            price = closing
    return Dataset(bars, {"source": "deterministic-demo", "quality": "synthetic",
                         "price_basis": "synthetic-no-actions", "seed": seed},
                   static_members(symbols, days[0], "2035-12-31", cutoff_at(days[0]).isoformat()))


def import_csv(path, members_path):
    with Path(path).open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    bars = []
    for row in rows:
        for key in ("open", "high", "low", "close", "volume", "dividend", "split"):
            row[key] = float(row.get(key) or 0)
        row["ticker"] = ticker(row["ticker"])
        bars.append(Bar(**row))
    with Path(members_path).open(encoding="utf-8-sig", newline="") as f:
        members = list(csv.DictReader(f))
    return Dataset(bars, {"source": "csv", "quality": "research", "price_basis": "supplier-OHLC-actions-required"}, members)


def yahoo_dataset(symbols, start, end, previous=None):
    """Incremental overlap; full refresh on revised overlap/action. Old vintages survive."""
    import yfinance as yf

    yf.set_tz_cache_location(str(Path("var/yfinance-cache").resolve()))
    symbols = tuple(ticker(s) for s in symbols)
    wanted = ("SPY", "QQQ") + symbols
    if previous and (previous.metadata["source"] != "yfinance" or
                     {m["ticker"] for m in previous.members} != set(symbols)):
        previous = None
    fetch_start = start
    if previous:
        if previous.start > start:
            previous = None
        else:
            fetch_start = previous.sessions[max(0, len(previous.sessions) - 10)]
    now = utcnow()
    bars = []
    exclusive_end = (timestamp(end + "T00:00:00+00:00") + timedelta(days=1)).date().isoformat()
    for symbol in wanted:
        for attempt in range(3):
            try:
                frame = yf.Ticker(symbol).history(start=fetch_start, end=exclusive_end,
                    auto_adjust=False, back_adjust=False, actions=True, repair=False, raise_errors=True)
                if frame.empty:
                    raise ValueError(f"No data for {symbol}")
                break
            except Exception:
                if attempt == 2:
                    raise
                time.sleep(2 ** attempt)
        for idx, row in frame.iterrows():
            day = str(idx.date())
            if day > end or cutoff_at(day) > timestamp(now):
                continue
            bars.append(Bar(symbol, day, float(row["Open"]), float(row["High"]), float(row["Low"]),
                            float(row["Close"]), float(row["Volume"]), now,
                            float(row.get("Dividends", 0)), float(row.get("Stock Splits", 0))))
    if previous:
        old = {(b.ticker, b.session): b for b in previous.bars}
        revised = False
        for b in bars:
            prior = old.get((b.ticker, b.session))
            if (b.split or b.dividend) and b.session > previous.end:
                revised = True
            if prior:
                a, z = asdict(prior), asdict(b)
                a.pop("known_at")
                z.pop("known_at")
                if a != z:
                    revised = True
        if revised:
            return yahoo_dataset(symbols, start, end, previous=None)
        for b in bars:
            old.setdefault((b.ticker, b.session), b)
        bars = list(old.values())
        members = previous.members
    else:
        members = static_members(symbols, start, "2035-12-31", now)
    dataset = Dataset(bars, {"source": "yfinance", "quality": "research",
        "price_basis": "Yahoo split-adjusted OHLC; dividends excluded; action windows unresolved",
        "universe_bias": "current fixed list; not historical membership"}, members)
    for symbol in wanted:
        if end not in dataset.by_ticker.get(symbol, {}):
            raise ValueError(f"Stale/missing latest session: {symbol} {end}")
    return dataset
