"""Versioned input contract. No implicit forward filling or ticker substitution."""

from dataclasses import asdict, dataclass
from datetime import timedelta
import csv
import math
from pathlib import Path
import time

import numpy as np

from .core import (
    ACTION_CAPTURE_SCHEMA_VERSION,
    CAPITAL_GAINS_STATUSES,
    VERIFIED_DIVIDEND_BASIS,
    cutoff_at,
    digest,
    next_sessions,
    sessions,
    ticker,
    timestamp,
    utcnow,
)


VERIFIED_YFINANCE_VERSIONS = ("1.7.0",)
VERIFIED_YFINANCE_ADAPTERS = tuple(f"yfinance-{v}" for v in VERIFIED_YFINANCE_VERSIONS)


def is_verified_yfinance_adapter(adapter_version):
    return adapter_version in VERIFIED_YFINANCE_ADAPTERS


def validate_action_capture(capture):
    if not isinstance(capture, dict):
        raise ValueError("action_capture must be a dict")
    if capture.get("schema_version") != ACTION_CAPTURE_SCHEMA_VERSION:
        raise ValueError(f"Unsupported action_capture schema_version: {capture.get('schema_version')}")
    if not isinstance(capture.get("adapter_version"), str) or not capture["adapter_version"]:
        raise ValueError("Non-empty adapter_version required")
    if not isinstance(capture.get("captured_at"), str):
        raise ValueError("captured_at timestamp string required")
    timestamp(capture["captured_at"])
    tickers = capture.get("tickers")
    if not isinstance(tickers, dict):
        raise ValueError("tickers dict required in action_capture")
    for sym, tinfo in tickers.items():
        ticker(sym)
        st = tinfo.get("capital_gains_status")
        if st not in CAPITAL_GAINS_STATUSES:
            raise ValueError(f"Invalid capital_gains_status: {st!r} for {sym}")
        intervals = tinfo.get("query_intervals")
        if not isinstance(intervals, list):
            raise ValueError(f"query_intervals list required for {sym}")
        for i, iv in enumerate(intervals):
            if iv.get("capital_gains_status") not in CAPITAL_GAINS_STATUSES:
                raise ValueError(f"Invalid capital_gains_status in interval for {sym}: {iv}")
            if iv["start"] not in sessions(iv["start"], iv["start"]) or iv["end"] not in sessions(iv["end"], iv["end"]):
                raise ValueError(f"Invalid session dates in interval for {sym}: {iv}")
            if iv["start"] > iv["end"]:
                raise ValueError(f"Inverted interval for {sym}: {iv}")
            for other in intervals[i + 1:]:
                if max(iv["start"], other["start"]) <= min(iv["end"], other["end"]):
                    if iv.get("capital_gains_status") != other.get("capital_gains_status"):
                        raise ValueError(
                            f"Conflicting overlapping query intervals for {sym}: "
                            f"{iv} vs {other}"
                        )
    events = capture.get("events")
    if not isinstance(events, list):
        raise ValueError("events list required in action_capture")
    for e in events:
        ticker(e["ticker"])
        if e["session"] not in sessions(e["session"], e["session"]):
            raise ValueError(f"Non-trading session in event: {e}")
        amt = e.get("amount")
        if not isinstance(amt, (int, float)) or not math.isfinite(amt) or amt <= 0:
            raise ValueError(f"Invalid non-zero event amount: {amt!r} in {e}")
        if not isinstance(e.get("field"), str) or not e["field"]:
            raise ValueError(f"Invalid event field: {e}")
        timestamp(e["known_at"])


def normalize_query_intervals(intervals):
    if not intervals:
        return []
    sorted_ivs = sorted(intervals, key=lambda iv: (iv["start"], iv["end"], iv.get("capital_gains_status", "")))
    merged = []
    for iv in sorted_ivs:
        if not merged:
            merged.append(dict(iv))
            continue
        prev = merged[-1]
        if prev.get("capital_gains_status") == iv.get("capital_gains_status"):
            if iv["start"] <= prev["end"]:
                if iv["end"] > prev["end"]:
                    prev["end"] = iv["end"]
                continue
            try:
                nxt = next_sessions(prev["end"], 1)
                if nxt and nxt[0] == iv["start"]:
                    prev["end"] = iv["end"]
                    continue
            except Exception:
                pass
        merged.append(dict(iv))
    return merged


