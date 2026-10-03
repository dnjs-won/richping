"""Synthetic session-contract evidence only; no H0001 trading or chart evidence."""

from dataclasses import replace
from datetime import timedelta
from hashlib import sha256
from pathlib import Path
import subprocess

import pytest

from richping.core import sessions
from richping.research_v2.aggregation import CompletedAggregator
from richping.research_v2.contracts import JsonObject, MarketBar, ReplayContext
from richping.research_v2.features import (
    MACDSpec, macd, macd_series, EMASpec, ema, close_series,
    PercentileSpec, rolling_percentile, ATRSpec, atr, FractalSpec, confirmed_swings,
)
from richping.research_v2.features.continuity import is_contiguous, slot_bounds
from richping.research_v2.market_data import MarketDataset
from richping.research_v2.replay import replay
from richping.research_v2.sessions import (
    EXTENDED, EXTENDED_PROFILE, EXTENDED_CONTINUITY as EC,
    EXTENDED_AGGREGATION, extended_bar_metadata, session_bounds, session_date, NY,
)
from richping.research_v2.strategy.capabilities import current_engine, require_session_capability
from richping.research_v2.strategy.h0001_spec import H0001Specification, load_h0001, ENGINE_BOUNDARIES
from richping.research_v2.strategy.specification import C1, PERFORMANCE, OPTIONAL, StrategySpecification
from test_research_v2 import Observer, fixture_data
from test_research_v2_specification import (
    resolve_fixture, feature_contract, prior_decision_inventory, prior_unresolved_fields,
    input_freeze_draft,
)

ROOT = Path(__file__).resolve().parents[1]
BASE = "73b5d3d5c096c0a2612c39191e6fd4b7980d8f7a"
DRAFT = ROOT / "research/strategy_specs/H0001-r03-draft.yaml"
RESOLVED = {"H1-SESSION", "H1-BASE", "H1-EMA-SEED", "H1-MACD-HISTORY", "H1-HISTORY-ORIGIN"}


def bars(day="2024-03-11", count=64, symbols=("ALFA",), offset=0):
    opened, _ = session_bounds(day, EXTENDED)
    output = []
    for i in range(count):
        start = opened + timedelta(minutes=15 * (i + offset))
        end = start + timedelta(minutes=15)
        for symbol in symbols:
            output.append(MarketBar("extended-fixture", symbol, "15m", start, end, day,
                100 + i, 103 + i, 98 + i, 101 + i, 10 + i, end, "synthetic",
                JsonObject.of(extended_bar_metadata(start, end)), "NONE_CONFIRMED"))
    return tuple(output)


def dataset(inputs):
    meta = fixture_data(count=1).manifest.unpack()
    meta.update(session_policy="RTH_EXTENDED", session_contract=EXTENDED_PROFILE.metadata,
                symbols=sorted({b.symbol for b in inputs}),
                captured_at=max(b.known_at for b in inputs).isoformat())
    return MarketDataset("extended-fixture", inputs, JsonObject.of(meta))


def context(inputs):
    return ReplayContext(max(b.known_at for b in inputs), tuple(inputs))


@pytest.mark.parametrize("offset,valid,segment", [
    (0, True, "PREMARKET"), (-1, False, None), (63, True, "AFTER_HOURS"), (64, False, None),
    (21, True, "PREMARKET"), (22, True, "RTH"), (47, True, "RTH"), (48, True, "AFTER_HOURS"),
])
def test_base_session_bounds_and_segments(offset, valid, segment):
    inputs = bars(count=1, offset=offset)
    if not valid:
        with pytest.raises(ValueError, match="outside extended"):
            dataset(inputs)
    else:
        assert dataset(inputs).bars == inputs
        assert inputs[0].provenance.unpack()["session_segment"] == segment


