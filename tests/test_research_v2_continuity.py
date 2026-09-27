"""Calendar-gap audit regressions; synthetic inputs, no strategy claims."""

from dataclasses import FrozenInstanceError, replace
from datetime import timedelta

import pytest

from richping.core import canonical
from richping.research_v2.contracts import ReplayContext, payload
from richping.research_v2.features import (
    ATRSpec, EMASpec, MACDSpec, TRSpec, PercentileSpec, ZScoreSpec,
    atr, ema, macd, macd_series, true_range, close_series,
    rolling_percentile, rolling_zscore,
)
from richping.research_v2.features.continuity import is_contiguous
from richping.research_v2.replay import replay
from test_research_v2 import Observer, fixture_data


def views(bars):
    observer = Observer()
    replay(fixture_data(bars=bars), observer)
    return observer.views


def session_bars(days):
    # Vary daily closes so recovered z-score tests exercise nonzero variance.
    return tuple(replace(b, open=b.open + 30 * i, high=b.high + 30 * i,
                         low=b.low + 30 * i, close=b.close + 30 * i)
                 for i, day in enumerate(days) for b in fixture_data(day).bars)


def recursive_features(context, timeframe):
    return (
        ema(context, "ALFA", timeframe, EMASpec(3, 1)),
        macd(context, "ALFA", timeframe, MACDSpec(1, 3, 3, 1)),
        atr(context, "ALFA", timeframe, ATRSpec(2, 2)),
    )


def assert_gap(result):
    assert (result.status, result.reason, result.values.unpack()) == (
        "NOT_READY", "noncontiguous_history", {})


def gap_fixture(timeframe):
    if timeframe == "15m":
        bars = fixture_data(count=6).bars
        missing, after = 2, 3
    elif timeframe == "1H":
        bars = fixture_data(count=16).bars
        missing, after = 4, 11  # One base input prevents the second 1H aggregate.
    else:
        bars = session_bars(("2024-03-11", "2024-03-12", "2024-03-13", "2024-03-14"))
        missing, after = 26, 77  # The second Daily aggregate cannot be completed.
    return bars, missing, after


@pytest.mark.parametrize("timeframe", ["15m", "1H", "Daily"])
@pytest.mark.parametrize("delayed", [False, True], ids=["missing", "delayed"])
def test_internal_gap_blocks_recursion_and_recovers_only_after_arrival(timeframe, delayed):
    bars, missing, after = gap_fixture(timeframe)
    supplied = list(bars)
    if delayed:
        supplied[missing] = replace(bars[missing], known_at=bars[-1].known_at)
    else:
        supplied.pop(missing)
    contexts = views(supplied)
    blocked = [c for c in contexts if bars[after].end_at <= c.as_of < bars[-1].known_at]
    assert blocked
    saved = []
    for c in blocked:
        for r in recursive_features(c, timeframe):
            assert_gap(r)
            saved.append((r, canonical(payload(r))))
        for field in ("macd_line", "signal_line", "histogram"):
            series = macd_series(c, "ALFA", timeframe, MACDSpec(1, 3, 3, 1), field=field)
            assert not series.contiguous
            first_bad = next(i for i, p in enumerate(series.points) if p.status != "READY")
            assert all((p.value, p.status, p.reason) == (None, "NOT_READY", "noncontiguous_history")
                       for p in series.points[first_bad:])
            # Even a window entirely AFTER the hole cannot use distorted MACD.
            for r in (rolling_percentile(series, PercentileSpec(1, 1)),
                      rolling_zscore(series, ZScoreSpec(1, 1, 0))):
                assert (r.status, r.reason, r.values.unpack()) == ("NOT_READY", "unavailable_input", {})
            saved.append((series, canonical(payload(series))))
    assert_gap(true_range(blocked[0], "ALFA", timeframe, TRSpec()))
    final = contexts[-1]
    if delayed:
        expected = recursive_features(views(bars)[-1], timeframe)
        for actual, full in zip(recursive_features(final, timeframe), expected):
            assert actual.status == "READY" and actual.values == full.values
        assert true_range(final, "ALFA", timeframe, TRSpec()).status == "READY"
        series = macd_series(final, "ALFA", timeframe, MACDSpec(1, 3, 3, 1), field="macd_line")
        assert series.contiguous and all(p.status == "READY" for p in series.points)
        assert all(p.known_at == bars[-1].known_at for p in series.points
                   if p.end_at >= bars[missing].end_at)
        assert rolling_percentile(series, PercentileSpec(2, 2)).status == "READY"
        assert rolling_zscore(series, ZScoreSpec(2, 2, 0)).status == "READY"
    else:
        for r in recursive_features(final, timeframe):
            assert_gap(r)
    for obj, serialized in saved:
        assert canonical(payload(obj)) == serialized
    with pytest.raises(FrozenInstanceError):
        saved[0][0].status = "READY"
    # An old detached context still yields the same unavailable snapshot.
    assert recursive_features(blocked[0], timeframe)[0] == saved[0][0]


