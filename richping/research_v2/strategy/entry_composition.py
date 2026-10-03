"""Frozen initial-entry opportunities only; no execution or outcome dependency."""

from dataclasses import dataclass
from pathlib import Path
import json

from ...core import canonical, digest, timestamp, ticker
from ..contracts import JsonObject, payload
from ..sessions import NY, RTH, EXTENDED
from .entry_15m import M15Memory, VERSION as M15_VERSION, contract_hash as m15_hash
from .h1_setup import H1SetupEpisode, CANONICAL as H1, LIFETIME
from .daily_trend import CANONICAL as TREND
from .daily_exhaustion import CANONICAL as EXHAUSTION
from .daily_exhaustion import typed_contract
from .mixed_profile import VERSION as JOIN_VERSION, expected_extended_end
from .daily_input import expected_daily_session

VERSION = "H0001_INITIAL_ENTRY_COMPOSER_V1"
POSITION_VERSION = "RESEARCH_ENTRY_POSITION_EVIDENCE_V1"
MODE = "CANDIDATE_ONLY_FLAT_RESEARCH_MODE_V1"
EPISODE_VERSION = "H0001_INITIAL_ENTRY_EPISODE_IDENTITY_V1"
SEMANTICS = {
    "gates": "READY_BULLISH_Daily_AND_READY_NORMAL_exhaustion_AND_ACTIVE_H1_AND_READY_TRUE_M15_AND_explicit_FLAT_AND_unconsumed_episode",
    "order": "atomic_publication_Daily_H1_raw_lifetime_M15_position_consumption_evaluation_immutable_emission",
    "episode": "reuse_LIFETIME_episode_id_digest_symbol_activation_raw_hash_activation_as_of_lifetime_hash",
    "consumption": "first_candidate_consumes_initial_right_only_refresh_does_not_reset",
    "new_episode": "expiry_cancellation_continuity_origin_loss_then_new_completed_H1_extreme_activation",
    "position": "explicit_versioned_provenance_hash_missing_UNAVAILABLE_FLAT_OPEN_UNAVAILABLE_no_candidate_to_OPEN",
    "research_mode": "admission_for_opportunity_only_forbidden_for_execution_portfolio_evaluation",
    "timing": "SAME_ATOMIC_BATCH_latest_expected_completed_only_no_partial_poll_correction_or_deferred_emission",
    "identity": "digest_symbol_type_as_of_end_Daily_refs_episode_ref_trigger_ref_position_ref_spec_composer_causal_hash",
    "store": "immutable_canonical_JSON_same_identity_different_payload_collision",
    "resolved": "initial_entry_candidate_lifecycle_only",
    "unresolved": "actual_position_open_add_exit_reentry_execution_stop_trailing_sizing_fill_cost",
    "outcomes": "NOT_RUN",
}


def contract():
    return {"version": VERSION, "semantics": SEMANTICS,
            "sources": {"trend": TREND.hash, "exhaustion": EXHAUSTION.hash,
                        "h1_raw": H1.hash, "h1_lifetime": LIFETIME.hash, "m15": m15_hash()},
            "position_version": POSITION_VERSION, "position_mode": MODE,
            "episode_version": EPISODE_VERSION}


def contract_hash():
    return digest(contract())


def specification_root():
    root = typed_contract(VERSION, {**SEMANTICS, "composer_hash": contract_hash()})
    for scope in ("actual_position_open", "add", "exit", "reentry", "execution"):
        root["parameters"][scope] = {"kind": "contract", "value": "UNRESOLVED",
                                     "choices": [], "decision_id": "H1-STATE-TRANSITIONS"}
    return root


@dataclass(frozen=True, slots=True)
class PositionEvidence:
    symbol: str
    as_of: str
    known_at: str
    state: str
    mode: str
    provenance: JsonObject
    version: str = POSITION_VERSION

    def __post_init__(self):
        object.__setattr__(self, "as_of", timestamp(self.as_of).isoformat())
        object.__setattr__(self, "known_at", timestamp(self.known_at).isoformat())
        if (ticker(self.symbol) != self.symbol or self.version != POSITION_VERSION
                or self.state not in {"FLAT", "OPEN", "UNAVAILABLE"}
                or self.mode != MODE or type(self.provenance) is not JsonObject
                or not self.provenance.unpack()):
            raise ValueError("Explicit versioned research position evidence required")

    @property
    def hash(self):
        return digest(payload(self))


def flat_research_evidence(symbol, as_of, *, daily_hash, intraday_hash):
    if not daily_hash or not intraday_hash:
        raise ValueError("Fixed dataset provenance required")
    return PositionEvidence(symbol, as_of, as_of, "FLAT", MODE, JsonObject.of({
        "admission": "INITIAL_ENTRY_OPPORTUNITY_RESEARCH_ONLY", "daily_hash": daily_hash,
        "intraday_hash": intraday_hash, "actual_portfolio_claim": False,
        "execution_portfolio_reuse": "FORBIDDEN", "candidate_changes_position": False}))


