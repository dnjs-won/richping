"""Frozen H0001 1H context and setup-local grace, detached research only.

No input selector, provider, trigger, order, fill or position lifecycle. Prepared
eligibility and upstream references are caller facts at the exact atomic as_of.
"""

from dataclasses import asdict, dataclass, replace
from datetime import datetime
import math

from ...core import digest, ticker, timestamp
from ..contracts import MarketBar, ReplayContext, StrategyState, JsonObject, payload
from ..features.contracts import FeatureResult
from ..features.macd import MACDSpec, macd, macd_series
from ..features.relative import PercentileSpec, rolling_percentile
from ..features.continuity import slot_bounds
from ..sessions import EXTENDED, EXTENDED_CONTINUITY as EC, bar_profile
from .daily_exhaustion import typed_contract


@dataclass(frozen=True, slots=True)
class H1RelativeSetupSpec:
    @property
    def version(self):
        return "H1_RELATIVE_DOWNSIDE_MACD_P05_V1"

    @property
    def macd_spec(self):
        return MACDSpec(12, 26, 9, 130, continuity=EC)

    @property
    def percentile_spec(self):
        return PercentileSpec(320, 320, continuity=EC)

    @property
    def first_ready_count(self):
        return self.macd_spec.min_history + self.percentile_spec.window - 1

    @property
    def semantics(self):
        return {"field": "MACD_LINE", "method": "ROLLING_PERCENTILE",
                "session": "RTH_EXTENDED", "session_profile": EXTENDED,
                "count_unit": "completed_selected_extended_1H_observations",
                "history_origin": "full_available_completed_causal_history",
                "session_reset": False, "reference": "CURRENT_INCLUSIVE",
                "partial_window": False, "polarity": "MACD_LINE_LT_ZERO",
                "cutoff": 0.05, "comparator": "LE",
                "states": "INACTIVE|DOWNSIDE_EXTREME|UNAVAILABLE",
                "role": "SETUP_CONTEXT_NOT_BUY_OR_PRICE_BOTTOM",
                "independent_from_Daily": True, "completed_only": True}

    @property
    def hash(self):
        return digest({"version": self.version, "semantics": self.semantics,
                       "macd": self.macd_spec.hash, "percentile": self.percentile_spec.hash})

    @property
    def relative_contract(self):
        return typed_contract(self.percentile_spec.version, {
            **asdict(self.percentile_spec), "field": "macd_line", "macd_line_lt_zero": True})


@dataclass(frozen=True, slots=True)
class H1SetupLifetimeSpec:
    @property
    def version(self):
        return "LAST_EXTREME_REFRESH_WITH_FIXED_GRACE_V1"

    @property
    def semantics(self):
        return {"K": 2, "unit": "completed_selected_extended_1H_observations",
                "age": "current_index_minus_last_extreme_index",
                "active": "age_LE_K", "expiry": "age_GT_K",
                "activation": "Daily_BULLISH_AND_exhaustion_NORMAL_AND_new_1H_extreme",
                "refresh": "each_new_completed_extreme_resets_age_zero",
                "activation_at": "current_atomic_as_of_gte_actual_feature_known_at",
                "UNAVAILABLE": "CANCEL_1H_UNAVAILABLE",
                "Daily_trend_loss": "CANCEL_DAILY_PERMISSION",
                "Daily_exhaustion_loss": "CANCEL_DAILY_EXHAUSTION",
                "cancellation_recovery": "new_completed_extreme_required_no_automatic_restore",
                "same_observation": "no_age_increment_no_refresh_no_reactivation",
                "observation_delivery": "every_new_completed_identity_in_order_skips_or_origin_changes_cancel",
                "session_carry": "observation_clock_no_wall_time_expiry_or_session_reset",
                "blocked_trigger_queue": "NO_DEFERRED_EXECUTION",
                "entry_consumption_add_reentry_position_open": "owned_by_unresolved_downstream_decisions",
                "global_state_transitions": "UNRESOLVED_setup_local_only"}

    @property
    def hash(self):
        return digest({"version": self.version, "semantics": self.semantics})

    @property
    def contract(self):
        return typed_contract(self.version, {**self.semantics,
            "lifetime_version": self.version, "lifetime_hash": self.hash,
            "raw_version": CANONICAL.version, "raw_hash": CANONICAL.hash,
            "freeze_ref": "research/decision_records/H0001-1h-relative-setup-freeze-v1.yaml",
            "canonical": "S1", "comparison_candidate": "S0_NO_1H_DOWNSIDE_SETUP_FILTER",
            "primary_comparisons": 1, "R2": "DEFERRED_SEPARATE_RESEARCH_VARIANT",
            "R3": "DEFERRED_SEPARATE_RESEARCH_VARIANT", "parameter_sweeps": "FORBIDDEN"})