def test_completed_hour_daily_and_no_regular_anchor_leak():
    inputs = bars()
    observer = Observer()
    replay(dataset(inputs), observer)
    assert all(not v.query(timeframe="1H") for v in observer.views[:3])
    first = observer.views[3].query(timeframe="1H")[0]
    second = observer.views[7].query(timeframe="1H")[1]
    assert (first.start_at, first.end_at, first.known_at) == (inputs[0].start_at, inputs[3].end_at, inputs[3].known_at)
    assert (first.open, first.high, first.low, first.close, first.volume) == (100, 106, 98, 104, 46)
    assert (second.start_at, second.end_at) == (inputs[4].start_at, inputs[7].end_at)
    assert (second.open, second.high, second.low, second.close, second.volume) == (104, 110, 102, 108, 62)
    assert len(observer.views[6].query(timeframe="1H")) == 1
    assert all(not v.query(timeframe="Daily") for v in observer.views[:-1])
    final = observer.views[-1]
    hours, daily = final.query(timeframe="1H"), final.query(timeframe="Daily")[0]
    assert len(hours) == 16
    assert [b.start_at.astimezone(NY).hour for b in hours] == list(range(4, 20))
    assert all(b.start_at.astimezone(NY).minute == 0 for b in hours)
    assert hours[5].provenance.unpack()["session_segment"] == "MIXED"  # 09:00-10:00
    assert (daily.start_at, daily.end_at) == (inputs[0].start_at, inputs[-1].end_at)
    assert (daily.open, daily.high, daily.low, daily.close, daily.volume) == (100, 166, 98, 164, 2656)
    assert daily.provenance.unpack()["input_count"] == 64
    assert daily.provenance.unpack()["aggregation"] == EXTENDED_AGGREGATION
    assert dataset(inputs).gaps == ()
    assert all(b.known_at <= v.as_of for v in observer.views for b in v.bars)


@pytest.mark.parametrize("offset", [20, 21, 22, 46, 47, 48])
def test_segment_transitions_are_contiguous(offset):
    assert is_contiguous(bars(count=3, offset=offset), "15m", EC)


@pytest.mark.parametrize("first,second,hours", [
    ("2024-03-11", "2024-03-12", 8),  # overnight
    ("2024-03-15", "2024-03-18", 56),  # weekend
    ("2024-03-08", "2024-03-11", 55),  # spring DST
    ("2024-11-01", "2024-11-04", 57),  # autumn DST
    ("2024-03-28", "2024-04-01", 80),  # Good Friday is not an observation
])
def test_calendar_discontinuities(first, second, hours):
    left, right = bars(first), bars(second)
    assert (right[0].start_at - left[-1].end_at).total_seconds() / 3600 == hours
    assert is_contiguous((left[-1], right[0]), "15m", EC)
    assert dataset(left + right).gaps == ()
    for frame in ("1H", "Daily"):
        aggregator = CompletedAggregator(profile=EXTENDED)
        outputs = [v for b in left + right for v in aggregator.accept(b, b.known_at) if v.timeframe == frame]
        assert is_contiguous(outputs, frame, EC)
        for b in outputs:
            assert slot_bounds(b.end_at, frame, EC) == (b.start_at, b.end_at)
    # Winter close is next UTC day but still the original local session.
    assert session_date(left[-1].end_at) == first


@pytest.mark.parametrize("day", ["2024-03-09", "2024-03-29", "2024-07-04"])
def test_weekend_and_holiday_bars_rejected(day):
    with pytest.raises(ValueError, match="Non-trading"):
        session_bounds(day, EXTENDED)
    b = bars(count=1)[0]
    with pytest.raises(ValueError, match="Non-trading"):
        dataset((replace(b, session=day),))


def test_early_close_is_unknown_not_an_invented_regular_day_or_skipped_holiday():
    with pytest.raises(ValueError, match="early-close"):
        session_bounds("2024-11-29", EXTENDED)
    with pytest.raises(ValueError, match="early-close"):
        dataset(bars("2024-11-27") + bars("2024-12-02"))
    assert not is_contiguous((bars("2024-11-27")[-1], bars("2024-12-02")[0]), "15m", EC)
    # The old RTH early-close contract is still available.
    rth = fixture_data(day="2024-11-29")
    assert len(rth.bars) == 14


@pytest.mark.parametrize("frame", ["15m", "1H", "Daily"])
def test_delayed_missing_premarket_input_blocks_until_repaired(frame):
    inputs = list(bars("2024-03-11") + bars("2024-03-12") + bars("2024-03-13"))
    missing = 64 + 5  # internal day, internal premarket hour
    late = inputs[-1].known_at + timedelta(minutes=1)
    inputs[missing] = replace(inputs[missing], known_at=late)
    observer = Observer()
    replay(dataset(inputs), observer)
    spec = MACDSpec(12, 26, 9, 1, continuity=EC)
    before, after = observer.views[-2:]
    assert macd(before, "ALFA", frame, spec).reason == "noncontiguous_history"
    repaired = macd(after, "ALFA", frame, spec)
    assert repaired.status == "READY"
    affected = next(b for b in after.query(timeframe=frame) if b.session == "2024-03-12"
                    and (frame == "Daily" or b.start_at <= inputs[missing].start_at < b.end_at))
    assert affected.known_at == late
    # Old detached snapshots never gain the delayed observation.
    assert macd(before, "ALFA", frame, spec).reason == "noncontiguous_history"


