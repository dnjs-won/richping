"""One frozen research trigger. No Daily/1H composer, positions or execution.

An opaque scope_ref is a caller's current eligible setup episode reference, not
proof of upstream readiness. Ungated mechanical exercises use a labelled scope.
"""

from dataclasses import asdict, dataclass, replace
from datetime import datetime
import math

from ...core import digest, timestamp
from ..contracts import ReplayContext, payload
from ..features.contracts import ScalarSeries, completed_bars
from ..features.continuity import is_contiguous, slot_bounds
from ..features.macd import MACDSpec, macd_series
from ..features.relative import PercentileSpec, rolling_percentile
from ..sessions import EXTENDED, EXTENDED_CONTINUITY as EC
from .daily_exhaustion import typed_contract


MACD = MACDSpec(12, 26, 9, 130, continuity=EC)
PERCENTILE = PercentileSpec(192, 192, continuity=EC)
VERSION = "M15_INITIAL_EXTREME_GC_PRICE_V1"
FIRST_READY_COUNT = 321
GC_SEMANTICS = {
    "event": "CROSS_EVENT", "previous": "macd_LE_signal", "current": "macd_GT_signal",
    "zero_line": "UNRESTRICTED_at_GC", "operands": "consecutive_completed_READY_15m",
    "persistent_relation": "NOT_A_CROSS_EVENT", "event_reuse": "FORBIDDEN"}
PRICE_SEMANTICS = {
    "family": "COMPLETED_PRICE_RECLAIM", "predicate": "close_GT_previous_completed_close",
    "same_bar_as_GC": True, "equality": "FALSE", "future_or_swing_reference": "NONE",
    "meaning": "minimum_price_direction_confirmation_not_proven_bottom"}
TEMPORAL_SEMANTICS = {
    "family": "D_AND_G_AND_P", "temporal": "FIRST_EXTREME_FIXED_GRACE_NO_REFRESH",
    "K": 4, "unit": "completed_selected_extended_15m_observations",
    "age": "current_index_minus_first_extreme_index", "eligible": "0_LE_age_LE_4",
    "expiry": "age_GT_4_before_reversal", "refresh": "NONE",
    "consume": "first_GC_even_when_price_FALSE", "rearm": "READY_INACTIVE_then_new_extreme",
    "scope": "current_eligible_1H_episode_only_no_outside_arm_carry",
    "cancellation": "UNAVAILABLE_or_upstream_loss_or_episode_or_identity_origin_change",
    "recovery": "new_completed_extreme_only_no_same_identity_restore",
    "candidate": "READY_Daily_BULLISH_NORMAL_AND_1H_ACTIVE_AND_position_FLAT_AND_trigger",
    "position_flat": "explicit_current_evidence_required_UNAVAILABLE_if_absent",
    "duplicates": "one_trigger_identity_per_completed_end_per_scope_no_poll_or_correction_retrigger",
    "candidate_is_order_fill_position": False, "comparator": "NONE",
    "global_position_transitions_add_reentry": "UNRESOLVED_separate_owner"}
TIMING_SEMANTICS = {
    "same_batch": "SAME_ATOMIC_BATCH", "publication": "complete_atomic_batch_before_decision",
    "evaluation_order": "authoritative_Daily_then_frozen_1H_lifetime_then_15m",
    "cadence": "new_completed_15m_identity_not_poll_or_correction",
    "delayed_batch": "end_order_advance_memory_only_latest_expected_15m_may_emit",
    "stale_higher_frame": "latest_expected_completed_inputs_required_no_fallback",
    "known_at": "maximum_actual_required_dependency_arrivals_lte_as_of",
    "unavailable": "cancel_arm_suppress_candidate_no_deferred_execution",
    "global_execution_add_exit_cadence": "UNRESOLVED_separate_contract_owners"}


def frozen_values():
    """Exact typed roots resolved by v12, without resolving global state guards."""
    conventions = {**asdict(PERCENTILE), "field": "macd_line", "macd_line_lt_zero": True,
                   "first_READY_N": FIRST_READY_COUNT, "session_profile": EXTENDED,
                   "history_origin": "full_available_completed_causal_prefix_no_session_reset",
                   "unavailable": "retain_missing_warmup_nonfinite_and_provenance_failures",
                   "known_at": "maximum_actual_MACD_prefix_dependency_arrivals"}
    return {
        ("feature_contracts", "entry_15m_relative_conventions"): typed_contract(PERCENTILE.version, conventions),
        ("rule_parameters", "entry_15m_relative_transform"): "ROLLING_PERCENTILE",
        ("rule_parameters", "entry_15m_rolling_lookback"): 192,
        ("rule_parameters", "entry_15m_downside_threshold"): 0.10,
        ("rule_parameters", "entry_15m_downside_comparator"): "LE",
        ("rule_parameters", "entry_15m_gc"): typed_contract("M15_GC_CROSS_V1", GC_SEMANTICS),
        ("rule_parameters", "entry_15m_price_reversal"): typed_contract("M15_PRICE_CLOSE_RECOVERY_V1", PRICE_SEMANTICS),
        ("rule_parameters", "entry_15m_trigger_conjunction"): typed_contract(VERSION, TEMPORAL_SEMANTICS),
        ("state_machine_parameters", "decision_timing"): typed_contract("H0001_INITIAL_ENTRY_TIMING_V1", TIMING_SEMANTICS),
    }