CANONICAL = H1RelativeSetupSpec()
LIFETIME = H1SetupLifetimeSpec()


def downside_label(macd_line, percentile):
    if any(type(v) not in (int, float) or not math.isfinite(v) for v in (macd_line, percentile)) or not 0 <= percentile <= 1:
        raise ValueError("Finite READY line and percentile in [0,1] required")
    return "DOWNSIDE_EXTREME" if macd_line < 0 and percentile <= 0.05 else "INACTIVE"


@dataclass(frozen=True, slots=True)
class PreparedH1Prefix:
    """No freshness selector: caller attests expected completion and input evidence.

    expected_completed_end excludes the in-progress bucket; on missing/delayed
    expected input the older delivered bar is not silently current. This does
    not select a real intraday price/action basis or implement its transform.
    """
    symbol: str
    bars: tuple[MarketBar, ...]
    eligibility_as_of: datetime
    expected_completed_end: datetime | None
    source_vintage: str
    evidence_known_at: datetime | None
    input_status: str = "READY"
    input_reason: str | None = None
    price_basis: str = "synthetic_unadjusted"

    def __post_init__(self):
        if ticker(self.symbol) != self.symbol or not self.source_vintage or not self.price_basis:
            raise ValueError("Explicit normalized identity/vintage/basis required")
        object.__setattr__(self, "bars", tuple(self.bars))
        for name in ("eligibility_as_of", "expected_completed_end", "evidence_known_at"):
            if getattr(self, name) is not None:
                object.__setattr__(self, name, timestamp(getattr(self, name)))
        if any(type(b) is not MarketBar for b in self.bars):
            raise ValueError("Immutable completed bars required")
        if self.input_status not in {"READY", "UNAVAILABLE"} or (
                (self.input_status == "READY") != (self.input_reason is None)):
            raise ValueError("Input status/reason mismatch")


@dataclass(frozen=True, slots=True)
class H1RelativeSetupRawState:
    symbol: str
    as_of: datetime
    source_1h_end: datetime | None
    source_1h_known_at: datetime | None
    history_origin: datetime | None
    completed_index: int | None
    state: str
    status: str
    reason: str | None
    input_hash: str
    source_vintage: str
    price_basis: str
    contract_version: str
    contract_hash: str
    input_count: int
    ready_reference_count: int
    macd_line: float | None
    percentile: float | None
    macd_feature: FeatureResult | None = None
    percentile_feature: FeatureResult | None = None

    def __post_init__(self):
        if ticker(self.symbol) != self.symbol or self.contract_hash != CANONICAL.hash or self.contract_version != CANONICAL.version:
            raise ValueError("Frozen raw identity required")
        for name in ("as_of", "source_1h_end", "source_1h_known_at", "history_origin"):
            if getattr(self, name) is not None:
                object.__setattr__(self, name, timestamp(getattr(self, name)))
        if self.source_1h_end is not None and (self.source_1h_known_at is None or not self.source_1h_end <= self.source_1h_known_at <= self.as_of):
            raise ValueError("Noncausal raw observation")
        if (type(self.input_count) is not int or self.input_count < 0
                or type(self.ready_reference_count) is not int or not 0 <= self.ready_reference_count <= 320
                or (self.completed_index is not None and (
                    type(self.completed_index) is not int or self.completed_index != self.input_count - 1))):
            raise ValueError("Explicit completed observation index/count required")
        if self.source_1h_end is not None and (self.history_origin is None or self.history_origin > self.source_1h_end):
            raise ValueError("One ordered history origin required")
        if self.status == "READY":
            if self.reason is not None or self.state != downside_label(self.macd_line, self.percentile) or self.completed_index is None:
                raise ValueError("READY raw predicate mismatch")
        elif self.status != "UNAVAILABLE" or self.state != "UNAVAILABLE" or not self.reason or self.macd_line is not None or self.percentile is not None:
            raise ValueError("Unavailable raw state requires reason, no numeric operands")

    @property
    def hash(self):
        return digest({k: v for k, v in payload(self).items()
                       if k not in {"as_of", "macd_feature", "percentile_feature"}})