def overall_capital_gains_status(intervals):
    if not intervals:
        return "unknown"
    statuses = {iv.get("capital_gains_status") for iv in intervals}
    if len(statuses) == 1:
        st = statuses.pop()
        if st in CAPITAL_GAINS_STATUSES:
            return st
    return "unknown"

@dataclass(frozen=True)
class ActionCaptureInspection:
    is_confirmed: bool
    has_capital_gains: bool
    is_pending: bool
    reason: str | None
    events: list[dict]


def inspect_action_capture(dataset, symbol, sessions_list, as_of=None, mode="research") -> ActionCaptureInspection:
    """Inspects action_capture provenance covering symbol across sessions_list.

    Checks:
    1. Dataset action_capture exists.
    2. Shadow timing: captured_at and event known_at <= as_of (fails to PENDING otherwise).
    3. Symbol exists in action_capture tickers.
    4. Query intervals cover every session in sessions_list with non-unknown status.
    5. Checks for Capital Gains distribution events matching symbol in sessions_list.
    """
    if not sessions_list:
        return ActionCaptureInspection(
            is_confirmed=True, has_capital_gains=False, is_pending=False, reason=None, events=[]
        )

    capture = None
    if dataset is not None and hasattr(dataset, "metadata") and isinstance(dataset.metadata, dict):
        capture = dataset.metadata.get("action_capture")

    if not isinstance(capture, dict):
        return ActionCaptureInspection(
            is_confirmed=False, has_capital_gains=False, is_pending=False, reason="action_capture_unknown", events=[]
        )

    # Point-in-time checks for shadow mode
    if mode == "shadow" and as_of is not None:
        as_of_dt = timestamp(as_of)
        cap_at = capture.get("captured_at")
        if cap_at is None or not str(cap_at).strip():
            return ActionCaptureInspection(
                is_confirmed=False, has_capital_gains=False, is_pending=True, reason="data_not_yet_known", events=[]
            )
        try:
            if timestamp(cap_at) > as_of_dt:
                return ActionCaptureInspection(
                    is_confirmed=False, has_capital_gains=False, is_pending=True, reason="data_not_yet_known", events=[]
                )
        except (ValueError, TypeError):
            return ActionCaptureInspection(
                is_confirmed=False, has_capital_gains=False, is_pending=True, reason="data_not_yet_known", events=[]
            )
        for e in capture.get("events", []):
            if e.get("ticker") == symbol and e.get("session") in sessions_list:
                ev_known = e.get("known_at")
                if ev_known is None or not str(ev_known).strip():
                    return ActionCaptureInspection(
                        is_confirmed=False, has_capital_gains=False, is_pending=True, reason="data_not_yet_known", events=[]
                    )
                try:
                    if timestamp(ev_known) > as_of_dt:
                        return ActionCaptureInspection(
                            is_confirmed=False, has_capital_gains=False, is_pending=True, reason="data_not_yet_known", events=[]
                        )
                except (ValueError, TypeError):
                    return ActionCaptureInspection(
                        is_confirmed=False, has_capital_gains=False, is_pending=True, reason="data_not_yet_known", events=[]
                    )

    tickers = capture.get("tickers")
    if not isinstance(tickers, dict) or symbol not in tickers:
        return ActionCaptureInspection(
            is_confirmed=False, has_capital_gains=False, is_pending=False, reason="action_capture_unknown", events=[]
        )

    tinfo = tickers[symbol]
    intervals = tinfo.get("query_intervals", [])
    if not isinstance(intervals, list):
        return ActionCaptureInspection(
            is_confirmed=False, has_capital_gains=False, is_pending=False, reason="action_capture_unknown", events=[]
        )

    # Check that every session in sessions_list is covered by an interval with verified status
    confirmed_sessions = set()
    for iv in intervals:
        st = iv.get("capital_gains_status")
        if st in ("present", "not_applicable_by_provider"):
            st_start = iv.get("start", "")
            st_end = iv.get("end", "")
            for s in sessions_list:
                if st_start <= s <= st_end:
                    confirmed_sessions.add(s)

    all_covered = all(s in confirmed_sessions for s in sessions_list)

    # Check for Capital Gains distribution events
    cg_events = []
    for e in capture.get("events", []):
        if e.get("ticker") == symbol and e.get("session") in sessions_list:
            field = str(e.get("field", "")).strip().lower()
            if field in ("capital gains", "capital_gains"):
                try:
                    amt = float(e.get("amount", 0.0))
                except (TypeError, ValueError):
                    amt = 0.0
                if amt > 0.0:
                    cg_events.append(e)

    if cg_events:
        return ActionCaptureInspection(
            is_confirmed=all_covered,
            has_capital_gains=True,
            is_pending=False,
            reason="unsupported_capital_gains_distribution",
            events=cg_events,
        )

    if not all_covered:
        return ActionCaptureInspection(
            is_confirmed=False,
            has_capital_gains=False,
            is_pending=False,
            reason="action_capture_unknown",
            events=[],
        )

    return ActionCaptureInspection(
        is_confirmed=True,
        has_capital_gains=False,
        is_pending=False,
        reason=None,
        events=[],
    )


