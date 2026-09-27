"""Hand arithmetic and causal invariants; synthetic fixtures, no performance claims."""

from dataclasses import FrozenInstanceError, replace
from datetime import timedelta

import pytest

from richping.core import digest
from richping.research_v2.contracts import Decision, JsonObject, ReplayContext, StrategyState, payload
from richping.research_v2.features import EMASpec, MACDSpec, ema, macd, macd_series
from richping.research_v2.features import (
    ATRSpec, TRSpec, FractalSpec, NormalizeSpec, PercentileSpec, ZScoreSpec,
    ScalarPoint, ScalarSeries, atr, true_range, close_series, normalize,
    rolling_percentile, rolling_zscore, confirmed_swings, classify_swings,
)
from richping.research_v2.replay import code_provenance, replay
from richping.research_v2.store import ResearchStore, TABLES
from test_research_v2 import Observer, fixture_data


def price_data(prices, **kwargs):
    data = fixture_data(count=len(prices), **kwargs)
    return fixture_data(bars=[replace(b, open=p, high=p, low=p, close=p)
                              for b, p in zip(data.bars, prices)])


def context(data):
    return ReplayContext(max(b.known_at for b in data.bars), data.bars)


def values(result):
    assert result.status == "READY" and result.reason is None
    return result.values.unpack()


def test_ema_first_observation_seed_hand_fixture_and_gate():
    observer = Observer()
    replay(price_data([2, 4, 8, 6]), observer)
    spec = EMASpec(span=3, min_history=1)
    assert [values(ema(c, "ALFA", "15m", spec))["ema"] for c in observer.views] == [2, 3, 5.5, 5.75]
    gated = EMASpec(span=3, min_history=3)
    for c in observer.views[:2]:
        r = ema(c, "ALFA", "15m", gated)
        assert (r.status, r.reason, r.values.unpack()) == ("NOT_READY", "insufficient_history", {})
    assert values(ema(observer.views[2], "ALFA", "15m", gated))["ema"] == 5.5
    assert spec.definition.parameters.unpack()["seed"] == "first_observation"
    assert spec.hash != gated.hash


def test_macd_hand_line_signal_histogram_and_warmup():
    observer = Observer()
    replay(price_data([2, 4, 8]), observer)
    # fast span 1 => [2,4,8]; slow span 3 => [2,3,5.5]
    # MACD [0,1,2.5]; signal span 3 => [0,.5,1.5]; hist [0,.5,1]
    spec = MACDSpec(1, 3, 3, min_history=1)
    assert [values(macd(c, "ALFA", "15m", spec)) for c in observer.views] == [
        {"macd_line": 0, "signal_line": 0, "histogram": 0},
        {"macd_line": 1, "signal_line": .5, "histogram": .5},
        {"macd_line": 2.5, "signal_line": 1.5, "histogram": 1}]
    gated = replace(spec, min_history=3)
    assert macd(observer.views[1], "ALFA", "15m", gated).status == "NOT_READY"
    assert values(macd(observer.views[2], "ALFA", "15m", gated))["signal_line"] == 1.5
    assert macd_series(observer.views[-1], "ALFA", "15m", gated, field="macd_line").points[0].value is None
    assert MACDSpec(12, 26, 9, 35).definition.parameters.unpack()["slow"] == 26


def hundred_bars():
    bars = []
    for day in ("2024-03-11", "2024-03-12", "2024-03-13", "2024-03-14"):
        bars.extend(fixture_data(day).bars)
    return fixture_data(bars=[replace(b, open=100 + i % 7, high=102 + i % 7,
                                     low=98 + i % 7, close=101 + i % 7)
                              for i, b in enumerate(bars[:100])])


def test_hundred_bar_prefix_invariance_macd():
    data = hundred_bars()
    altered = fixture_data(bars=[b if i < 50 else replace(b, open=1e8, high=1e9, low=1, close=1e8)
                                 for i, b in enumerate(data.bars)])
    first, second = Observer(), Observer()
    replay(data, first)
    replay(altered, second)
    spec = MACDSpec(12, 26, 9, 35)
    for a, b in zip(first.views[:50], second.views[:50]):
        assert macd(a, "ALFA", "15m", spec) == macd(b, "ALFA", "15m", spec)
    assert first.views[49].bars == second.views[49].bars
    old = macd(first.views[49], "ALFA", "15m", spec)
    macd(first.views[-1], "ALFA", "15m", spec)
    assert old == macd(first.views[49], "ALFA", "15m", spec)