def classify_h1_relative_setup(prefix: PreparedH1Prefix, as_of, spec=CANONICAL):
    if type(prefix) is not PreparedH1Prefix or type(spec) is not H1RelativeSetupSpec:
        raise ValueError("Prepared causal 1H prefix and frozen spec required")
    instant, bars = timestamp(as_of), prefix.bars
    causal = (prefix.evidence_known_at is not None and prefix.evidence_known_at <= instant
              and all(b.end_at <= instant and b.known_at <= instant for b in bars))
    identified = (causal and bool(bars)
                  and all(b.symbol == prefix.symbol and b.timeframe == "1H"
                          and b.provenance.unpack().get("session_profile") == EXTENDED for b in bars)
                  and all(a.end_at < b.end_at for a, b in zip(bars, bars[1:])))
    line_feature = rank_feature = None
    ready_count = 0

    def output(reason=None, line=None, rank=None):
        return H1RelativeSetupRawState(prefix.symbol, instant,
            bars[-1].end_at if identified else None,
            max([prefix.evidence_known_at, *(b.known_at for b in bars)]) if identified else None,
            bars[0].end_at if identified else None, len(bars) - 1 if identified else None,
            downside_label(line, rank) if reason is None else "UNAVAILABLE",
            "READY" if reason is None else "UNAVAILABLE", reason,
            digest({"bars": payload(bars), "vintage": prefix.source_vintage,
                    "evidence_known_at": prefix.evidence_known_at.isoformat(),
                    "price_basis": prefix.price_basis}) if causal else digest({"rejected_input": reason}),
            prefix.source_vintage, prefix.price_basis, spec.version, spec.hash,
            len(bars) if causal else 0, ready_count, line, rank, line_feature, rank_feature)

    if prefix.eligibility_as_of != instant:
        return output("eligibility_as_of_mismatch")
    if not causal:
        return output("required_input_evidence_unavailable" if prefix.evidence_known_at is None
                      else "future_1H_or_input_evidence")
    if prefix.input_status != "READY":
        return output(prefix.input_reason)
    if not bars:
        return output("no_completed_1H_input")
    if prefix.expected_completed_end is None:
        return output("expected_completion_evidence_unavailable")
    try:
        slot_bounds(prefix.expected_completed_end, "1H", EC)
        if prefix.expected_completed_end > instant or bars[-1].end_at != prefix.expected_completed_end:
            return output("latest_expected_completed_1H_missing")
        if (any(b.symbol != prefix.symbol or b.timeframe != "1H" or bar_profile(b) != EXTENDED for b in bars)
                or any(a.end_at >= b.end_at for a, b in zip(bars, bars[1:]))):
            return output("invalid_1H_prefix")
        context = ReplayContext(instant, bars)
        line_feature = macd(context, prefix.symbol, "1H", spec.macd_spec)
        series = macd_series(context, prefix.symbol, "1H", spec.macd_spec, field="macd_line")
        ready_count = sum(p.status == "READY" for p in series.points[-spec.percentile_spec.window:])
        rank_feature = rolling_percentile(series, spec.percentile_spec)
        for feature, name in ((line_feature, "macd"), (rank_feature, "percentile")):
            if feature.status != "READY":
                return output(name + ":" + feature.reason)
        return output(line=line_feature.values.unpack()["macd_line"], rank=rank_feature.values.unpack()["percentile"])
    except (ValueError, OverflowError):
        return output("invalid_nonfinite_or_unsupported_1H_input")


@dataclass(frozen=True, slots=True)
class SetupDailyPermission:
    symbol: str
    as_of: datetime
    known_at: datetime
    trend: str
    exhaustion: str
    trend_ref_hash: str
    exhaustion_ref_hash: str

    def __post_init__(self):
        for name in ("as_of", "known_at"):
            object.__setattr__(self, name, timestamp(getattr(self, name)))
        if (ticker(self.symbol) != self.symbol or self.known_at > self.as_of
                or self.trend not in {"BULLISH", "NOT_BULLISH", "UNAVAILABLE"}
                or self.exhaustion not in {"NORMAL", "EXTENDED", "UNAVAILABLE"}
                or not self.trend_ref_hash or not self.exhaustion_ref_hash):
            raise ValueError("Causal explicit Daily permission references required")