def contract_hash():
    return digest({"version": VERSION, "macd": MACD.hash, "percentile": PERCENTILE.hash,
                   "roots": {f"{s}.{k}": v for (s, k), v in frozen_values().items()}})


def _finite(*values):
    return all(type(v) in (int, float) and math.isfinite(v) for v in values)


def downside_label(line, percentile):
    if not _finite(line, percentile) or not 0 <= percentile <= 1:
        raise ValueError("Finite READY MACD and rank in [0,1] required")
    return "DOWNSIDE_EXTREME" if line < 0 and percentile <= .10 else "INACTIVE"


def gc_event(previous_line, previous_signal, line, signal):
    if not _finite(previous_line, previous_signal, line, signal):
        return None
    return previous_line <= previous_signal and line > signal


def price_confirmation(previous_close, close):
    return close > previous_close if _finite(previous_close, close) else None


@dataclass(frozen=True, slots=True)
class M15Observation:
    symbol: str
    end_at: datetime
    known_at: datetime
    as_of: datetime
    index: int
    history_origin: datetime
    source_vintage: str
    input_hash: str
    raw: str
    reason: str | None
    line: float | None
    signal: float | None
    percentile: float | None
    ready_reference_count: int
    gc: bool | None
    price: bool | None

    def __post_init__(self):
        for key in ("end_at", "known_at", "as_of", "history_origin"):
            object.__setattr__(self, key, timestamp(getattr(self, key)))
        if not self.history_origin <= self.end_at <= self.known_at <= self.as_of:
            raise ValueError("Causal completed observation required")
        slot_bounds(self.end_at, "15m", EC)
        if type(self.index) is not int or self.index < 0 or not self.source_vintage or not self.input_hash:
            raise ValueError("Explicit immutable observation identity required")
        if self.raw == "UNAVAILABLE":
            if not self.reason or self.percentile is not None:
                raise ValueError("UNAVAILABLE requires reason, no fabricated rank")
        elif self.reason is not None or self.raw != downside_label(self.line, self.percentile):
            raise ValueError("READY downside predicate mismatch")
        if not 0 <= self.ready_reference_count <= 192 or any(type(v) not in (bool, type(None)) for v in (self.gc, self.price)):
            raise ValueError("Explicit operand availability required")

    @property
    def identity_hash(self):
        return digest({k: v for k, v in payload(self).items() if k != "as_of"})


def measure_completed_15m(context, symbol):
    """Materialize causal scalar prefixes, never use a suffix to rank a point.

    ReplayContext bounds actual availability. Historical points retain running
    max dependency known_at; this is a research vintage, not a live PIT claim.
    Invalid provenance fails at this admission boundary; classifier maps it to
    UNAVAILABLE. Scalar warmup/missing slots are retained by existing primitives.
    """
    bars = completed_bars(context, symbol, "15m", EC)
    if not bars:
        return ()
    provenance = {(b.source, b.corporate_action,
                   b.provenance.unpack().get("price_basis"),
                   b.provenance.unpack().get("known_at_policy")) for b in bars}
    if len(provenance) != 1:
        raise ValueError("mixed_provider_price_or_availability_provenance")
    lines = macd_series(context, symbol, "15m", MACD, field="macd_line")
    signals = macd_series(context, symbol, "15m", MACD, field="signal_line")
    output, input_chain = [], digest({"MACD": MACD.hash})
    for i, (bar, line, signal) in enumerate(zip(bars, lines.points, signals.points)):
        input_chain = digest({"previous_prefix": input_chain, "bar": payload(bar)})
        # Only the selected prefix's last W slots enter the rolling transform.
        points = lines.points[max(0, i + 1 - PERCENTILE.window):i + 1]
        series = ScalarSeries(symbol, "15m", line.known_at, lines.source, points, input_chain)
        rank = rolling_percentile(series, PERCENTILE)
        ready_count = sum(p.status == "READY" for p in points)
        reason = None if rank.status == "READY" else "percentile:" + rank.reason
        percentile = rank.values.unpack().get("percentile")
        cross = (gc_event(lines.points[i-1].value, signals.points[i-1].value, line.value, signal.value)
                 if i and lines.points[i-1].status == signals.points[i-1].status == "READY" else None)
        price = price_confirmation(bars[i-1].close, bar.close) if i and cross is not None else None
        output.append(M15Observation(symbol, bar.end_at, line.known_at, context.as_of,
            i, bars[0].end_at, bar.dataset_id, input_chain,
            downside_label(line.value, percentile) if reason is None else "UNAVAILABLE",
            reason, line.value, signal.value, percentile, ready_count, cross, price))
    return tuple(output)