def test_independent_timeframes_and_incomplete_hour():
    observer = Observer()
    replay(fixture_data(count=12), observer)
    spec = MACDSpec(1, 3, 3, 1)
    assert macd(observer.views[2], "ALFA", "1H", spec).status == "NOT_READY"
    hour = macd(observer.views[7], "ALFA", "1H", spec)
    later = macd(observer.views[10], "ALFA", "1H", spec)
    assert hour.values == later.values and hour.input_hash == later.input_hash
    assert hour.input_end_at == later.input_end_at and hour.input_count == 2
    assert macd(observer.views[7], "ALFA", "15m", spec).values != hour.values
    assert macd(observer.views[10], "ALFA", "15m", spec).input_count == 11


def test_feature_contract_immutable_provenance_and_parameters():
    c = context(price_data([2, 4, 8]))
    spec = EMASpec(3, 1)
    r = ema(c, "ALFA", "15m", spec)
    assert r.specification_hash == spec.hash
    assert r.input_count == 3 and r.input_end_at == c.bars[-1].end_at and r.as_of == c.as_of
    assert r.hash == digest(payload(r))
    assert ema(c, "ALFA", "15m", EMASpec(4, 1)).hash != r.hash
    with pytest.raises(FrozenInstanceError):
        spec.span = 5
    with pytest.raises(FrozenInstanceError):
        r.status = "UNDEFINED"
    copy = r.values.unpack()
    copy["ema"] = 99
    assert values(r)["ema"] == 5.5
    with pytest.raises(ValueError, match="ReplayContext"):
        ema(price_data([2]), "ALFA", "15m", spec)


@pytest.mark.parametrize("make", [lambda: EMASpec(0, 1), lambda: EMASpec(True, 1),
    lambda: EMASpec(2, 0), lambda: EMASpec(2, 1, seed="sma"),
    lambda: MACDSpec(3, 3, 1, 1), lambda: MACDSpec(1, 3, 0, 1)])
def test_invalid_moving_specs(make):
    with pytest.raises(ValueError):
        make()


def test_true_range_and_wilder_atr_hand_calculation():
    data = price_data([10, 12, 9, 13])
    bars = [replace(b, high=h, low=l) for b, h, l in zip(data.bars, [11, 13, 10, 14], [9, 11, 8, 12])]
    observer = Observer()
    replay(fixture_data(bars=bars), observer)
    # TR: 2; max(2,3,1)=3; max(2,2,4)=4; max(2,5,3)=5.
    assert [values(true_range(c, "ALFA", "15m", TRSpec()))["true_range"] for c in observer.views] == [2, 3, 4, 5]
    spec = ATRSpec(3, 3)
    assert atr(observer.views[1], "ALFA", "15m", spec).status == "NOT_READY"
    assert values(atr(observer.views[2], "ALFA", "15m", spec))["atr"] == 3
    assert values(atr(observer.views[3], "ALFA", "15m", spec))["atr"] == pytest.approx(11 / 3)
    assert atr(observer.views[2], "ALFA", "15m", ATRSpec(3, 4)).status == "NOT_READY"
    assert values(atr(context(price_data([5, 5, 5])), "ALFA", "15m", spec))["atr"] == 0


def scalar(prices):
    return close_series(context(price_data(prices)), "ALFA", "15m")


def test_percentile_hand_window_ties_and_range():
    spec = PercentileSpec(4, 4)
    # Current 2: one strictly smaller, two equals => (1 + .5*2)/4 = .5.
    assert values(rolling_percentile(scalar([1, 2, 3, 2]), spec))["percentile"] == .5
    assert values(rolling_percentile(scalar([2, 2, 2, 2]), spec))["percentile"] == .5
    assert values(rolling_percentile(scalar([1, 2, 3, 4]), spec))["percentile"] == .875
    assert values(rolling_percentile(scalar([4, 3, 2, 1]), spec))["percentile"] == .125
    assert rolling_percentile(scalar([1, 2, 3]), spec).status == "NOT_READY"
    dropped = rolling_percentile(scalar([99999, 1, 2, 3, 2]), spec)
    assert values(dropped)["percentile"] == .5 and dropped.input_count == 4
    assert values(rolling_percentile(scalar([.001, 1, 2, 3, 2]), spec)) == values(dropped)