def create_action_capture(adapter_version, history_options, captured_at, tickers_info, events):
    sorted_tickers = {}
    for sym in sorted(tickers_info.keys()):
        info = tickers_info[sym]
        norm_intervals = normalize_query_intervals(info.get("query_intervals", []))
        st = info.get("capital_gains_status") or overall_capital_gains_status(norm_intervals)
        sorted_tickers[sym] = {
            "capital_gains_status": st,
            "instrument_type": info.get("instrument_type"),
            "query_intervals": norm_intervals,
            "quote_currency": info.get("quote_currency"),
        }
    sorted_events = sorted(
        events,
        key=lambda e: (e["ticker"], e["session"], e["field"], float(e["amount"]), e["known_at"])
    )
    capture = {
        "adapter_version": adapter_version,
        "captured_at": captured_at,
        "events": sorted_events,
        "history_options": dict(sorted(history_options.items())) if history_options else {},
        "schema_version": ACTION_CAPTURE_SCHEMA_VERSION,
        "tickers": sorted_tickers,
    }
    validate_action_capture(capture)
    return capture


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
        if "action_capture" in self.metadata:
            validate_action_capture(self.metadata["action_capture"])
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


def synthetic_dataset(n=900, symbols=("ALFA", "BETA", "GAMA", "DELT"), seed=7, dividend_basis=None, captured_at=None):
    """Artificial upward drift exercises mechanics, never investment evidence."""
    days = sessions("2022-01-03", "2026-09-01")[:n]
    rng = np.random.default_rng(seed)
    bars = []
    wanted_symbols = ("SPY", "QQQ") + tuple(symbols)
    for j, symbol in enumerate(wanted_symbols):
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
    captured_at = captured_at or cutoff_at(days[-1]).isoformat()
    tickers_info = {}
    for sym in (ticker(s) for s in wanted_symbols):
        tickers_info[sym] = {
            "capital_gains_status": "not_applicable_by_provider",
            "instrument_type": "SYNTHETIC",
            "query_intervals": [{"start": days[0], "end": days[-1], "capital_gains_status": "not_applicable_by_provider"}],
            "quote_currency": "USD",
        }
    capture = create_action_capture(
        adapter_version="synthetic",
        history_options={},
        captured_at=captured_at,
        tickers_info=tickers_info,
        events=[],
    )
    metadata = {
        "source": "deterministic-demo",
        "quality": "synthetic",
        "price_basis": "synthetic-no-actions",
        "seed": seed,
        "action_capture": capture,
    }
    if dividend_basis:
        metadata["dividend_basis"] = dividend_basis
    return Dataset(bars, metadata,
                   static_members(symbols, days[0], "2035-12-31", cutoff_at(days[0]).isoformat()))


