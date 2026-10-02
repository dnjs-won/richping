"""Frozen Daily exhaustion measurement and new-exposure gate, research only.

The caller supplies already eligible/transformed causal Daily input. No input
selector, action transform, strategy event handler, orders or fills live here.
"""

from dataclasses import dataclass
from datetime import datetime
import math

from ...core import digest, timestamp
from ..contracts import ReplayContext, payload
from ..features.contracts import FeatureResult
from ..features.macd import MACDSpec, macd, macd_series
from ..features.relative import PercentileSpec, rolling_percentile
from ..sessions import RTH, bar_profile
from .daily_trend import PreparedDailyPrefix


def typed_contract(version, semantics):
    def typed(value):
        if isinstance(value, dict):
            return {"kind": "contract", "value": value, "choices": [], "decision_id": None}
        return {"kind": {str: "text", int: "integer", float: "number", bool: "boolean"}[type(value)],
                "value": value, "choices": [], "decision_id": None}
    return {"name": version.lower().removesuffix("_v1"), "version": "v1",
            "parameters": {k: typed(v) for k, v in semantics.items()}}


@dataclass(frozen=True, slots=True)
class DailyExhaustionSpec:
    """One ex-ante tuple; parameter changes require a registered revision."""

    @property
    def version(self):
        return "DAILY_EXHAUSTION_MACD_LINE_PERCENTILE_V1"

    @property
    def macd_spec(self):
        return MACDSpec(12, 26, 9, min_history=130)

    @property
    def percentile_spec(self):
        return PercentileSpec(window=252, min_history=252)

    @property
    def first_ready_count(self):
        return self.macd_spec.min_history + self.percentile_spec.window - 1

    @property
    def semantics(self):
        return {
            "session": "RTH_DAILY", "session_profile": RTH,
            "price_basis": "PIT_SPLIT_ADJUSTED_OHLC",
            "freshness": "LATEST_EXPECTED_COMPLETED_SESSION_REQUIRED",
            "field": "MACD_LINE", "fast": 12, "slow": 26, "signal": 9,
            "macd_min_history": self.macd_spec.min_history,
            "seed": "first_observation", "signal_start": "first_macd_observation",
            "history_origin": "full_available_completed_causal_history", "session_reset": False,
            "relative_transform": "ROLLING_PERCENTILE",
            "transform_version": self.percentile_spec.version,
            "window": self.percentile_spec.window, "min_history": self.percentile_spec.min_history,
            "count_unit": "completed_RTH_DAILY_trading_observations_not_calendar_days",
            "convention": "CURRENT_INCLUSIVE", "ties": "midrank",
            "partial_reference_window": False,
            "readiness_formula": "MACD_min_history_plus_percentile_window_minus_1",
            "first_full_window_expected_N": self.first_ready_count,
            "upper_percentile": 0.95, "comparator": "GREATER_THAN_OR_EQUAL",
            "macd_line_gt_zero": True,
            "states": "NORMAL|EXTENDED|UNAVAILABLE",
            "unavailable": "input_freshness_PIT_evidence_readiness_continuity_finite_known_at_failure",
            "cadence": "new_causally_usable_completed_RTH_Daily_or_actual_evidence_vintage",
            "independent_from_trend": True,
        }

    @property
    def hash(self):
        return digest({"version": self.version, "semantics": self.semantics,
                       "macd_specification_hash": self.macd_spec.hash,
                       "percentile_specification_hash": self.percentile_spec.hash})

    @property
    def contract(self):
        return typed_contract(self.version, {**self.semantics, "state_version": self.version,
            "state_definition_hash": self.hash, "macd_specification_hash": self.macd_spec.hash,
            "percentile_specification_hash": self.percentile_spec.hash})


@dataclass(frozen=True, slots=True)
class DailyExhaustionPolicy:
    @property
    def version(self):
        return "DAILY_EXHAUSTION_BLOCK_NEW_EXPOSURE_V1"

    @property
    def semantics(self):
        return {
            "selected_policy": "P2", "action": "BLOCK_NEW_LONG_EXPOSURE",
            "candidate_types": "INITIAL_ENTRY|ADD|REENTRY",
            "NORMAL": "ALLOW_exhaustion_veto_NONE_other_permissions_still_required",
            "EXTENDED": "BLOCK_EXTENDED", "UNAVAILABLE": "BLOCK_UNAVAILABLE",
            "unavailable_policy": "FAIL_CLOSED_FOR_NEW_EXPOSURE",
            "unavailable_reason": "NEW_EXPOSURE_BLOCKED_DUE_TO_EXHAUSTION_UNAVAILABLE",
            "reentry_is_new_exposure": True,
            "existing_position": "NO_FORCED_EXIT_existing_HOLD_EXIT_unchanged",
            "exit_owner": "1H_EXIT_WATCH_plus_15m_structure_exit",
            "blocked_signal_queue": "DISABLED",
            "blocked_signal_lifecycle": "NO_DEFERRED_EXECUTION_OF_BLOCKED_SIGNAL",
            "subsequent_entry": "requires_new_valid_downstream_H0001_signal_trigger",
            "gate_cadence": "each_future_new_exposure_candidate_latest_causal_Daily_state",
            "global_decision_timing": "owned_by_H1_DECISION_TIMING",
        }

    @property
    def hash(self):
        return digest({"version": self.version, "semantics": self.semantics})

    @property
    def contract(self):
        return typed_contract(self.version, {**self.semantics,
            "policy_version": self.version, "policy_hash": self.hash})