def test_zscore_hand_population_sample_and_zero_variance():
    series = scalar([1, 2, 3])
    # mean=2, squared deviations sum=2.
    assert values(rolling_zscore(series, ZScoreSpec(3, 3, 0)))["zscore"] == pytest.approx((3 / 2) ** .5)
    assert values(rolling_zscore(series, ZScoreSpec(3, 3, 1)))["zscore"] == 1
    zero = rolling_zscore(scalar([2, 2, 2]), ZScoreSpec(3, 3, 0))
    assert (zero.status, zero.reason, zero.values.unpack()) == ("UNDEFINED", "zero_variance", {})
    assert rolling_zscore(scalar([1, 2]), ZScoreSpec(3, 3, 0)).status == "NOT_READY"
    assert values(rolling_zscore(scalar([1000, 1, 2, 3]), ZScoreSpec(3, 3, 1)))["zscore"] == 1


def test_scalar_warmup_slots_not_silently_skipped_and_future_rejected():
    series = scalar([1, 2, 3])
    points = (replace(series.points[0], value=None, status="NOT_READY", reason="warmup"), *series.points[1:])
    unavailable = replace(series, points=points)
    assert rolling_percentile(unavailable, PercentileSpec(3, 2)).status == "NOT_READY"
    assert rolling_zscore(unavailable, ZScoreSpec(3, 2, 0)).status == "NOT_READY"
    assert rolling_percentile(unavailable, PercentileSpec(2, 2)).status == "READY"
    undefined = replace(unavailable, points=(replace(points[0], status="UNDEFINED", reason="zero_variance"), *points[1:]))
    assert rolling_percentile(undefined, PercentileSpec(3, 2)).status == "UNDEFINED"
    with pytest.raises(ValueError, match="Future"):
        replace(series, as_of=series.points[0].known_at)
    with pytest.raises(ValueError, match="strictly increase"):
        replace(series, points=tuple(reversed(series.points)))
    with pytest.raises(ValueError, match="Finite"):
        replace(series.points[0], value=float("inf"))


def test_normalization_hand_positive_zero_unavailable_and_alignment():
    c = context(price_data([2, 4, 8]))
    m = macd(c, "ALFA", "15m", MACDSpec(1, 3, 3, 1))
    a = atr(c, "ALFA", "15m", ATRSpec(3, 3))  # TR [0,2,4] => ATR 2
    spec = NormalizeSpec("macd_line", "atr")
    r = normalize(m, a, spec)
    assert values(r)["normalized"] == 1.25
    assert r.input_count == 2
    c0 = context(price_data([5, 5, 5]))
    zero = atr(c0, "ALFA", "15m", ATRSpec(3, 3))
    assert normalize(m, zero, spec).reason == "nonpositive_scale"
    missing = atr(c, "ALFA", "15m", ATRSpec(4, 4))
    assert normalize(m, missing, spec).status == "NOT_READY"
    undefined = replace(a, values=JsonObject(), status="UNDEFINED", reason="fixture")
    assert normalize(m, undefined, spec).status == "UNDEFINED"
    negative = replace(a, values=JsonObject.of({"atr": -2}))
    assert normalize(m, negative, spec).reason == "nonpositive_scale"
    for changed in (replace(a, as_of=a.as_of + timedelta(minutes=1)), replace(a, symbol="BETA"),
                    replace(a, input_end_at=c.bars[0].end_at), replace(a, timeframe="1H")):
        with pytest.raises(ValueError, match="Unaligned"):
            normalize(m, changed, spec)
    with pytest.raises(ValueError, match="numeric"):
        normalize(m, a, NormalizeSpec("unknown", "atr"))


def events(r):
    return values(r)["events"] if r.status == "READY" else []


def test_pivot_confirmation_right_bars_and_no_backdating():
    observer = Observer()
    replay(price_data([1, 4, 3, 2, 1]), observer)
    spec = FractalSpec(left=1, right=2)
    assert events(confirmed_swings(observer.views[1], "ALFA", "15m", spec)) == []
    assert events(confirmed_swings(observer.views[2], "ALFA", "15m", spec)) == []
    swings = confirmed_swings(observer.views[3], "ALFA", "15m", spec)
    high, = events(swings)
    assert high["kind"] == "SWING_HIGH_CONFIRMED" and high["pivot_price"] == 4
    assert high["pivot_at"] == observer.views[1].as_of.isoformat()
    assert high["confirmed_at"] == observer.views[3].as_of.isoformat()
    assert high["specification_hash"] == spec.hash
    assert high in events(confirmed_swings(observer.views[-1], "ALFA", "15m", spec))