def import_csv(path, members_path):
    with Path(path).open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        has_cg = "capital_gains" in fieldnames
        rows = list(reader)
    bars = []
    events = []
    by_sym_sessions = {}
    for row in rows:
        sym = ticker(row["ticker"])
        row["ticker"] = sym
        sess = row["session"]
        by_sym_sessions.setdefault(sym, []).append(sess)
        if has_cg:
            raw_cg = row.pop("capital_gains", None)
            if raw_cg is None or str(raw_cg).strip() == "":
                raise ValueError(f"Empty capital_gains value for {sym} on {sess}")
            try:
                cg = float(raw_cg)
            except (TypeError, ValueError):
                raise ValueError(f"Invalid non-numeric capital_gains value: {raw_cg!r}")
            if not math.isfinite(cg) or cg < 0:
                raise ValueError(f"Invalid capital_gains value: {raw_cg!r}")
            if cg > 0:
                events.append({
                    "ticker": sym,
                    "session": sess,
                    "field": "capital_gains",
                    "amount": cg,
                    "known_at": row["known_at"],
                })
        else:
            row.pop("capital_gains", None)
        for key in ("open", "high", "low", "close", "volume", "dividend", "split"):
            row[key] = float(row.get(key) or 0)
        bars.append(Bar(**row))

    captured_at = max((b.known_at for b in bars), default=utcnow())
    tickers_info = {}
    status = "present" if has_cg else "unknown"
    for sym, sess_list in by_sym_sessions.items():
        min_s = min(sess_list)
        max_s = max(sess_list)
        tickers_info[sym] = {
            "capital_gains_status": status,
            "instrument_type": None,
            "query_intervals": [{"start": min_s, "end": max_s, "capital_gains_status": status}],
            "quote_currency": None,
        }
    capture = create_action_capture(
        adapter_version="csv",
        history_options={},
        captured_at=captured_at,
        tickers_info=tickers_info,
        events=events,
    )
    with Path(members_path).open(encoding="utf-8-sig", newline="") as f:
        members = list(csv.DictReader(f))
    metadata = {
        "source": "csv",
        "quality": "research",
        "price_basis": "supplier-OHLC-actions-required",
        "action_capture": capture,
    }
    return Dataset(bars, metadata, members)