CANONICAL = DailyExhaustionSpec()
POLICY = DailyExhaustionPolicy()
BLOCKER_VERSION = "DAILY_BLOCKER_MACD_LINE_P95_V1"


def blocker_contract():
    return typed_contract(BLOCKER_VERSION, {
        "state_definition": CANONICAL.contract, "policy": POLICY.contract,
        "combined_version": BLOCKER_VERSION,
        "combined_hash": digest({"version": BLOCKER_VERSION,
                                 "state": CANONICAL.hash, "policy": POLICY.hash}),
        "freeze_ref": "research/decision_records/H0001-daily-blocker-freeze-v1.yaml",
        "B0": "NO_BLOCKER_optional_B1_raw_observation_no_actionable_exhaustion_veto",
        "B1": "CANONICAL_DAILY_MACD_LINE_UPPER_RELATIVE_EXTREME",
        "B2": "DEFERRED_SEPARATE_RESEARCH_VARIANT",
        "initial_family": "E0_NO_ACTIONABLE_BLOCKER|E1_CANONICAL_B1_FROZEN_POLICY",
        "primary_comparisons": 1, "parameter_sweeps": "FORBIDDEN",
        "other_variants": "new_revision_and_new_preregistered_trial_family_required",
    })


def exhaustion_label(macd_line, percentile):
    """READY finite operands only; equality is inclusive for rank, strict for sign."""
    if any(type(v) not in (int, float) or not math.isfinite(v)
           for v in (macd_line, percentile)) or not 0 <= percentile <= 1:
        raise ValueError("Finite READY MACD line and percentile in [0,1] required")
    return "EXTENDED" if macd_line > 0 and percentile >= 0.95 else "NORMAL"


@dataclass(frozen=True, slots=True)
class DailyExhaustionState:
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
    state_version: str
    state_definition_hash: str
    input_count: int
    ready_reference_count: int
    macd_line: float | None
    percentile: float | None
    macd_feature: FeatureResult | None
    percentile_feature: FeatureResult | None

    @property
    def hash(self):
        # Observation as_of and feature result as_of are envelopes, not raw state
        # identity. Reusing one fresh Daily input intraday preserves this hash.
        return digest({k: v for k, v in payload(self).items()
                       if k not in {"as_of", "macd_feature", "percentile_feature"}})


def classify_daily_exhaustion(prefix: PreparedDailyPrefix, as_of, spec=CANONICAL):
    if type(prefix) is not PreparedDailyPrefix or type(spec) is not DailyExhaustionSpec:
        raise ValueError("Prepared causal prefix and frozen exhaustion spec required")
    instant, bars = timestamp(as_of), prefix.bars
    causal = (all(b.end_at <= instant and b.known_at <= instant for b in bars)
              and prefix.transform_known_at is not None and prefix.transform_known_at <= instant
              and all(t <= instant for t in prefix.transform_effective_at))
    line_feature = rank_feature = None
    ready_count = 0

    def output(reason=None, line=None, rank=None):
        ready = reason is None
        return DailyExhaustionState(
            prefix.symbol, instant, bars[-1].session if causal and bars else None,
            exhaustion_label(line, rank) if ready else "UNAVAILABLE",
            "READY" if ready else "UNAVAILABLE", reason, prefix.session_profile, prefix.price_basis,
            bars[-1].end_at if causal and bars else None,
            max([prefix.transform_known_at, *(b.known_at for b in bars)]) if causal else None,
            digest({"bars": payload(bars), "vintage": prefix.source_vintage,
                    "transform_known_at": prefix.transform_known_at.isoformat(),
                    "transform_effective_at": [t.isoformat() for t in prefix.transform_effective_at],
                    "session_profile": prefix.session_profile, "price_basis": prefix.price_basis})
            if causal else digest({"rejected_input": reason}),
            prefix.source_vintage, spec.version, spec.hash, len(bars) if causal else 0,
            ready_count, line, rank, line_feature, rank_feature)

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
        context = ReplayContext(instant, bars)
        line_feature = macd(context, prefix.symbol, "Daily", spec.macd_spec)
        if line_feature.status != "READY":
            return output("macd:" + line_feature.reason)
        series = macd_series(context, prefix.symbol, "Daily", spec.macd_spec, field="macd_line")
        reference = series.points[-spec.percentile_spec.window:]
        ready_count = sum(p.status == "READY" for p in reference)
        rank_feature = rolling_percentile(series, spec.percentile_spec)
        if rank_feature.status != "READY":
            return output("percentile:" + rank_feature.reason)
        line = line_feature.values.unpack()["macd_line"]
        rank = rank_feature.values.unpack()["percentile"]
        return output(line=line, rank=rank)
    except (ValueError, OverflowError):
        return output("invalid_nonfinite_or_unsupported_Daily_input")


def evaluate_exhaustion_policy(daily_exhaustion_state, candidate_exposure_event_type):
    """Semantic veto only. No order, sizing, position, exit or deferred queue."""
    if candidate_exposure_event_type not in {"INITIAL_ENTRY", "ADD", "REENTRY"}:
        raise ValueError("Only new LONG exposure candidates belong to this policy")
    if daily_exhaustion_state not in {"NORMAL", "EXTENDED", "UNAVAILABLE"}:
        raise ValueError("Explicit raw exhaustion state required")
    return {"NORMAL": "ALLOW", "EXTENDED": "BLOCK_EXTENDED",
            "UNAVAILABLE": "BLOCK_UNAVAILABLE"}[daily_exhaustion_state]