def test_structure_confirmed_high_low_classification_hand_fixture():
    # Confirmed highs 5,6,4,4 => initial,HH,LH,EQH.
    # Confirmed lows 2,3,1,1 => initial,HL,LL,EQL.
    c = context(price_data([3, 5, 2, 6, 3, 4, 1, 4, 1, 3]))
    classified = events(classify_swings(confirmed_swings(c, "ALFA", "15m", FractalSpec(1, 1))))
    assert [e["classification"] for e in classified if e["kind"] == "SWING_HIGH_CONFIRMED"] == [None, "HH", "LH", "EQH"]
    assert [e["classification"] for e in classified if e["kind"] == "SWING_LOW_CONFIRMED"] == [None, "HL", "LL", "EQL"]


@pytest.mark.parametrize("prices", [[1, 3, 3, 1], [3, 1, 1, 3], [2, 2, 2, 2]])
def test_equal_neighbor_ties_reject_plateau_pivots(prices):
    assert events(confirmed_swings(context(price_data(prices)), "ALFA", "15m", FractalSpec(1, 1))) == []


def test_delayed_missing_right_bar_cannot_confirm_or_revise_prior_events():
    data = price_data([1, 5, 3, 2, 4, 1, 3])
    bars = list(data.bars)
    bars[2] = replace(bars[2], known_at=bars[5].known_at)
    observer = Observer()
    replay(fixture_data(bars=bars), observer)
    spec = FractalSpec(1, 1)
    prior = []
    for c in observer.views:
        current = events(confirmed_swings(c, "ALFA", "15m", spec))
        assert all(e in current for e in prior)
        if c.as_of < bars[2].known_at:
            assert not any(e["pivot_at"] == bars[1].end_at.isoformat() for e in current)
        prior = current
    high = next(e for e in prior if e["pivot_at"] == bars[1].end_at.isoformat())
    assert high["confirmed_at"] == bars[2].known_at.isoformat()
    with pytest.raises(ValueError, match="Future"):
        ReplayContext(bars[1].known_at, tuple(bars[:3]))


def test_incomplete_hour_cannot_confirm_swing():
    observer = Observer()
    replay(price_data([1] * 4 + [4] * 4 + [2] * 4), observer)
    spec = FractalSpec(1, 1)
    for c in observer.views[:11]:
        assert events(confirmed_swings(c, "ALFA", "1H", spec)) == []
    high, = events(confirmed_swings(observer.views[11], "ALFA", "1H", spec))
    assert high["pivot_at"] == observer.views[7].as_of.isoformat()
    assert high["confirmed_at"] == observer.views[11].as_of.isoformat()


def test_hundred_bar_all_feature_prefix_invariance_and_confirmed_event_stability():
    data = hundred_bars()
    altered = fixture_data(bars=[b if i < 50 else replace(b, open=1e8, high=1e9, low=1, close=1e8)
                                 for i, b in enumerate(data.bars)])
    first, second = Observer(), Observer()
    replay(data, first)
    replay(altered, second)
    def features(c):
        m = MACDSpec(12, 26, 9, 26)
        series = macd_series(c, "ALFA", "15m", m, field="macd_line")
        swing = confirmed_swings(c, "ALFA", "15m", FractalSpec(2, 2))
        return (ema(c, "ALFA", "15m", EMASpec(12, 12)), macd(c, "ALFA", "15m", m),
                atr(c, "ALFA", "15m", ATRSpec(14, 14)),
                rolling_percentile(series, PercentileSpec(10, 5)),
                rolling_zscore(series, ZScoreSpec(10, 5, 1)), swing, classify_swings(swing))
    for a, b in zip(first.views[:50], second.views[:50]):
        assert features(a) == features(b)
    old_events = events(features(first.views[49])[-2])
    assert old_events  # Fixture really exercises confirmed events.
    assert all(e in events(features(second.views[-1])[-2]) for e in old_events)


