"""Frozen Daily price permission, detached research only.

Prepared inputs attest to an already transformed/eligible series. This module
does not obtain actions, transform prices, select freshness or join timeframes.
Synthetic fixtures verify the classifier, not those missing data capabilities.
"""

from dataclasses import dataclass
from datetime import datetime
import math

from ...core import digest, timestamp, ticker
from ..contracts import MarketBar, ReplayContext, payload
from ..features.moving import EMASpec, ema
from ..sessions import RTH, bar_profile


def minimum_history(span=50, residual=0.001):
    """Observations needed for the actual first-seed residual <= residual.

    E_1=C_1; N observations perform N-1 recursive updates, so the seed's
    coefficient is (1-alpha)**(N-1). One seed observation precedes the updates.
    """
    return 1 + math.ceil(math.log(residual) / math.log(1 - 2 / (span + 1)))


@dataclass(frozen=True, slots=True)
class DailyTrendSpec:
    candidate: str = "DLP-B"

    def __post_init__(self):
        if self.candidate not in {"DLP-A", "DLP-B"}:
            raise ValueError("Only frozen T0/T1 are executable; DLP-C is deferred")

    @property
    def version(self):
        return ("DAILY_TREND_EMA_LEVEL_SLOPE_V1" if self.candidate == "DLP-B"
                else "DAILY_TREND_EMA_LEVEL_ABLATION_V1")

    @property
    def ema_spec(self):
        return EMASpec(span=50, min_history=minimum_history())

    @property
    def semantics(self):
        return {
            "session": "RTH_DAILY", "session_profile": RTH,
            "price_basis": "PIT_SPLIT_ADJUSTED_OHLC",
            "freshness": "LATEST_EXPECTED_COMPLETED_SESSION_REQUIRED",
            "ema_span": 50, "ema_seed": "FIRST_OBSERVATION_RECURSIVE",
            "minimum_history": self.ema_spec.min_history, "seed_residual_limit": 0.001,
            "readiness_count": "COMPLETED_OBSERVATIONS_INCLUDING_FIRST_SEED",
            "readiness_definition": "actual_first_seed_residual_lte_0_001",
            "operand_readiness": "current_and_t_minus_5_prefix_independently_READY",
            "history_origin": "available_completed_history_prefix_v1",
            "level": "close_gt_ema", "level_equality": False,
            "slope_lag_observations": 5, "slope_equality": False,
            "require_positive_slope": self.candidate == "DLP-B",
            "states": "BULLISH|NOT_BULLISH|UNAVAILABLE",
            "unavailable": "input_history_action_freshness_or_calculation_unavailable",
            "lifecycle": "same_fresh_Daily_same_state_new_expected_undelivered_UNAVAILABLE",
        }

    @property
    def hash(self):
        return digest({"version": self.version, "semantics": self.semantics,
                       "ema_feature_specification_hash": self.ema_spec.hash})

    @property
    def contract(self):
        """C0's typed, versioned immutable contract representation."""
        def typed(value):
            return {"kind": {str: "text", int: "integer", float: "number",
                             bool: "boolean"}[type(value)],
                    "value": value, "choices": [], "decision_id": None}
        return {"name": self.version.lower().removesuffix("_v1"), "version": "v1",
                "parameters": {k: typed(v) for k, v in {
                    **self.semantics, "rule_version": self.version,
                    "rule_hash": self.hash,
                    "ema_feature_specification_hash": self.ema_spec.hash,
                }.items()}}


CANONICAL = DailyTrendSpec()
ABLATION = DailyTrendSpec("DLP-A")


@dataclass(frozen=True, slots=True)
class PreparedDailyPrefix:
    """Caller-supplied eligibility facts for this exact as_of; no selector.

    transform_known_at is the maximum of required action/transform evidence
    (including evidence of no relevant action), not the price timestamp alone.
    transform_effective_at contains applied action effective times. The caller
    owns factor validity, coverage, history origin and PIT transformation.
    """
    symbol: str
    bars: tuple[MarketBar, ...]
    eligibility_as_of: datetime
    expected_session: str | None
    source_vintage: str
    transform_known_at: datetime | None
    transform_effective_at: tuple[datetime, ...] = ()
    input_status: str = "READY"
    input_reason: str | None = None
    session_profile: str = RTH
    price_basis: str = "PIT_SPLIT_ADJUSTED_OHLC"

    def __post_init__(self):
        if ticker(self.symbol) != self.symbol or not self.source_vintage:
            raise ValueError("Normalized symbol and explicit vintage required")
        object.__setattr__(self, "bars", tuple(self.bars))
        object.__setattr__(self, "eligibility_as_of", timestamp(self.eligibility_as_of))
        if self.transform_known_at is not None:
            object.__setattr__(self, "transform_known_at", timestamp(self.transform_known_at))
        object.__setattr__(self, "transform_effective_at",
                           tuple(timestamp(t) for t in self.transform_effective_at))
        if any(type(b) is not MarketBar for b in self.bars):
            raise ValueError("Immutable Daily bars required")
        if self.input_status not in {"READY", "UNAVAILABLE"} or (
                (self.input_status == "READY") != (self.input_reason is None)):
            raise ValueError("Input status/reason mismatch")