@pytest.mark.parametrize("timeframe", ["15m", "1H", "Daily"])
@pytest.mark.parametrize("days", [
    ("2024-03-11", "2024-03-12"),  # Overnight.
    ("2024-03-08", "2024-03-11"),  # Weekend and DST change.
    ("2024-05-24", "2024-05-28"),  # Memorial Day holiday.
    ("2024-07-03", "2024-07-05"),  # Early close, holiday, next session.
])
def test_official_session_transitions_are_contiguous(timeframe, days):
    bars = session_bars(days)
    c = views(bars)[-1]
    selected = c.query("ALFA", timeframe)
    assert is_contiguous(selected, timeframe)
    assert all(r.status == "READY" for r in recursive_features(c, timeframe))
    # Directly exercise TR across the closure using just the adjacent slots.
    last = [b for b in selected if b.session == days[0]][-1]
    first = next(b for b in selected if b.session == days[1])
    boundary = ReplayContext(first.known_at, (last, first))
    assert true_range(boundary, "ALFA", timeframe, TRSpec()).status == "READY"
    raw = close_series(boundary, "ALFA", timeframe)
    assert raw.contiguous
    assert rolling_percentile(raw, PercentileSpec(2, 2)).status == "READY"
    assert rolling_zscore(raw, ZScoreSpec(2, 2, 0)).status == "READY"
    if days[0] == "2024-07-03" and timeframe == "1H":
        assert last.end_at - last.start_at == timedelta(minutes=30)


@pytest.mark.parametrize("timeframe", ["15m", "1H", "Daily"])
def test_missing_whole_trading_session_is_not_an_overnight(timeframe):
    c = views(tuple(b for day in ("2024-03-11", "2024-03-13")
                    for b in fixture_data(day).bars))[-1]
    for r in recursive_features(c, timeframe):
        assert_gap(r)
    raw = close_series(c, "ALFA", timeframe)
    assert not raw.contiguous
    assert_gap(rolling_percentile(raw, PercentileSpec(100, 1)))


@pytest.mark.parametrize("timeframe", ["15m", "1H"])
@pytest.mark.parametrize("side", ["before_close", "after_open"])
def test_missing_slot_at_early_close_boundary_is_still_a_gap(timeframe, side):
    c = views(session_bars(("2024-07-03", "2024-07-05")))[-1]
    selected = c.query("ALFA", timeframe)
    transition = next(i for i, b in enumerate(selected) if b.session == "2024-07-05")
    missing = transition - 1 if side == "before_close" else transition
    sparse = selected[:missing] + selected[missing + 1:]
    for r in recursive_features(ReplayContext(c.as_of, sparse), timeframe):
        assert_gap(r)
    crossing = sparse[transition - 2:transition] if side == "before_close" else sparse[transition - 1:transition + 1]
    assert_gap(true_range(ReplayContext(c.as_of, crossing), "ALFA", timeframe, TRSpec()))


@pytest.mark.parametrize("timeframe", ["15m", "1H", "Daily"])
def test_raw_and_external_scalar_windows_cannot_compress_internal_gap(timeframe):
    bars, missing, after = gap_fixture(timeframe)
    c = views(bars)[-1]
    complete = close_series(c, "ALFA", timeframe)
    # Explicit caller-built series: all delivered numbers are READY, one slot absent.
    sparse = replace(complete, points=(complete.points[0], *complete.points[2:]))
    assert not sparse.contiguous and all(p.status == "READY" for p in sparse.points)
    for r in (rolling_percentile(sparse, PercentileSpec(100, 1)),
              rolling_zscore(sparse, ZScoreSpec(100, 1, 0))):
        assert_gap(r)
    # Raw scalars are independent observations: a later contiguous window is valid.
    assert rolling_percentile(sparse, PercentileSpec(2, 2)).status == "READY"
    assert rolling_zscore(sparse, ZScoreSpec(2, 2, 0)).status == "READY"
    raw = close_series(views([b for i, b in enumerate(bars) if i != missing])[-1], "ALFA", timeframe)
    assert not raw.contiguous
    assert_gap(rolling_percentile(raw, PercentileSpec(100, 1)))


@pytest.mark.parametrize("timeframe", ["15m", "1H", "Daily"])
def test_no_history_before_first_visible_bar_or_after_last_is_required(timeframe):
    bars, _, _ = gap_fixture(timeframe)
    all_bars = views(bars)[-1].query("ALFA", timeframe)
    # Start mid-history and stop before the end; no synthetic leading/trailing gap.
    selected = all_bars[1:3]
    c = ReplayContext(all_bars[-1].known_at + timedelta(days=1), selected)
    assert all(r.status == "READY" for r in recursive_features(c, timeframe))
    assert true_range(c, "ALFA", timeframe, TRSpec()).status == "READY"
    single = ReplayContext(c.as_of, selected[:1])
    assert true_range(single, "ALFA", timeframe, TRSpec()).status == "READY"


def test_tr_recovers_when_its_two_bar_input_no_longer_spans_gap():
    bars = fixture_data(count=5).bars
    c = ReplayContext(bars[-1].known_at, (bars[0], *bars[2:]))
    assert true_range(c, "ALFA", "15m", TRSpec()).status == "READY"
    for r in recursive_features(c, "15m"):
        assert_gap(r)


def test_gap_reason_takes_precedence_over_warmup():
    bars = fixture_data(count=3).bars
    c = ReplayContext(bars[-1].known_at, (bars[0], bars[-1]))
    for r in (ema(c, "ALFA", "15m", EMASpec(3, 10)),
              macd(c, "ALFA", "15m", MACDSpec(1, 3, 3, 10)),
              atr(c, "ALFA", "15m", ATRSpec(3, 10))):
        assert_gap(r)