def test_missing_final_constituent_never_exposes_hour_or_daily():
    observer = Observer()
    replay(dataset(bars()[:-1]), observer)
    assert len(observer.views[-1].query(timeframe="1H")) == 15
    assert not observer.views[-1].query(timeframe="Daily")


def test_atomic_same_known_at_multisymbol_and_delayed_inputs():
    inputs = list(bars(count=8, symbols=("ALFA", "BETA")))
    inputs[0] = replace(inputs[0], known_at=inputs[7].known_at)
    observer = Observer()
    replay(dataset(inputs), observer)
    event = observer.events[3]
    assert len(event.base_bars) == 3
    assert {b.symbol for b in event.completed if b.timeframe == "1H"} == {"ALFA", "BETA"}
    assert all(b.known_at <= event.as_of for b in event.completed)


def test_hour_macd_updates_only_at_complete_buckets():
    observer = Observer()
    replay(dataset(bars(count=12)), observer)
    spec = MACDSpec(12, 26, 9, 1, continuity=EC)
    results = [macd(v, "ALFA", "1H", spec) for v in observer.views]
    assert all(r.status == "NOT_READY" for r in results[:3])
    assert len({(r.input_hash, r.values.text) for r in results[3:7]}) == 1
    assert results[7].input_hash != results[6].input_hash
    assert results[7].values != results[6].values


@pytest.fixture(scope="module")
def long_history():
    # No synthetic observations are invented on early-close days.
    days = sessions("2023-12-26", "2024-07-02")
    assert len(days) >= 130
    aggregator = CompletedAggregator(profile=EXTENDED)
    by_frame = {frame: [] for frame in ("15m", "1H", "Daily")}
    for day_index, day in enumerate(days[:130]):
        for original in bars(day):
            bar = replace(original, **{key: getattr(original, key) + day_index / 3 for key in ("open", "high", "low", "close")})
            for output in aggregator.accept(bar, bar.known_at):
                by_frame[output.timeframe].append(output)
    return by_frame


@pytest.mark.parametrize("frame", ["15m", "1H", "Daily"])
def test_exact_130_gate_and_deterministic_first_observation(long_history, frame):
    inputs = long_history[frame][:130]
    spec = MACDSpec(12, 26, 9, 130, continuity=EC)
    assert macd(context(inputs[:129]), "ALFA", frame, spec).reason == "insufficient_history"
    result = macd(context(inputs), "ALFA", frame, spec)
    assert result.status == "READY" and result.input_count == 130
    # Independent scalar recurrence, carried across every session boundary.
    fast = slow = inputs[0].close
    signal = 0.0
    for b in inputs[1:]:
        fast += (2 / 13) * (b.close - fast)
        slow += (2 / 27) * (b.close - slow)
        signal += (2 / 10) * ((fast - slow) - signal)
    assert result.values.unpack() == pytest.approx({"macd_line": fast - slow,
        "signal_line": signal, "histogram": fast - slow - signal}, abs=1e-12)
    assert macd(context(inputs), "ALFA", frame, spec).hash == result.hash
    series = macd_series(context(inputs), "ALFA", frame, spec, field="macd_line")
    assert [p.status for p in series.points] == ["NOT_READY"] * 129 + ["READY"]
    assert series.contiguous


def test_no_per_session_ema_reset(long_history):
    inputs = long_history["15m"][:65]
    spec = MACDSpec(12, 26, 9, 1, continuity=EC)
    complete = macd(context(inputs), "ALFA", "15m", spec)
    reset = macd(context(inputs[-1:]), "ALFA", "15m", spec)
    assert complete.values != reset.values
    assert reset.values.unpack() == {"macd_line": 0, "signal_line": 0, "histogram": 0}
    assert ema(context(inputs), "ALFA", "15m", EMASpec(26, 1, continuity=EC)).values.unpack()["ema"] != inputs[-1].close


def test_history_is_not_truncated_to_warmup_count(long_history):
    inputs = long_history["15m"][:200]
    spec = MACDSpec(12, 26, 9, 130, continuity=EC)
    full = macd(context(inputs), "ALFA", "15m", spec)
    truncated = macd(context(inputs[-130:]), "ALFA", "15m", spec)
    assert full.input_count == 200
    assert full.values != truncated.values