def classify_15m(context, symbol, *, expected_completed_end):
    """Latest prepared prefix only; missing/stale/provenance is UNAVAILABLE."""
    selected = context.query(symbol, "15m")
    if not selected:
        raise ValueError("At least one completed source identity required")
    current = selected[-1]
    try:
        if expected_completed_end is None or current.end_at != timestamp(expected_completed_end):
            raise ValueError("latest_expected_completed_15m_missing")
        return measure_completed_15m(context, symbol)[-1]
    except (ValueError, OverflowError) as exc:
        return M15Observation(symbol, current.end_at, max(b.known_at for b in selected),
            context.as_of, len(selected)-1, selected[0].end_at, current.dataset_id,
            digest({"rejected_prefix": payload(selected)}), "UNAVAILABLE", str(exc),
            None, None, None, 0, None, None)


@dataclass(frozen=True, slots=True)
class M15Memory:
    observation: M15Observation
    scope_ref: str | None
    arm_index: int | None
    arm_end: datetime | None
    locked: bool
    trigger: bool
    event: str

    def __post_init__(self):
        if (type(self.observation) is not M15Observation
                or type(self.locked) is not bool or type(self.trigger) is not bool
                or (self.arm_index is None) != (self.arm_end is None)):
            raise ValueError("Immutable typed trigger memory required")
        if self.arm_index is not None and (type(self.arm_index) is not int
                or not 0 <= self.arm_index <= self.observation.index
                or not self.observation.history_origin <= self.arm_end <= self.observation.end_at
                or self.locked or not self.scope_ref):
            raise ValueError("Nonfuture eligible arming identity required")
        if self.trigger and (self.event != "TRIGGER" or self.arm_index is not None
                or not self.locked or not self.scope_ref):
            raise ValueError("Consumed trigger provenance required")


def evaluate_temporal(previous, observation, *, scope_ref, emit_eligible=True):
    """Pure trigger-local C1 state; caller owns eligibility/upstream proof.

    Same atomic batch is admitted after upstream publication: pass its *current*
    eligible episode ref. None cancels. Deferred/stale batch members may advance
    memory but consume/reject a GC without emitting (emit_eligible=False).
    No candidate, signal/position transition or order is created here.
    """
    if type(observation) is not M15Observation or (previous is not None and type(previous) is not M15Memory):
        raise ValueError("Frozen completed observation and memory required")
    if scope_ref is not None and (type(scope_ref) is not str or not scope_ref):
        raise ValueError("Explicit eligible episode reference or None required")
    if type(emit_eligible) is not bool:
        raise ValueError("Explicit latest-expected emission eligibility required")
    old = previous.observation if previous else None
    if old and (old.symbol != observation.symbol or old.as_of > observation.as_of or old.end_at > observation.end_at):
        raise ValueError("Monotone same-symbol evaluation required")
    arm = previous.arm_index if previous else None
    arm_end = previous.arm_end if previous else None
    locked = previous.locked if previous else False
    fresh = old is None or observation.end_at > old.end_at
    broken = old is not None and fresh and (observation.index != old.index + 1
        or observation.history_origin != old.history_origin or observation.source_vintage != old.source_vintage
        or not is_contiguous((old, observation), "15m", EC))
    changed = old is not None and not fresh and observation.identity_hash != old.identity_hash
    if broken or changed or observation.raw == "UNAVAILABLE" or observation.gc is None or observation.price is None:
        return M15Memory(observation, scope_ref, None, None, False, False, "UNAVAILABLE_CANCEL")
    if scope_ref is None:
        return M15Memory(observation, None, None, None, False, False, "UPSTREAM_CANCEL")
    if not fresh:
        # Recovery/correction/poll of a rejected source never creates an event.
        return replace(previous, observation=observation, scope_ref=scope_ref,
                       arm_index=arm if previous.scope_ref == scope_ref else None,
                       arm_end=arm_end if previous.scope_ref == scope_ref else None,
                       locked=locked if previous.scope_ref == scope_ref else False,
                       trigger=False, event="DUPLICATE_NO_EVENT")
    if previous and previous.scope_ref != scope_ref:
        arm = arm_end = None
        locked = False
    event = "INACTIVE"
    if arm is not None and observation.index - arm > 4:
        arm = arm_end = None
        locked, event = True, "EXPIRED"
    if locked and observation.raw == "INACTIVE":
        locked = False
    if arm is None and not locked and observation.raw == "DOWNSIDE_EXTREME":
        arm, arm_end, event = observation.index, observation.end_at, "ARMED"
    if arm is not None and observation.gc:
        trigger = bool(observation.price and emit_eligible)
        return M15Memory(observation, scope_ref, None, None, True, trigger,
                         "TRIGGER" if trigger else "FIRST_GC_REJECTED_CONSUMED")
    return M15Memory(observation, scope_ref, arm, arm_end, locked, False, event)