@dataclass(frozen=True, slots=True)
class H1SetupEpisode:
    symbol: str
    as_of: datetime
    status: str
    event: str
    reason: str | None
    episode_id: str | None
    activation_at: datetime | None
    last_extreme_at: datetime | None
    last_extreme_end: datetime | None
    last_extreme_index: int | None
    age_since_last_extreme: int | None
    expiry_at: datetime | None
    cancellation_reason: str | None
    last_seen_end: datetime | None
    last_seen_index: int | None
    history_origin: datetime | None
    raw_ref_hash: str
    daily_refs: JsonObject
    contract_hash: str
    cancellation_at: datetime | None = None

    def __post_init__(self):
        for name in ("as_of", "activation_at", "last_extreme_at", "last_extreme_end", "expiry_at", "last_seen_end", "history_origin", "cancellation_at"):
            if getattr(self, name) is not None:
                object.__setattr__(self, name, timestamp(getattr(self, name)))
        if (ticker(self.symbol) != self.symbol or self.status not in {"ACTIVE", "INACTIVE", "EXPIRED", "CANCELLED"}
                or self.contract_hash != LIFETIME.hash or type(self.daily_refs) is not JsonObject):
            raise ValueError("Frozen immutable episode identity required")
        if any(getattr(self, name) is not None and getattr(self, name) > self.as_of for name in (
                "activation_at", "last_extreme_at", "last_extreme_end", "expiry_at", "last_seen_end", "history_origin", "cancellation_at")):
            raise ValueError("Future episode timestamp")
        if self.status in {"ACTIVE", "EXPIRED", "CANCELLED"} and any(value is None for value in (
                self.episode_id, self.activation_at, self.last_extreme_at, self.last_extreme_index, self.age_since_last_extreme)):
            raise ValueError("Episode lifecycle provenance required")
        if self.status == "ACTIVE" and not 0 <= self.age_since_last_extreme <= 2:
            raise ValueError("ACTIVE episode exceeds frozen grace")
        if self.status == "EXPIRED" and (self.expiry_at is None or self.age_since_last_extreme <= 2):
            raise ValueError("Expired grace provenance required")
        if self.status == "CANCELLED" and (self.cancellation_reason is None or self.cancellation_at is None):
            raise ValueError("Cancellation reason required")

    @property
    def transport(self):
        return StrategyState(LIFETIME.version, JsonObject.of(payload(self)))

    @classmethod
    def from_transport(cls, state):
        if type(state) is not StrategyState or state.version != LIFETIME.version:
            raise ValueError("Frozen episode transport required")
        body = state.data.unpack()
        body["daily_refs"] = JsonObject.of(body["daily_refs"])
        return cls(**body)