@dataclass(frozen=True, slots=True)
class Consumption:
    episode_id: str | None = None
    consumed: bool = False
    last_end: str | None = None


@dataclass(frozen=True, slots=True)
class CompositionResult:
    status: str
    reason: str
    memory: Consumption
    event: JsonObject | None = None


def compose_initial_entry(joined, episode, trigger, evidence, previous=None, *, specification, previous_trigger=None):
    """Consume validated frozen outputs, never recompute any primitive/lifetime."""
    old = previous or Consumption()
    as_of = timestamp(joined["as_of"])
    active = type(episode) is H1SetupEpisode and episode.status == "ACTIVE"
    episode_id = episode.episode_id if active else None
    consumed = old.consumed if old.episode_id == episode_id and active else False
    end = trigger.observation.end_at.isoformat() if type(trigger) is M15Memory else None
    memory = Consumption(episode_id, consumed, max(filter(None, (old.last_end, end)), default=None))

    def reject(status, reason):
        return CompositionResult(status, reason, memory)

    refs = {r["role"]: r for r in joined.get("references", [])}
    roles = ("DAILY_TREND_PERMISSION", "DAILY_EXHAUSTION", "H1_RELATIVE_SETUP_RAW", "M15_INITIAL_ENTRY_PRIMITIVE")
    if (set(refs) != set(roles) or len(joined.get("references", [])) != 4
            or joined.get("version") != JOIN_VERSION or joined.get("publication") != "atomic_known_at_batch_v1"):
        return reject("UNAVAILABLE", "MISSING_OR_INCOMPATIBLE_ROLE")
    if any(r["status"] != "READY" or not r.get("source_known_at") or not r.get("source_end_at")
           or not r.get("state_hash") or not r.get("causal_input_hash")
           or timestamp(r["source_known_at"]) > as_of or timestamp(r["source_end_at"]) > as_of for r in refs.values()):
        return reject("UNAVAILABLE", "REQUIRED_ROLE_UNAVAILABLE_OR_FUTURE")
    trend, exhaustion, raw, m15 = (refs[r] for r in roles)
    symbol = trend["symbol"]
    if (any(r["symbol"] != symbol for r in refs.values())
            or any(r["timeframe"] != frame for r, frame in zip((trend, exhaustion, raw, m15), ("Daily", "Daily", "1H", "15m")))
            or trend["source_vintage"] != exhaustion["source_vintage"]
            or raw["source_vintage"] != m15["source_vintage"]
            or trend["price_basis"] != exhaustion["price_basis"]
            or raw["price_basis"] != m15["price_basis"]
            or trend["source_end_at"] != exhaustion["source_end_at"]
            or trend["session_profile"] != RTH or exhaustion["session_profile"] != RTH
            or raw["session_profile"] != EXTENDED or m15["session_profile"] != EXTENDED
            or trend["state_version"] != TREND.version or exhaustion["state_version"] != EXHAUSTION.version
            or raw["state_version"] != H1.version or m15["state_version"] != M15_VERSION
            or joined.get("Daily_input_status") != "READY"
            or joined.get("expected_Daily_session") != expected_daily_session(as_of)
            or timestamp(trend["source_end_at"]).astimezone(NY).date().isoformat() != joined.get("expected_Daily_session")
            or timestamp(raw["source_end_at"]) != expected_extended_end(as_of, "1H")
            or timestamp(m15["source_end_at"]) != expected_extended_end(as_of, "15m")):
        return reject("UNAVAILABLE", "STALE_OR_INCOMPATIBLE_IDENTITY")
    if type(episode) is not H1SetupEpisode or type(trigger) is not M15Memory:
        return reject("UNAVAILABLE", "LIFETIME_OR_TRIGGER_EVIDENCE_MISSING")
    if evidence is None:
        return reject("UNAVAILABLE", "POSITION_EVIDENCE_MISSING")
    if (type(evidence) is not PositionEvidence or evidence.symbol != symbol
            or timestamp(evidence.as_of) != as_of or timestamp(evidence.known_at) > as_of
            or evidence.state == "UNAVAILABLE"):
        return reject("UNAVAILABLE", "POSITION_EVIDENCE_UNAVAILABLE")
    if ((type(episode) is H1SetupEpisode and episode.status == "CANCELLED"
         and episode.cancellation_reason == "SETUP_CANCELLED_1H_UNAVAILABLE")
            or (type(trigger) is M15Memory and trigger.event == "UNAVAILABLE_CANCEL")):
        return reject("UNAVAILABLE", "CONTINUITY_OR_ORIGIN_UNAVAILABLE")
    if trend["state"] != "BULLISH":
        return reject("INELIGIBLE", "DAILY_NOT_BULLISH")
    if exhaustion["state"] != "NORMAL":
        return reject("INELIGIBLE", "EXHAUSTION_EXTENDED")
    if not active:
        return reject("INELIGIBLE", "H1_NOT_ACTIVE")
    if (episode.symbol != symbol or episode.as_of != as_of or episode.raw_ref_hash != raw["state_hash"]
            or episode.daily_refs.unpack()["trend_ref_hash"] != trend["state_hash"]
            or episode.daily_refs.unpack()["exhaustion_ref_hash"] != exhaustion["state_hash"]
            or type(trigger) is not M15Memory or trigger.observation.as_of != as_of
            or trigger.observation.identity_hash != m15["state_hash"]
            or (trigger.trigger and (trigger.observation.gc is not True or trigger.observation.price is not True))
            or trigger.scope_ref != episode_id):
        return reject("UNAVAILABLE", "BROKEN_EPISODE_OR_TRIGGER_LINK")
    if evidence.state != "FLAT":
        return reject("INELIGIBLE", "INELIGIBLE_FOR_INITIAL_ENTRY_POSITION_OPEN")
    if consumed:
        return reject("INELIGIBLE", "INITIAL_ENTRY_CONSUMED")
    if not trigger.trigger:
        return reject("INELIGIBLE", "M15_TRIGGER_FALSE")
    if old.last_end is not None and end <= old.last_end:
        return reject("INELIGIBLE", "POLL_OR_CORRECTION_NO_EVENT")
    extreme_end = (previous_trigger.arm_end if type(previous_trigger) is M15Memory
                   and previous_trigger.scope_ref == episode_id else None)
    extreme_index = (previous_trigger.arm_index if extreme_end is not None else None)
    if extreme_end is None and trigger.observation.raw == "DOWNSIDE_EXTREME":
        extreme_end, extreme_index = trigger.observation.end_at, trigger.observation.index
    if extreme_end is None or not 0 <= trigger.observation.index - extreme_index <= 4:
        return reject("UNAVAILABLE", "TRIGGER_EXTREME_PROVENANCE_MISSING")
    # Specification is a validated v13 value; full strategy remains DRAFT.
    spec = specification.unpack()
    if spec["specification_version"] != "h0001_r03_spec_v13":
        raise ValueError("Frozen minimal v13 composition specification required")
    ep_ref = {"version": EPISODE_VERSION, "episode_id": episode_id,
              "lifetime_hash": LIFETIME.hash, "setup_hash": digest(payload(episode))}
    trigger_ref = {"version": M15_VERSION, "contract_hash": m15_hash(),
                   "trigger_hash": digest({"memory": payload(trigger), "extreme_end": payload(extreme_end),
                                           "extreme_index": extreme_index}),
                   "observation_hash": m15["state_hash"], "extreme_end": payload(extreme_end),
                   "age": trigger.observation.index - extreme_index}
    dependencies = {"references": joined["references"], "episode": ep_ref,
                    "trigger": trigger_ref, "position_evidence_hash": evidence.hash,
                    "specification_hash": specification.specification_hash,
                    "composer_hash": contract_hash()}
    causal_hash = digest(dependencies)
    identity = {"symbol": symbol, "event_type": "INITIAL_ENTRY_CANDIDATE",
                "as_of": as_of.isoformat(), "completed_15m_end_at": end, **dependencies,
                "causal_input_hash": causal_hash}
    body = {"event_id": digest(identity), **identity,
            "known_at": max([r["source_known_at"] for r in refs.values()] + [evidence.known_at]),
            "Daily": {"session": joined["expected_Daily_session"], "contract_hash": TREND.hash, **trend},
            "exhaustion": {"contract_hash": EXHAUSTION.hash, **exhaustion},
            "H1": {**ep_ref, "source_end_at": raw["source_end_at"], "raw_state": raw["state"],
                   "setup": "ACTIVE", "age": episode.age_since_last_extreme,
                   "last_extreme_end": payload(episode.last_extreme_end), "raw_ref": raw},
            "M15": {**trigger_ref, "source_end_at": end, "GC": trigger.observation.gc,
                    "price_confirmation": trigger.observation.price},
            "position_evidence": {**payload(evidence), "hash": evidence.hash},
            "strategy": {"version": spec["specification_version"], "hash": specification.specification_hash},
            "composer": {"version": VERSION, "hash": contract_hash()},
            "candidate_status": "ENTRY_CANDIDATE", "reason": "ALL_FROZEN_GATES_ALLOWED",
            "candidate_is_order_fill_position": False}
    return CompositionResult("ENTRY_CANDIDATE", body["reason"],
                             Consumption(episode_id, True, memory.last_end), JsonObject.of(body))


def save_candidate_stream(path, events):
    """Small immutable research artifact; explicit ID/payload collision checks."""
    path = Path(path)
    unique = {}
    for event in events:
        body = event.unpack() if type(event) is JsonObject else event
        key = body["event_id"]
        if key in unique and unique[key] != body:
            raise ValueError("candidate identity payload collision")
        unique[key] = body
    body = {"version": VERSION, "events": list(unique.values())}
    text = canonical(body)
    if path.exists():
        if json.loads(path.read_text(encoding="utf-8")) != body:
            raise ValueError("immutable candidate stream collision")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x", encoding="utf-8") as file:
            file.write(text)
    return digest(body)
