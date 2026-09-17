"""Point-in-time, feature-only cash-gap normalization. Never outcome accounting."""

from dataclasses import dataclass, replace
import math

from .core import cutoff_at, timestamp
from .data import inspect_action_capture, is_verified_yfinance_adapter


FEATURE_VERSION = "cash_gap_backward_v1"
DIVIDEND_UNIT = "quote_currency_split_adjusted_per_share"
# Large distributions can have nonstandard ex-date/due-bill semantics (FINRA 11140).
# This is a rejection guard, not proof of ordinary-dividend tax classification.
MAX_DIVIDEND_FRACTION = 0.25


def normalize_dividends(bars, previous_close=None):
    """Pure OHLC view, latest anchored; caller must verify provenance first.

    Each event e applies (1 - D_e / C_{e-1}) only to bars strictly before e.
    The first bar's event needs a preceding close for validation, but scales no bar.
    Volume and action evidence are retained verbatim. No provider Adj Close used.
    """
    factors = []
    for i, bar in enumerate(bars):
        dividend = bar.dividend
        if not math.isfinite(dividend) or dividend < 0:
            raise ValueError("invalid_dividend_amount")
        factor = 1.0
        if dividend:
            prior = bars[i - 1].close if i else previous_close
            if prior is None or not math.isfinite(prior) or prior <= 0:
                raise ValueError("missing_dividend_reference")
            if dividend >= prior:
                raise ValueError("impossible_dividend_adjustment")
            if dividend / prior >= MAX_DIVIDEND_FRACTION:
                raise ValueError("large_cash_distribution")
            factor = 1.0 - dividend / prior
        factors.append(factor)
    result, cumulative = [], 1.0
    for bar, factor in reversed(list(zip(bars, factors))):
        if not math.isfinite(cumulative) or cumulative <= 0:
            raise ValueError("invalid_dividend_adjustment")
        result.append(bar if cumulative == 1 else replace(bar,
            open=bar.open * cumulative, high=bar.high * cumulative,
            low=bar.low * cumulative, close=bar.close * cumulative))
        cumulative *= factor
    return list(reversed(result))


@dataclass(frozen=True)
class FeatureWindow:
    raw: list
    bars: list
    observations: tuple
    blockers: tuple
    detail: str | None = None


def feature_window(dataset, symbol, session, cutoff=None, mode="research"):
    """Shared authoritative preflight for benchmarks, candidates and diagnostics."""
    if mode not in {"research", "shadow"}:
        raise ValueError("Invalid feature mode")
    cutoff = cutoff or cutoff_at(session).isoformat()
    raw = dataset.window(symbol, session, 61, cutoff, "research")
    if raw is None:
        return FeatureWindow([], [], (), ("missing_or_unknown_history",))
    if mode == "shadow" and any(timestamp(b.known_at) > timestamp(cutoff) for b in raw):
        return FeatureWindow([], [], (), ("data_not_yet_known",))
    days = {b.session for b in raw}
    capture = inspect_action_capture(dataset, symbol, list(days), cutoff, mode)
    if capture.is_pending:
        return FeatureWindow(raw, [], (), ("data_not_yet_known",))
    observations = ("dividend",) if any(b.dividend for b in raw) else ()
    blockers = []
    if any(b.split for b in raw):
        blockers.append("split")
    if capture.has_capital_gains:
        blockers.append("capital_gains")
    if not capture.is_confirmed:
        blockers.append("action_capture_unknown")
    cap = dataset.metadata.get("action_capture", {})
    events = [e for e in cap.get("events", []) if e["ticker"] == symbol and e["session"] in days]
    if any(e["field"] not in {"Capital Gains", "capital_gains", "Dividends"} for e in events):
        blockers.append("unsupported_corporate_action")
    cash_events = [e for e in events if e["field"] == "Dividends"]
    if any(sum(b.session == e["session"] and b.dividend == e["amount"] for b in raw) != 1
           for e in cash_events):
        blockers.append("unsupported_corporate_action")
    normalized, detail = raw, None
    if observations and not blockers:
        info = cap.get("tickers", {}).get(symbol, {})
        provider_ok = (
            dataset.metadata.get("source") == "yfinance"
            and dataset.metadata.get("price_basis") == "Yahoo split-adjusted OHLC; unadjusted for cash dividends"
            and is_verified_yfinance_adapter(cap.get("adapter_version"))
            and cap.get("history_options") == {"actions": True, "auto_adjust": False, "back_adjust": False, "repair": False}
            and info.get("instrument_type") in {"EQUITY", "ETF"}
            and info.get("quote_currency") == "USD"
        )
        dividends = cash_events
        expected = [b for b in raw if b.dividend]
        evidence_ok = len(dividends) == len(expected) and all(
            sum(e["session"] == b.session and e["amount"] == b.dividend
                and e.get("unit_basis") == DIVIDEND_UNIT and e.get("currency") == "USD"
                for e in dividends) == 1 for b in expected)
        if not provider_ok or not evidence_ok:
            detail = "unverified_feature_dividend_basis"
        else:
            prior = None
            if raw[0].dividend:
                index = dataset.positions[raw[0].session]
                prior = dataset.by_ticker[symbol].get(dataset.sessions[index - 1]) if index else None
                if prior and mode == "shadow" and timestamp(prior.known_at) > timestamp(cutoff):
                    blockers.append("data_not_yet_known")
            if not blockers:
                try:
                    normalized = normalize_dividends(raw, prior.close if prior else None)
                except ValueError as exc:
                    detail = str(exc)
        if detail:
            blockers.append("dividend_unsupported")
    # A dividend observed in an otherwise invalid window is not certified supported.
    if observations:
        observations += ("dividend_unsupported" if blockers else "dividend_normalized",)
    return FeatureWindow(raw, [] if blockers else normalized, observations, tuple(blockers), detail)