@dataclass(frozen=True, slots=True)
class DailyTrendState:
    symbol: str
    as_of: datetime
    session_date: str | None
    state: str
    status: str
    reason: str | None
    session_profile: str
    price_basis: str
    input_end_at: datetime | None
    known_at: datetime | None
    input_hash: str
    source_vintage: str
    ema_feature_specification_hash: str
    rule_version: str
    rule_hash: str
    input_count: int
    lag_input_count: int
    current_ema: float | None
    lag_ema: float | None


def classify_daily_trend(prefix: PreparedDailyPrefix, as_of, spec=CANONICAL,
                         *, matched_comparison=True):
    """Pure classification of a prepared causal prefix; never writes or orders.

    By default A and B check the same operand readiness/coverage. A omits only
    the slope predicate, so availability cannot confound T1/T0. Standalone A
    (matched_comparison=False) needs only the current EMA; B always needs both.
    Future inputs are rejected, never filtered into a silently shortened prefix.
    """
    if type(prefix) is not PreparedDailyPrefix or type(spec) is not DailyTrendSpec:
        raise ValueError("Prepared prefix and frozen trend specification required")
    if type(matched_comparison) is not bool:
        raise ValueError("Explicit boolean comparison mode required")
    instant = timestamp(as_of)
    bars = prefix.bars
    n, lag_n = len(bars), max(0, len(bars) - 5)
    # Invalid/future evidence contributes no backdated input hash or provenance.
    causal = (all(b.end_at <= instant and b.known_at <= instant for b in bars)
              and prefix.transform_known_at is not None
              and prefix.transform_known_at <= instant
              and all(t <= instant for t in prefix.transform_effective_at))

    def output(reason=None, current=None, lag=None):
        ready = reason is None
        bullish = ready and bars[-1].close > current and (
            not spec.semantics["require_positive_slope"] or current > lag)
        return DailyTrendState(
            prefix.symbol, instant, bars[-1].session if causal and bars else None,
            "BULLISH" if bullish else "NOT_BULLISH" if ready else "UNAVAILABLE",
            "READY" if ready else "UNAVAILABLE", reason,
            prefix.session_profile, prefix.price_basis,
            bars[-1].end_at if causal and bars else None,
            max([prefix.transform_known_at, *(b.known_at for b in bars)]) if causal else None,
            digest({"bars": payload(bars), "vintage": prefix.source_vintage,
                    "transform_known_at": prefix.transform_known_at.isoformat(),
                    "transform_effective_at": [t.isoformat() for t in prefix.transform_effective_at],
                    "session_profile": prefix.session_profile,
                    "price_basis": prefix.price_basis}) if causal else digest({"rejected_input": reason}),
            prefix.source_vintage, spec.ema_spec.hash, spec.version, spec.hash,
            n if causal else 0, lag_n if causal else 0, current, lag)

    if prefix.eligibility_as_of != instant:
        return output("eligibility_as_of_mismatch")
    if not causal:
        return output("action_evidence_unavailable" if prefix.transform_known_at is None
                      else "future_Daily_or_action_evidence")
    if prefix.input_status != "READY":
        return output(prefix.input_reason)
    if prefix.session_profile != RTH or prefix.price_basis != spec.semantics["price_basis"]:
        return output("input_contract_mismatch")
    if not bars:
        return output("no_completed_input")
    if prefix.expected_session is None:
        return output("freshness_evidence_unavailable")
    try:
        if any(b.symbol != prefix.symbol or b.timeframe != "Daily" or bar_profile(b) != RTH
               for b in bars) or any(a.end_at >= b.end_at for a, b in zip(bars, bars[1:])):
            return output("invalid_Daily_prefix")
        if bars[-1].session != prefix.expected_session:
            return output("latest_expected_completed_session_missing")
        current = ema(ReplayContext(instant, bars), prefix.symbol, "Daily", spec.ema_spec)
        # Same origin and same current-as_of price vintage; t-5 is a prefix,
        # not a historical snapshot from before a causal split rebase.
        lag = (ema(ReplayContext(instant, bars[:lag_n]), prefix.symbol, "Daily", spec.ema_spec)
               if matched_comparison or spec.candidate == "DLP-B" else None)
    except ValueError:
        return output("invalid_or_unsupported_Daily_input")
    for operand, label in ((current, "current_ema"), (lag, "lag_ema")):
        if operand is not None and operand.status != "READY":
            return output(label + ":" + operand.reason)
    return output(current=current.values.unpack()["ema"],
                  lag=lag.values.unpack()["ema"] if lag is not None else None)
