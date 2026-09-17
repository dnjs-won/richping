"""Pure signal and outcome calculations, with explicit information cutoffs."""

from functools import cached_property
import math

import numpy as np

from .core import (
    DEFAULT_OUTCOME_VERSION,
    LEGACY_OUTCOME_VERSION,
    OUTCOME_VERSION_V1,
    OUTCOME_VERSION_V2,
    OUTCOME_VERSION_V3,
    SUPPORTED_OUTCOME_VERSIONS,
    VERIFIED_DIVIDEND_BASIS,
    cutoff_at,
    next_sessions,
    timestamp,
)
from .data import inspect_action_capture


def unit(value, low, high):
    return float(np.clip((value - low) / (high - low), 0.0, 1.0))


def features(bars, benchmark):
    closes = np.array([b.close for b in bars])
    volume = np.array([b.volume for b in bars])
    high = np.array([b.high for b in bars])
    low = np.array([b.low for b in bars])
    returns = closes[1:] / closes[:-1] - 1
    tr = np.maximum(high[1:] - low[1:], np.maximum(abs(high[1:] - closes[:-1]), abs(low[1:] - closes[:-1])))
    r20 = closes[-1] / closes[-21] - 1
    return {
        "return_1d": float(returns[-1]), "return_5d": float(closes[-1] / closes[-6] - 1),
        "return_20d": float(r20), "relative_strength": float(r20 - (benchmark[-1].close / benchmark[-21].close - 1)),
        "ma20": float(closes[-20:].mean()), "ma60": float(closes[-60:].mean()),
        "trend": float(closes[-1] / closes[-60:].mean() - 1),
        "breakout_distance": float(closes[-1] / high[-21:-1].max() - 1),
        "relative_volume": float(volume[-1] / volume[-21:-1].mean()) if volume[-21:-1].mean() > 0 else 0.0,
        "atr": float(tr[-14:].mean()), "realized_vol": float(returns[-20:].std(ddof=1) * math.sqrt(252)),
        "dollar_volume": float(np.mean(closes[-20:] * volume[-20:])),
        "price": float(closes[-1]), "volume": float(volume[-1]),
    }


def rank_score(f):
    parts = {
        "momentum": 25 * unit(f["return_20d"], -0.05, 0.15),
        "relative_strength": 25 * unit(f["relative_strength"], -0.05, 0.10),
        "trend": 20 * unit(f["trend"], -0.05, 0.15),
        "relative_volume": 15 * unit(f["relative_volume"], 0.5, 2.0),
        "breakout": 15 * unit(f["breakout_distance"], -0.10, 0.02),
    }
    return sum(parts.values()), parts