def yahoo_dataset(symbols, start, end, previous=None, prior_capture=None):
    """Incremental overlap; full refresh on revised overlap/action. Old vintages survive."""
    import yfinance as yf

    yf.set_tz_cache_location(str(Path("var/yfinance-cache").resolve()))
    symbols = tuple(ticker(s) for s in symbols)
    wanted = ("SPY", "QQQ") + symbols

    history_options = {
        "actions": True,
        "auto_adjust": False,
        "back_adjust": False,
        "repair": False,
    }
    raw_ver = getattr(yf, "__version__", None)
    if raw_ver and isinstance(raw_ver, str) and raw_ver.strip():
        adapter_ver = f"yfinance-{raw_ver.strip()}"
    else:
        adapter_ver = "yfinance-unknown"

    if previous:
        prev_meta = previous.metadata
        prev_cap = prev_meta.get("action_capture")
        if (
            prev_meta.get("source") != "yfinance"
            or {m["ticker"] for m in previous.members} != set(symbols)
            or previous.start > start
            or not isinstance(prev_cap, dict)
            or prev_cap.get("schema_version") != ACTION_CAPTURE_SCHEMA_VERSION
            or prev_cap.get("adapter_version") != adapter_ver
            or prev_cap.get("history_options") != history_options
        ):
            if isinstance(prev_cap, dict) and prior_capture is None:
                prior_capture = prev_cap
            previous = None

    fetch_start = start
    if previous:
        fetch_start = previous.sessions[max(0, len(previous.sessions) - 10)]
    bars = []
    new_events = []
    fetched_tickers_info = {}
    ticker_captured_times = []
    exclusive_end = (timestamp(end + "T00:00:00+00:00") + timedelta(days=1)).date().isoformat()
    for symbol in wanted:
        ticker_obj = yf.Ticker(symbol)
        frame = None
        for attempt in range(3):
            try:
                frame = ticker_obj.history(start=fetch_start, end=exclusive_end,
                    auto_adjust=False, back_adjust=False, actions=True, repair=False, raise_errors=True)
                if frame.empty:
                    raise ValueError(f"No data for {symbol}")
                break
            except Exception:
                if attempt == 2:
                    raise
                time.sleep(2 ** attempt)

        inst_type = None
        quote_curr = None
        has_meta = False
        try:
            if hasattr(ticker_obj, "get_history_metadata"):
                hm = ticker_obj.get_history_metadata() or {}
                has_meta = True
            elif hasattr(ticker_obj, "history_metadata"):
                hm = ticker_obj.history_metadata
                hm = hm() if callable(hm) else (hm or {})
                has_meta = True
            elif hasattr(ticker_obj, "fast_info"):
                hm = getattr(ticker_obj, "fast_info", {}) or {}
                has_meta = True
            else:
                hm = {}
            if isinstance(hm, dict):
                inst_type = hm.get("instrumentType")
                quote_curr = hm.get("currency")
        except Exception:
            pass

        if not inst_type and hasattr(ticker_obj, "instrument_type"):
            inst_type = ticker_obj.instrument_type
            has_meta = True
        if not quote_curr and hasattr(ticker_obj, "quote_currency"):
            quote_curr = ticker_obj.quote_currency
            has_meta = True

        symbol_captured_at = utcnow()
        ticker_captured_times.append(symbol_captured_at)

        if not has_meta and previous is not None:
            prev_tinfo = previous.metadata.get("action_capture", {}).get("tickers", {}).get(symbol, {})
            inst_type = prev_tinfo.get("instrument_type")
            quote_curr = prev_tinfo.get("quote_currency")

        has_cg_col = "Capital Gains" in frame.columns
        if has_cg_col:
            status = "present"
        elif is_verified_yfinance_adapter(adapter_ver) and inst_type == "EQUITY":
            status = "not_applicable_by_provider"
        else:
            status = "unknown"

        sym_sessions = []
        for idx, row in frame.iterrows():
            day = str(idx.date())
            if day > end or cutoff_at(day) > timestamp(symbol_captured_at):
                continue
            sym_sessions.append(day)

            div_val = float(row.get("Dividends", 0))
            split_val = float(row.get("Stock Splits", 0))

            if has_cg_col:
                raw_cg = row["Capital Gains"]
                if raw_cg is None:
                    raise ValueError(f"Invalid Capital Gains value for {symbol} on {day}: {raw_cg!r}")
                try:
                    cg_val = float(raw_cg)
                except (TypeError, ValueError):
                    raise ValueError(f"Invalid non-numeric Capital Gains value for {symbol} on {day}: {raw_cg!r}")
                if not math.isfinite(cg_val) or cg_val < 0:
                    raise ValueError(f"Invalid Capital Gains value for {symbol} on {day}: {raw_cg!r}")
                if cg_val > 0:
                    new_events.append({
                        "ticker": symbol,
                        "session": day,
                        "field": "Capital Gains",
                        "amount": cg_val,
                        "known_at": symbol_captured_at,
                    })

            bars.append(Bar(symbol, day, float(row["Open"]), float(row["High"]), float(row["Low"]),
                            float(row["Close"]), float(row["Volume"]), symbol_captured_at,
                            div_val, split_val))

        if sym_sessions:
            fetched_tickers_info[symbol] = {
                "capital_gains_status": status,
                "instrument_type": inst_type,
                "query_intervals": [{"start": min(sym_sessions), "end": max(sym_sessions), "capital_gains_status": status}],
                "quote_currency": quote_curr,
            }

    overall_captured_at = max(ticker_captured_times) if ticker_captured_times else utcnow()

    if previous:
        old = {(b.ticker, b.session): b for b in previous.bars}
        prev_cap = previous.metadata["action_capture"]
        prev_tickers = prev_cap.get("tickers", {})
        prev_events_map = {(e["ticker"], e["session"], e["field"]): e["amount"]
                           for e in prev_cap.get("events", [])}
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

        new_events_overlap = {(e["ticker"], e["session"], e["field"]): e["amount"]
                              for e in new_events if e["session"] <= previous.end}

        for symbol in wanted:
            tinfo = fetched_tickers_info.get(symbol)
            if not tinfo:
                continue
            prev_tinfo = prev_tickers.get(symbol, {})
            prev_status = prev_tinfo.get("capital_gains_status")
            new_status = tinfo.get("capital_gains_status")
            if prev_status != new_status:
                revised = True

            prev_inst = prev_tinfo.get("instrument_type")
            new_inst = tinfo.get("instrument_type")
            if prev_inst != new_inst:
                revised = True

            prev_curr = prev_tinfo.get("quote_currency")
            new_curr = tinfo.get("quote_currency")
            if prev_curr != new_curr:
                revised = True

            overlap_sessions = [b.session for b in bars if b.ticker == symbol and b.session <= previous.end]
            for s in overlap_sessions:
                k = (symbol, s, "Capital Gains")
                old_amt = prev_events_map.get(k)
                new_amt = new_events_overlap.get(k)
                if old_amt is not None and new_amt is None:
                    revised = True
                elif old_amt is None and new_amt is not None:
                    revised = True
                elif old_amt is not None and new_amt is not None and old_amt != new_amt:
                    revised = True

        if revised:
            return yahoo_dataset(symbols, start, end, previous=None, prior_capture=prev_cap)

        for b in bars:
            old.setdefault((b.ticker, b.session), b)
        bars = list(old.values())

        merged_events_map = {}
        for e in prev_cap.get("events", []):
            merged_events_map[(e["ticker"], e["session"], e["field"])] = dict(e)
        for e in new_events:
            k = (e["ticker"], e["session"], e["field"])
            if k not in merged_events_map:
                merged_events_map[k] = dict(e)
        merged_events = list(merged_events_map.values())

        merged_tickers = {}
        for symbol in wanted:
            prev_tinfo = prev_tickers.get(symbol, {})
            new_tinfo = fetched_tickers_info.get(symbol, {})
            prev_ivs = prev_tinfo.get("query_intervals", [])
            new_ivs = new_tinfo.get("query_intervals", [])
            norm_ivs = normalize_query_intervals(prev_ivs + new_ivs)
            merged_tickers[symbol] = {
                "capital_gains_status": overall_capital_gains_status(norm_ivs),
                "instrument_type": new_tinfo.get("instrument_type"),
                "query_intervals": norm_ivs,
                "quote_currency": new_tinfo.get("quote_currency"),
            }

        capture = create_action_capture(
            adapter_version=adapter_ver,
            history_options=history_options,
            captured_at=overall_captured_at,
            tickers_info=merged_tickers,
            events=merged_events,
        )
        members = previous.members
        meta = dict(previous.metadata)
        meta.pop("dividend_basis", None)
        meta["action_capture"] = capture
    else:
        members = static_members(symbols, start, "2035-12-31", overall_captured_at)
        if prior_capture:
            prior_events = {(e["ticker"], e["session"], e["field"]): e for e in prior_capture.get("events", [])}
            for e in new_events:
                k = (e["ticker"], e["session"], e["field"])
                if k in prior_events:
                    pe = prior_events[k]
                    if float(e["amount"]) == float(pe["amount"]):
                        e["known_at"] = pe["known_at"]
        capture = create_action_capture(
            adapter_version=adapter_ver,
            history_options=history_options,
            captured_at=overall_captured_at,
            tickers_info=fetched_tickers_info,
            events=new_events,
        )
        meta = {
            "source": "yfinance",
            "quality": "research",
            "price_basis": "Yahoo split-adjusted OHLC; unadjusted for cash dividends",
            "universe_bias": "current fixed list; not historical membership",
            "action_capture": capture,
        }
    dataset = Dataset(bars, meta, members)
    for symbol in wanted:
        if end not in dataset.by_ticker.get(symbol, {}):
            raise ValueError(f"Stale/missing latest session: {symbol} {end}")
    return dataset