def test_missing_trading_session_is_not_a_calendar_gap():
    inputs = bars("2024-03-11") + bars("2024-03-13")
    assert len(dataset(inputs).gaps) == 64
    assert not is_contiguous(inputs, "15m", EC)
    assert macd(context(inputs), "ALFA", "15m", MACDSpec(12, 26, 9, 1, continuity=EC)).reason == "noncontiguous_history"


@pytest.mark.parametrize("cutoff", [22, 23, 48, 49])
def test_prefix_invariance_at_premarket_regular_after_hours_boundaries(cutoff):
    original = bars()
    altered = tuple(b if i < cutoff else replace(b, close=800, high=900) for i, b in enumerate(original))
    full, changed, truncated = Observer(), Observer(), Observer()
    replay(dataset(original), full)
    replay(dataset(altered), changed)
    replay(dataset(original[:cutoff]), truncated)
    assert full.views[:cutoff] == changed.views[:cutoff] == truncated.views
    assert [t.completed for t in full.events[:cutoff]] == [t.completed for t in truncated.events]
    for frame in ("15m", "1H", "Daily"):
        spec = MACDSpec(12, 26, 9, 1, continuity=EC)
        assert macd(full.views[cutoff - 1], "ALFA", frame, spec) == macd(truncated.views[-1], "ALFA", frame, spec)


def test_generic_feature_contracts_accept_only_matching_session_profiles():
    view = context(bars(count=8))
    scalar = close_series(view, "ALFA", "15m", continuity=EC)
    assert scalar.contiguous
    assert rolling_percentile(scalar, PercentileSpec(4, 4, continuity=EC)).status == "READY"
    assert atr(view, "ALFA", "15m", ATRSpec(3, 3, continuity=EC)).status == "READY"
    assert confirmed_swings(view, "ALFA", "15m", FractalSpec(1, 1, continuity=EC)).status == "READY"
    with pytest.raises(ValueError, match="continuity mismatch"):
        macd(view, "ALFA", "15m", MACDSpec(12, 26, 9, 1))
    with pytest.raises(ValueError, match="continuity mismatch"):
        rolling_percentile(scalar, PercentileSpec(4, 4))
    with pytest.raises(ValueError, match="Mixed session"):
        context(bars(count=1) + fixture_data(count=1).bars)
    with pytest.raises(ValueError, match="profile mismatch"):
        CompletedAggregator().accept(bars(count=1)[0], bars(count=1)[0].known_at)


def test_extended_manifest_and_bar_metadata_cannot_be_silently_omitted_or_forged():
    data = dataset(bars(count=1))
    meta = data.manifest.unpack()
    meta.pop("session_contract")
    with pytest.raises(ValueError, match="Explicit extended"):
        replace(data, manifest=JsonObject.of(meta))
    b = data.bars[0]
    with pytest.raises(ValueError, match="Mixed session"):
        dataset((replace(b, provenance=JsonObject()),))
    bad = {**b.provenance.unpack(), "session_segment": "RTH"}
    with pytest.raises(ValueError, match="metadata mismatch"):
        dataset((replace(b, provenance=JsonObject.of(bad)),))


def test_eight_decisions_resolved_source_bytes_untouched():
    spec = input_freeze_draft()  # Historical eight-decision audit at v7.
    before = StrategySpecification.loads(subprocess.check_output([
        "git", "show", BASE + ":research/strategy_specs/H0001-r03-draft.yaml"], cwd=ROOT).decode())
    old, new = before.unpack(), spec.unpack()
    assert prior_decision_inventory(old) == prior_decision_inventory(new)
    assert prior_unresolved_fields(spec) == {p: info for p, info in before.unresolved_fields.items()
                                      if info["decision_id"] not in RESOLVED}
    assert len(spec.unresolved_fields) == 97
    assert [len(spec.blockers(c)) for c in (C1, PERFORMANCE, OPTIONAL)] == [46, 17, 7]
    assert old["state_machine"] == new["state_machine"]
    for section in ("rule_parameters", "state_machine_parameters", "execution_requirements",
                    "research_requirements", "optional_extensions"):
        assert old[section] == new[section]
    for key, record in old["chart_parity"].items():
        if key != "engine_1h_boundary":
            assert new["chart_parity"][key] == record
    assert new["status"] == "DRAFT"
    assert new["specification_version"] == "h0001_r03_spec_v7"
    assert spec.specification_hash != before.specification_hash
    raw = subprocess.check_output(["git", "show", BASE + ":research/hypotheses/H0001-r03.yaml"], cwd=ROOT)
    local = (ROOT / "research/hypotheses/H0001-r03.yaml").read_bytes()
    # Git may check out CRLF; compare both exact local bytes and Git blob bytes.
    assert local.replace(b"\r\n", b"\n") == raw.replace(b"\r\n", b"\n")
    assert sha256(local).hexdigest() in {"abdd4f10d127ee7614a4eead734d1bfbf7dc1897ec368f8a3b70a1645e2552fc",
                                       "35e13276056a36d6a06de04611720fd286113f0e5db1e4255af6ceeb6a0f0bc2"}
    assert not (ROOT / "research/hypotheses/H0001-r04.yaml").exists()