def observe(snapshot, dataset, horizon, as_of, mode="research"):
    days = next_sessions(snapshot["session"], horizon)
    end = days[-1]
    if "outcome_version" not in snapshot:
        version = OUTCOME_VERSION_V1
    else:
        version = snapshot["outcome_version"]
    result = {"horizon": horizon, "end_session": end, "observed_at": timestamp(as_of).isoformat(),
              "outcome_version": version}
    if version not in SUPPORTED_OUTCOME_VERSIONS:
        return {**result, "status": "UNRESOLVED", "reason": "unsupported_outcome_version"}
    if cutoff_at(end) > timestamp(as_of):
        return {**result, "status": "PENDING", "reason": "horizon_not_mature"}
    symbol = snapshot["ticker"]
    bars = [dataset.by_ticker.get(symbol, {}).get(s) for s in days]
    if any(b is None for b in bars):
        return {**result, "status": "UNRESOLVED", "reason": "missing_or_delisted_session"}
    if mode == "shadow" and any(timestamp(b.known_at) > timestamp(as_of) for b in bars):
        return {**result, "status": "PENDING", "reason": "data_not_yet_known"}

    # Version-specific handling of corporate actions and dividend accounting
    if version == OUTCOME_VERSION_V1:
        # Legacy v1: any corporate action (split or dividend) renders window UNRESOLVED
        if any(b.split or b.dividend for b in bars):
            return {**result, "status": "UNRESOLVED", "reason": "corporate_action_requires_accounting"}
        origin = dataset.by_ticker.get(symbol, {}).get(snapshot["session"])
        if origin is None or not math.isclose(origin.close, snapshot["entry_reference"], rel_tol=1e-8):
            return {**result, "status": "UNRESOLVED", "reason": "price_vintage_changed"}
        entry = bars[0].open
        raw = bars[-1].close / entry - 1
        stop, target = snapshot["stop_reference"], snapshot["target_reference"]
        target_day = next((b.session for b in bars if b.high >= target), None)
        stop_day = next((b.session for b in bars if b.low <= stop), None)
        first = "NONE"
        if target_day and stop_day and target_day == stop_day:
            first = "AMBIGUOUS"
        elif target_day and (not stop_day or target_day < stop_day):
            first = "TARGET"
        elif stop_day:
            first = "STOP"
        return {**result, "status": "COMPLETE", "entry_session": days[0], "entry_price": entry,
                "raw_return": raw, "net_return": raw - snapshot["cost"],
                "mfe": max(0.0, max(b.high for b in bars) / entry - 1),
                "mae": min(0.0, min(b.low for b in bars) / entry - 1),
                "target_hit": bool(target_day), "stop_hit": bool(stop_day), "first_hit": first}

    elif version == OUTCOME_VERSION_V2:
        # v2: Ordinary cash dividends supported if dataset explicitly verifies dividend contract
        # (Preserved historical replay code; not an approved rule for current evaluation)
        if any(b.split for b in bars):
            return {**result, "status": "UNRESOLVED", "reason": "stock_split_requires_accounting"}

        has_dividends = any(b.dividend > 0 for b in bars)
        if has_dividends:
            div_basis = dataset.metadata.get("dividend_basis")
            if div_basis != VERIFIED_DIVIDEND_BASIS:
                return {**result, "status": "UNRESOLVED", "reason": "unverified_dividend_basis"}
            # Preserved legacy rule for historical replay: single dividend >= 20% of close price indicates special/irregular distribution
            if any(b.dividend >= 0.20 * b.close for b in bars if b.dividend > 0):
                return {**result, "status": "UNRESOLVED", "reason": "special_or_irregular_dividend_requires_accounting"}

        # Revised/split-adjusted vintage must never silently change frozen price units.
        origin = dataset.by_ticker.get(symbol, {}).get(snapshot["session"])
        if origin is None or not math.isclose(origin.close, snapshot["entry_reference"], rel_tol=1e-8):
            return {**result, "status": "UNRESOLVED", "reason": "price_vintage_changed"}

        entry = bars[0].open
        exit_price = bars[-1].close
        price_return = float(exit_price / entry - 1)

        # Entitled dividends: ex-dividend occurring on sessions strictly after entry day up to horizon end.
        # Entry at open on bars[0] means the position is acquired after the ex-dividend cutoff of bars[0].
        eligible_bars = bars[1:]
        dividend_cash = float(sum(b.dividend for b in eligible_bars))
        dividend_return = float(dividend_cash / entry)
        raw_return = float(price_return + dividend_return)
        cost = float(snapshot["cost"])
        net_return = float(raw_return - cost)
        price_net_return = float(price_return - cost)

        stop, target = snapshot["stop_reference"], snapshot["target_reference"]
        target_day = next((b.session for b in bars if b.high >= target), None)
        stop_day = next((b.session for b in bars if b.low <= stop), None)
        first = "NONE"
        if target_day and stop_day and target_day == stop_day:
            first = "AMBIGUOUS"
        elif target_day and (not stop_day or target_day < stop_day):
            first = "TARGET"
        elif stop_day:
            first = "STOP"

        return {**result, "status": "COMPLETE", "entry_session": days[0], "entry_price": entry,
                "exit_price": exit_price, "price_return": price_return, "price_net_return": price_net_return,
                "dividend_cash": dividend_cash, "dividend_return": dividend_return,
                "raw_return": raw_return, "net_return": net_return, "cost": cost,
                "entry_day_dividend_excluded": float(bars[0].dividend),
                "mfe": max(0.0, max(b.high for b in bars) / entry - 1),
                "mae": min(0.0, min(b.low for b in bars) / entry - 1),
                "target_hit": bool(target_day), "stop_hit": bool(stop_day), "first_hit": first,
                "return_basis": "ordinary_cash_dividend_entitlement_gross_unreinvested",
                "notes": "Pre-tax dividend entitlement research return; excludes entry-day ex-dividend; no reinvestment; price-only barriers"}

    elif version == OUTCOME_VERSION_V3:
        # v3_cash_action_guard: Price-only return; all corporate actions fail closed.
        # Reason priority:
        # 1. stock_split_requires_accounting
        # 2. unsupported_capital_gains_distribution
        # 3. unverified_cash_dividend_event
        # 4. action_capture_unknown

        # Priority 1: Stock split
        if any(b.split for b in bars):
            return {**result, "status": "UNRESOLVED", "reason": "stock_split_requires_accounting"}

        ac = inspect_action_capture(dataset, symbol, days, as_of=as_of, mode=mode)
        if mode == "shadow" and ac.is_pending:
            return {**result, "status": "PENDING", "reason": "data_not_yet_known"}

        # Priority 2: Capital Gains distribution
        if ac.has_capital_gains:
            return {**result, "status": "UNRESOLVED", "reason": "unsupported_capital_gains_distribution"}

        # Priority 3: Cash dividend (entry-day and all holding sessions included; no threshold or verified bypass)
        if any(b.dividend > 0 for b in bars):
            return {**result, "status": "UNRESOLVED", "reason": "unverified_cash_dividend_event"}

        # Priority 4: Action capture unverified or incomplete
        if not ac.is_confirmed:
            return {**result, "status": "UNRESOLVED", "reason": "action_capture_unknown"}

        # Frozen price vintage integrity check
        origin = dataset.by_ticker.get(symbol, {}).get(snapshot["session"])
        if origin is None or not math.isclose(origin.close, snapshot["entry_reference"], rel_tol=1e-8):
            return {**result, "status": "UNRESOLVED", "reason": "price_vintage_changed"}

        entry = bars[0].open
        exit_price = bars[-1].close
        price_return = float(exit_price / entry - 1)
        cost = float(snapshot["cost"])
        raw_return = float(price_return)
        net_return = float(raw_return - cost)
        price_net_return = net_return

        stop, target = snapshot["stop_reference"], snapshot["target_reference"]
        target_day = next((b.session for b in bars if b.high >= target), None)
        stop_day = next((b.session for b in bars if b.low <= stop), None)
        first = "NONE"
        if target_day and stop_day and target_day == stop_day:
            first = "AMBIGUOUS"
        elif target_day and (not stop_day or target_day < stop_day):
            first = "TARGET"
        elif stop_day:
            first = "STOP"

        return {**result, "status": "COMPLETE", "entry_session": days[0], "entry_price": entry,
                "exit_price": exit_price, "price_return": price_return, "price_net_return": price_net_return,
                "raw_return": raw_return, "net_return": net_return, "cost": cost,
                "mfe": max(0.0, max(b.high for b in bars) / entry - 1),
                "mae": min(0.0, min(b.low for b in bars) / entry - 1),
                "target_hit": bool(target_day), "stop_hit": bool(stop_day), "first_hit": first,
                "return_basis": "price_only_unadjusted_cash_dividends",
                "notes": "Price-only return; corporate actions excluded; roundtrip cost deducted once"}

    return {**result, "status": "UNRESOLVED", "reason": "unsupported_outcome_version"}