def test_atomic_multi_symbol_features_input_order_and_ticker_relabeling():
    data = fixture_data(count=8, symbols=("ALFA", "BETA"))
    bars = [replace(b, open=b.open + 10, high=b.high + 10, low=b.low + 10, close=b.close + 10)
            if b.symbol == "BETA" else b for b in data.bars]
    first, second, third = Observer(), Observer(), Observer()
    replay(fixture_data(bars=bars), first)
    reversed_ties = [b for i in range(0, len(bars), 2) for b in reversed(bars[i:i + 2])]
    replay(fixture_data(bars=reversed_ties), second)
    rename = {"ALFA": "ZETA", "BETA": "ABLE"}
    replay(fixture_data(bars=[replace(b, symbol=rename[b.symbol]) for b in bars]), third)
    for index, (a, b, c) in enumerate(zip(first.views, second.views, third.views), 1):
        for symbol in rename:
            for tf in ("15m", "1H"):
                spec = MACDSpec(1, 3, 3, 1)
                left = macd(a, symbol, tf, spec)
                assert left == macd(b, symbol, tf, spec)
                renamed = macd(c, rename[symbol], tf, spec)
                assert (left.values, left.status, left.input_count, left.as_of) == (
                    renamed.values, renamed.status, renamed.input_count, renamed.as_of)
                assert left.input_count == (index if tf == "15m" else index // 4)


def test_delayed_bar_not_in_features_before_arrival_and_scalar_known_at():
    data = price_data([100, 2, 3, 4, 5])
    bars = list(data.bars)
    bars[0] = replace(bars[0], known_at=bars[3].known_at)
    observer = Observer()
    replay(fixture_data(bars=bars), observer)
    spec = EMASpec(3, 1)
    assert [values(ema(c, "ALFA", "15m", spec))["ema"] for c in observer.views[:2]] == [2, 2.5]
    assert values(ema(observer.views[2], "ALFA", "15m", spec))["ema"] == 15.5
    series = macd_series(observer.views[2], "ALFA", "15m", MACDSpec(1, 3, 3, 1), field="histogram")
    assert all(p.known_at == bars[0].known_at for p in series.points)
    assert all(p.known_at <= series.as_of for p in series.points)


@pytest.mark.parametrize("make", [lambda: ATRSpec(3, 2), lambda: ATRSpec(3, 3, smoothing="sma"),
    lambda: TRSpec("zero"), lambda: PercentileSpec(3, 4), lambda: PercentileSpec(3, 2, ties="min"),
    lambda: ZScoreSpec(3, 1, 1), lambda: ZScoreSpec(3, 2, 2),
    lambda: FractalSpec(1, 0), lambda: FractalSpec(1, 1, ties="equal"),
    lambda: NormalizeSpec("x", "y", denominator_policy="allow_zero")])
def test_invalid_remaining_specs(make):
    with pytest.raises(ValueError):
        make()


class FeatureRecorder(Observer):
    """Persist generic feature snapshots through the existing V2-A evidence path."""

    def __init__(self, span=3):
        super().__init__()
        self.spec = EMASpec(span, 1)
        self.specification = JsonObject.of({"purpose": "feature-fixture", "ema": payload(self.spec.definition)})

    def on_event(self, context, state, event):
        self.views.append(context)
        results = [payload(ema(context, s, "15m", self.spec)) for s in ("ALFA", "BETA")]
        return Decision(StrategyState("feature-fixture-v1", JsonObject.of({"features": results})))


def test_feature_evidence_deterministic_isolated_store_and_spec_changes(tmp_path):
    data = fixture_data(count=4, symbols=("ALFA", "BETA"))
    with ResearchStore(tmp_path / "features.sqlite") as store:
        a = replay(data, FeatureRecorder(), store=store)
        counts = {t: store.db.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in TABLES}
        b = replay(fixture_data(count=4, symbols=("BETA", "ALFA")), FeatureRecorder(), store=store)
        assert a == b and a.hash == b.hash
        assert counts == {t: store.db.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in TABLES}
        assert store.load_checkpoint(a.run_id, 3).state == a.traces[-1].decision.state
        other = replay(data, FeatureRecorder(4), store=store)
        assert other.run_id != a.run_id
        first = a.traces[0].decision.state.data.unpack()["features"]
        assert [r["input_count"] for r in first] == [1, 1]


def test_recursive_code_provenance_covers_every_feature_source(monkeypatch):
    from pathlib import Path
    import richping.research_v2.features as package
    files = tuple(Path(package.__file__).parent.glob("*.py"))
    baseline = code_provenance(FeatureRecorder())["engine_hash"]
    original = Path.read_text
    for feature_file in files:
        with monkeypatch.context() as patch:
            def changed(path, *args, **kwargs):
                content = original(path, *args, **kwargs)
                return content + "\n# provenance probe\n" if path == feature_file else content
            patch.setattr(Path, "read_text", changed)
            assert code_provenance(FeatureRecorder())["engine_hash"] != baseline


def test_feature_package_has_no_data_store_loader_or_strategy_imports():
    import ast
    from pathlib import Path
    import richping.research_v2.features as package
    forbidden = {"market_data", "store", "replay", "aggregation", "engine", "paper", "data"}
    for path in Path(package.__file__).parent.glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                assert "h0001" not in ast.unparse(node).lower()
                if isinstance(node, ast.ImportFrom):
                    assert node.module.split(".")[-1] not in forbidden


@pytest.mark.parametrize("first,second", [
    (EMASpec(3, 1), EMASpec(4, 1)), (MACDSpec(1, 3, 3, 1), MACDSpec(1, 3, 4, 1)),
    (ATRSpec(3, 3), ATRSpec(3, 4)), (PercentileSpec(3, 2), PercentileSpec(4, 2)),
    (ZScoreSpec(3, 2, 0), ZScoreSpec(3, 2, 1)), (FractalSpec(1, 1), FractalSpec(1, 2)),
    (NormalizeSpec("x", "y"), NormalizeSpec("z", "y"))])
def test_every_feature_spec_tracks_math_parameters(first, second):
    assert first.hash != second.hash
    assert first.definition.version and first.definition.name


def test_transform_provenance_contains_source_spec_and_changed_method():
    c = context(price_data([2, 4, 8, 5]))
    a = macd_series(c, "ALFA", "15m", MACDSpec(1, 3, 3, 1), field="macd_line")
    b = macd_series(c, "ALFA", "15m", MACDSpec(1, 4, 3, 1), field="macd_line")
    pa = rolling_percentile(a, PercentileSpec(3, 3))
    pb = rolling_percentile(b, PercentileSpec(3, 3))
    assert pa.specification_hash != pb.specification_hash
    assert pa.specification.parameters.unpack()["source"] == payload(a.source)
    assert rolling_zscore(a, ZScoreSpec(3, 3, 0)).specification_hash != pa.specification_hash


def test_undefined_extreme_arithmetic_and_empty_inputs_fail_closed():
    huge = scalar([1, 2, 3])
    huge = replace(huge, points=tuple(replace(p, value=v) for p, v in zip(huge.points, [-1e308, 0, 1e308])))
    r = rolling_zscore(huge, ZScoreSpec(3, 3, 0))
    assert r.status == "UNDEFINED" and r.reason == "nonfinite_result"
    c = ReplayContext(context(price_data([1])).as_of)
    m = macd(c, "ALFA", "15m", MACDSpec(1, 3, 3, 1))
    a = atr(c, "ALFA", "15m", ATRSpec(3, 3))
    assert normalize(m, a, NormalizeSpec("macd_line", "atr")).status == "NOT_READY"
    assert true_range(c, "ALFA", "15m", TRSpec()).status == "NOT_READY"
    assert classify_swings(confirmed_swings(c, "ALFA", "15m", FractalSpec(1, 1))).status == "NOT_READY"


def test_structure_session_gap_does_not_create_false_neighbor_confirmation():
    monday = price_data([1, 5, 2])
    # Remove right neighbor; a later session cannot stand in for missing Monday slots.
    tuesday = fixture_data("2024-03-12", count=1)
    data = fixture_data(bars=[*monday.bars[:2], *tuesday.bars])
    r = confirmed_swings(context(data), "ALFA", "15m", FractalSpec(1, 1))
    assert r.status == "NOT_READY" and r.reason == "insufficient_contiguous_history"


def test_structure_across_session_boundary_and_daily_completed_bars():
    bars = []
    for day, price in zip(("2024-03-08", "2024-03-11", "2024-03-12"), (2, 5, 3)):
        bars.extend(replace(b, open=price, high=price, low=price, close=price)
                    for b in fixture_data(day).bars)
    observer = Observer()
    replay(fixture_data(bars=bars), observer)
    spec = FractalSpec(1, 1)
    assert confirmed_swings(observer.views[-2], "ALFA", "Daily", spec).status == "NOT_READY"
    e, = events(confirmed_swings(observer.views[-1], "ALFA", "Daily", spec))
    assert e["pivot_price"] == 5
    assert e["confirmed_at"] == observer.views[-1].as_of.isoformat()