def evaluate_h1_setup_lifetime(previous, raw, daily, spec=LIFETIME):
    """One ordered completed identity per step; same-identity as_of calls allowed.

    Upstream loss and raw unavailability cancel immediately, including between
    hour completions. A watermark prevents replaying an old extreme after loss.
    No trigger consumption, position state, request or execution is produced.
    """
    if (type(raw) is not H1RelativeSetupRawState or type(daily) is not SetupDailyPermission
            or type(spec) is not H1SetupLifetimeSpec or (previous is not None and type(previous) is not H1SetupEpisode)):
        raise ValueError("Frozen raw, episode and Daily references required")
    if raw.symbol != daily.symbol or raw.as_of != daily.as_of:
        raise ValueError("Aligned current raw and Daily references required")
    if previous is not None and (previous.symbol != raw.symbol or previous.as_of > raw.as_of or previous.contract_hash != spec.hash):
        raise ValueError("Monotone same-symbol frozen episode required")
    refs = JsonObject.of(payload(daily))
    old = previous or H1SetupEpisode(raw.symbol, raw.as_of, "INACTIVE", "NO_SETUP", None,
        None, None, None, None, None, None, None, None, None, None, None, raw.hash, refs, spec.hash)
    new_end = raw.source_1h_end
    if new_end is not None and old.last_seen_end is not None and new_end < old.last_seen_end:
        raise ValueError("Completed observation identity cannot move backward")
    fresh = new_end is not None and (old.last_seen_end is None or new_end > old.last_seen_end)
    current = replace(old, as_of=raw.as_of, raw_ref_hash=raw.hash, daily_refs=refs,
        last_seen_end=new_end if fresh else old.last_seen_end,
        last_seen_index=raw.completed_index if fresh else old.last_seen_index,
        history_origin=raw.history_origin if fresh else old.history_origin, event="UNCHANGED")

    cancellation = ("SETUP_CANCELLED_1H_UNAVAILABLE" if raw.state == "UNAVAILABLE" else
                    "SETUP_CANCELLED_DAILY_PERMISSION" if daily.trend != "BULLISH" else
                    "SETUP_CANCELLED_DAILY_EXHAUSTION" if daily.exhaustion != "NORMAL" else None)
    if cancellation:
        return replace(current, status="CANCELLED", event="CANCELLED", reason=cancellation,
                       cancellation_reason=cancellation, cancellation_at=raw.as_of) if old.status == "ACTIVE" else replace(current, event="BLOCKED", reason=cancellation)
    # Never infer unseen refreshes or an index clock from a different origin.
    if old.status == "ACTIVE" and (raw.history_origin != old.history_origin
            or raw.completed_index != old.last_seen_index + int(fresh)):
        return replace(current, status="CANCELLED", event="CANCELLED",
                       reason="SETUP_CANCELLED_1H_UNAVAILABLE", cancellation_reason="SETUP_CANCELLED_1H_UNAVAILABLE", cancellation_at=raw.as_of)
    if not fresh:
        return current
    if raw.state == "DOWNSIDE_EXTREME":
        if old.status == "ACTIVE":
            return replace(current, event="EXTREME_REFRESH", reason=None,
                last_extreme_at=raw.as_of, last_extreme_end=new_end,
                last_extreme_index=raw.completed_index, age_since_last_extreme=0)
        return replace(current, status="ACTIVE", event="ACTIVATED", reason=None,
            episode_id=digest([raw.symbol, raw.hash, raw.as_of.isoformat(), spec.hash]),
            activation_at=raw.as_of, last_extreme_at=raw.as_of, last_extreme_end=new_end,
            last_extreme_index=raw.completed_index, age_since_last_extreme=0,
            expiry_at=None, cancellation_reason=None, cancellation_at=None)
    if old.status == "ACTIVE":
        age = raw.completed_index - old.last_extreme_index
        if age > spec.semantics["K"]:
            return replace(current, status="EXPIRED", event="EXPIRE_GRACE", reason="EXPIRE_GRACE",
                           age_since_last_extreme=age, expiry_at=raw.as_of)
        return replace(current, event="GRACE", reason=None, age_since_last_extreme=age)
    return replace(current, event="NO_NEW_EXTREME")


def setup_trace(raw, episode, *, downstream_trigger_ref=None):
    """Immutable payload only; no logger/label writer or future trigger lookup."""
    if raw.symbol != episode.symbol or raw.as_of != episode.as_of or raw.hash != episode.raw_ref_hash:
        raise ValueError("Aligned raw and episode trace required")
    return JsonObject.of({"symbol": raw.symbol, "as_of": raw.as_of.isoformat(),
        "source_1h_end": payload(raw.source_1h_end), "source_1h_known_at": payload(raw.source_1h_known_at),
        "macd_line": raw.macd_line, "percentile": raw.percentile,
        "percentile_version": CANONICAL.percentile_spec.version,
        "percentile_hash": CANONICAL.percentile_spec.hash, "window": 320,
        "threshold": 0.05, "comparator": "LE", "polarity": "MACD_LINE_LT_ZERO",
        "raw_state": raw.state, "status_reason": raw.reason, "setup_status": episode.status,
        "activation_at": payload(episode.activation_at), "last_extreme_at": payload(episode.last_extreme_at),
        "age_since_last_extreme": episode.age_since_last_extreme, "expiry_at": payload(episode.expiry_at),
        "cancellation_reason": episode.cancellation_reason, "Daily_refs": episode.daily_refs.unpack(),
        "cancellation_at": payload(episode.cancellation_at),
        "input_hash": raw.input_hash, "source_vintage": raw.source_vintage,
        "downstream_trigger_ref": downstream_trigger_ref, "setup_contract_version": LIFETIME.version,
        "setup_contract_hash": LIFETIME.hash, "raw_contract_version": raw.contract_version,
        "raw_contract_hash": raw.contract_hash, "raw_ref_hash": raw.hash,
        "ready_reference_count": raw.ready_reference_count, "episode_id": episode.episode_id})