class Engine:
    def __init__(self, dataset, config, outcome_version=None):
        self.data = dataset
        self.config = config
        self.outcome_version = outcome_version or DEFAULT_OUTCOME_VERSION
        self._signals = {}
        self._excluded_history = []

    def signals(self, session, cutoff=None, mode="research"):
        cutoff = cutoff or cutoff_at(session).isoformat()
        if cutoff_at(session) > timestamp(cutoff):
            raise ValueError("Session is not complete at cutoff")
        key = (session, cutoff if mode == "shadow" else None, mode)
        if key in self._signals:
            return self._signals[key]
        spy = self.data.window("SPY", session, 61, cutoff, mode)
        qqq = self.data.window("QQQ", session, 61, cutoff, mode)
        if spy is None or qqq is None:
            raise ValueError(f"Missing/stale benchmark history at {session}")

        # Benchmark input integrity checks: split, dividend, capital gains, unverified capture
        for b_name, b_bars in (("SPY", spy), ("QQQ", qqq)):
            if any(b.split or b.dividend for b in b_bars):
                raise ValueError(f"Corporate action in {b_name} benchmark history at {session}")
            b_sessions = [b.session for b in b_bars]
            b_ac = inspect_action_capture(self.data, b_name, b_sessions, as_of=cutoff, mode=mode)
            if mode == "shadow" and b_ac.is_pending:
                raise ValueError(f"Benchmark {b_name} history not yet known as of {cutoff}")
            if b_ac.has_capital_gains:
                raise ValueError(f"Capital gains distribution in {b_name} benchmark history at {session}")
            if not b_ac.is_confirmed:
                raise ValueError(f"Unverified action capture in {b_name} benchmark history at {session}")

        sf, qf = features(spy, spy), features(qqq, spy)
        risk_on = sf["price"] > sf["ma60"] and qf["price"] > qf["ma60"]
        high_vol = sf["realized_vol"] >= 0.25
        regime = ("RISK_ON" if risk_on else "RISK_OFF") + ("_HIGH_VOL" if high_vol else "_LOW_VOL")
        found, excluded = [], {}
        for symbol in self.config.tickers:
            if not self.data.active(symbol, session, cutoff, mode):
                excluded[symbol] = "not_in_asof_universe"
                continue
            bars = self.data.window(symbol, session, 61, cutoff, mode)
            if bars is None:
                excluded[symbol] = "missing_or_unknown_history"
                continue
            if any(b.split or b.dividend for b in bars):
                excluded[symbol] = "corporate_action_in_feature_window"
                continue
            bar_sessions = [b.session for b in bars]
            sym_ac = inspect_action_capture(self.data, symbol, bar_sessions, as_of=cutoff, mode=mode)
            if mode == "shadow" and sym_ac.is_pending:
                excluded[symbol] = "data_not_yet_known"
                continue
            if sym_ac.has_capital_gains:
                excluded[symbol] = "corporate_action_in_feature_window"
                continue
            if not sym_ac.is_confirmed:
                excluded[symbol] = "action_capture_unknown"
                continue
            f = features(bars, spy)
            if f["price"] < self.config.min_price or f["dollar_volume"] < self.config.min_dollar_volume:
                excluded[symbol] = "price_or_liquidity"
                continue
            score, parts = rank_score(f)
            if score < self.config.min_score or f["price"] <= f["ma20"]:
                excluded[symbol] = "weak_signal"
                continue
            if f["atr"] <= 0 or 2 * f["atr"] >= f["price"]:
                excluded[symbol] = "invalid_risk_reference"
                continue
            found.append({"ticker": symbol, "session": session, "cutoff": cutoff, "regime": regime,
                "features": f, "score": score, "contributors": parts, "entry_reference": f["price"],
                "stop_reference": f["price"] - 2 * f["atr"], "target_reference": f["price"] + 4 * f["atr"],
                "holding_period": self.config.horizon, "cost": self.config.cost,
                "outcome_version": self.outcome_version})
        result = {"regime": regime, "supported": risk_on and not high_vol,
                  "candidates": sorted(found, key=lambda s: (-s["score"], s["ticker"])), "excluded": excluded}
        self._signals[key] = result
        return result

    @cached_property
    def history(self):
        # These are research labels, never exposed to feature generation. Every
        # calibration query must enforce label_end < training boundary separately.
        rows = []
        self._excluded_history = []
        for session in self.data.sessions[60:]:
            try:
                signals = self.signals(session)
            except ValueError:
                continue
            if not signals["supported"]:
                continue
            for signal in signals["candidates"]:
                outcome = observe(signal, self.data, self.config.horizon, cutoff_at(self.data.end).isoformat())
                if outcome["status"] == "COMPLETE":
                    rows.append({"session": session, "ticker": signal["ticker"], "regime": signal["regime"],
                                 "score": signal["score"], "end_session": outcome["end_session"],
                                 "net_return": outcome["net_return"],
                                 "outcome_version": outcome.get("outcome_version", self.outcome_version)})
                else:
                    self._excluded_history.append({
                        "session": session, "ticker": signal["ticker"], "regime": signal["regime"],
                        "score": signal["score"], "end_session": outcome.get("end_session"),
                        "status": outcome["status"], "reason": outcome.get("reason"),
                        "outcome_version": outcome.get("outcome_version", self.outcome_version),
                    })
        return rows

    @property
    def excluded_history(self):
        _ = self.history
        return getattr(self, "_excluded_history", [])

    def calibration(self, signal, boundary=None):
        from .evaluation import estimate
        boundary = boundary or signal["session"]
        index = self.data.positions[boundary]
        # Maximum supported label horizon (20) plus one-session embargo.
        end_index = index - 22
        if end_index < 0:
            return estimate([], self.config)
        end = self.data.sessions[end_index]
        start = self.data.sessions[max(0, end_index - self.config.train_sessions + 1)]
        rows = [r for r in self.history if start <= r["session"] <= end
                and r["end_session"] < boundary and r["regime"] == signal["regime"]
                and abs(r["score"] - signal["score"]) <= 15]
        return {**estimate(rows, self.config), "training_start": start, "training_end": end,
                "label_cutoff": boundary}
