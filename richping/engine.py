"""Pure signal and outcome calculations, with explicit information cutoffs."""

from functools import cached_property
import math

import numpy as np

from .core import cutoff_at, next_sessions, timestamp


def unit(value, low, high):
    return float(np.clip((value - low) / (high - low), 0, 1))


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
    result = {"horizon": horizon, "end_session": end, "observed_at": timestamp(as_of).isoformat()}
    if cutoff_at(end) > timestamp(as_of):
        return {**result, "status": "PENDING", "reason": "horizon_not_mature"}
    symbol = snapshot["ticker"]
    bars = [dataset.by_ticker.get(symbol, {}).get(s) for s in days]
    if any(b is None for b in bars):
        return {**result, "status": "UNRESOLVED", "reason": "missing_or_delisted_session"}
    if mode == "shadow" and any(timestamp(b.known_at) > timestamp(as_of) for b in bars):
        return {**result, "status": "PENDING", "reason": "data_not_yet_known"}
    if any(b.split or b.dividend for b in bars):
        return {**result, "status": "UNRESOLVED", "reason": "corporate_action_requires_accounting"}
    # Revised/split-adjusted vintage must never silently change frozen price units.
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


class Engine:
    def __init__(self, dataset, config):
        self.data = dataset
        self.config = config
        self._signals = {}

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
                "holding_period": self.config.horizon, "cost": self.config.cost})
        result = {"regime": regime, "supported": risk_on and not high_vol,
                  "candidates": sorted(found, key=lambda s: (-s["score"], s["ticker"])), "excluded": excluded}
        self._signals[key] = result
        return result

    @cached_property
    def history(self):
        # These are research labels, never exposed to feature generation. Every
        # calibration query must enforce label_end < training boundary separately.
        rows = []
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
                                 "net_return": outcome["net_return"]})
        return rows

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