def select_extended_fixture(value):
    """Fake admission fixture only; no additional choices persisted to H0001."""
    value["timeframe_contracts"]["session_policy"]["value"] = "RTH_EXTENDED"
    for key, v in current_engine(EXTENDED).items():
        value["engine_capabilities"][key]["value"] = v
    value["chart_parity"]["engine_1h_boundary"]["value"] = ENGINE_BOUNDARIES[EXTENDED]
    for prefix in ("setup_1h", "entry_15m", "exit_1h"):
        if ((prefix == "setup_1h" and value["specification_version"] in {"h0001_r03_spec_v11", "h0001_r03_spec_v12"})
                or (prefix == "entry_15m" and value["specification_version"] == "h0001_r03_spec_v12")):
            continue  # Preserve the frozen setup; only fill downstream fixtures.
        value["feature_contracts"][prefix + "_relative_conventions"]["value"] = feature_contract(
            PercentileSpec(1, 1, continuity=EC), field="macd_line")
    value["rule_parameters"]["swing_parameters"]["value"] = feature_contract(FractalSpec(1, 1, continuity=EC))
    return value


def test_extended_admission_is_explicit_and_draft_still_blocked():
    spec = load_h0001(DRAFT)
    require_session_capability(spec.unpack())
    with pytest.raises(ValueError, match="FROZEN"):
        spec.require_c1_ready()
    # Resolve other decisions only in an ephemeral test fixture to reach the gate.
    value = resolve_fixture(spec, {C1})
    value["status"] = "FROZEN"
    value["timeframe_contracts"]["session_policy"]["value"] = "RTH_EXTENDED"
    with pytest.raises(ValueError, match="session policy"):
        H0001Specification.of(value).require_c1_ready()
    select_extended_fixture(value)
    H0001Specification.of(value).require_c1_ready()
    value["engine_capabilities"]["aggregation"]["value"] = current_engine()["aggregation"]
    with pytest.raises(ValueError, match="capability/version mismatch"):
        H0001Specification.of(value).require_c1_ready()


@pytest.mark.parametrize("field", list(current_engine(EXTENDED)))
def test_extended_admission_rejects_stale_capability_versions(field):
    value = select_extended_fixture(resolve_fixture(load_h0001(DRAFT), {C1}))
    value["status"] = "FROZEN"
    value["engine_capabilities"][field]["value"] = "1H" if field == "base_timeframe" else "stale_v0"
    with pytest.raises(ValueError, match="capability/version mismatch"):
        H0001Specification.of(value).require_c1_ready()


def test_extended_admission_rejects_rth_feature_continuity():
    value = select_extended_fixture(resolve_fixture(load_h0001(DRAFT), {C1}))
    value["status"] = "FROZEN"
    value["rule_parameters"]["swing_parameters"]["value"] = feature_contract(FractalSpec(1, 1))
    with pytest.raises(ValueError, match="session continuity mismatch"):
        H0001Specification.of(value).require_c1_ready()


def test_rth_and_extended_daily_semantics_are_distinct():
    extended, regular = Observer(), Observer()
    replay(dataset(bars()), extended)
    replay(fixture_data(), regular)
    e = extended.views[-1].query(timeframe="Daily")[0]
    r = regular.views[-1].query(timeframe="Daily")[0]
    assert (e.start_at, e.end_at) != (r.start_at, r.end_at)
    assert e.provenance.unpack()["aggregation"] != r.provenance.unpack()["aggregation"]
    with pytest.raises(ValueError, match="continuity mismatch"):
        macd(context((r,)), "ALFA", "Daily", MACDSpec(12, 26, 9, 1, continuity=EC))
