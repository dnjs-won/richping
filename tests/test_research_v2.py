"""Synthetic causal foundation tests. No strategy performance assertions."""

from dataclasses import FrozenInstanceError, fields, replace
from datetime import timedelta
from hashlib import sha256
import json
import sqlite3

import pytest

from richping.core import canonical, close_at, digest, open_at, timestamp
from richping.store import Store
from richping.paper import PaperStore
from richping.research_v2.aggregation import CompletedAggregator
from richping.research_v2.clock import ReplayClock
from richping.research_v2.contracts import (
    CONTRACT_VERSION, Decision, Fill, Intent, JsonObject, MarketBar,
    ReplayContext, StrategyState, payload,
)
from richping.research_v2.dummy import RecorderStrategy
from richping.research_v2.market_data import MarketDataset
from richping.research_v2.replay import replay
from richping.research_v2.store import ResearchStore, TABLES


def fixture_data(day="2024-03-11", count=None, symbols=("ALFA",), bars=None, dataset_id="fixture-v1"):
    if bars is None:
        bars = []
        opened, closed = open_at(day), close_at(day)
        count = count if count is not None else int((closed - opened) / timedelta(minutes=15))
        for i in range(count):
            for symbol in symbols:
                start = opened + timedelta(minutes=15 * i)
                end = start + timedelta(minutes=15)
                bars.append(MarketBar(dataset_id, symbol, "15m", start, end, day,
                    100 + i, 103 + i, 98 + i, 101 + i, 10 + i, end, "fixture",
                    JsonObject.of({"fixture": "hand-inspected", "row": i}), "NONE_CONFIRMED"))
    manifest = JsonObject.of({"schema_version": CONTRACT_VERSION, "quality": "SYNTHETIC",
        "provider": "fixture", "adapter_version": "fixture-v1",
        "symbols": sorted({b.symbol for b in bars}), "membership_limitations": "synthetic fixed symbols",
        "base_timeframe": "15m", "timezone": "America/New_York", "calendar": "XNYS",
        "session_policy": "RTH", "captured_at": max(b.known_at for b in bars).isoformat(),
        "price_basis": "synthetic_unadjusted", "corporate_actions": "NONE_CONFIRMED",
        "known_at_policy": "explicit_per_bar"})
    return MarketDataset(dataset_id, bars, manifest)


class Observer(RecorderStrategy):
    def __init__(self):
        self.views = []
        self.events = []

    def on_event(self, context, state, event):
        self.views.append(context)
        self.events.append(event)
        return super().on_event(context, state, event)


def test_hidden_future_replay_exposes_only_delivered_prefix():
    data = fixture_data(count=8)
    observer = Observer()
    result = replay(data, observer)
    assert len(result.traces) == 8
    assert [e.base_bar for e in observer.events] == list(data.bars)
    for i, view in enumerate(observer.views):
        assert view.query(timeframe="15m") == data.bars[:i + 1]
        assert max(b.high for b in view.query(timeframe="15m")) == 103 + i
        assert all(b.known_at <= view.as_of for b in view.bars)
        assert not hasattr(view, "dataset")
        assert not hasattr(view, "store")
        assert not hasattr(view, "__dict__")
        assert {f.name for f in fields(view)} == {"as_of", "bars"}
        with pytest.raises(ValueError, match="Future"):
            view.query(end_at=data.bars[-1].end_at + timedelta(minutes=15))
    # Retained old contexts cannot gain bars as the engine continues.
    assert observer.views[0].query(timeframe="15m") == data.bars[:1]
    with pytest.raises(FrozenInstanceError):
        observer.views[0].bars = data.bars
    altered = fixture_data(bars=[b if i < 4 else replace(b, high=900, close=800)
                                 for i, b in enumerate(data.bars)])
    second = Observer()
    replay(altered, second)
    assert observer.views[:4] == second.views[:4]


def test_hour_and_daily_completion_exact_boundary_and_hand_ohlcv():
    data = fixture_data()
    observer = Observer()
    replay(data, observer)
    assert all(not v.query(timeframe="1H") for v in observer.views[:3])
    hour = observer.views[3].query(timeframe="1H")[0]
    assert hour.start_at == open_at("2024-03-11")
    assert hour.end_at == hour.known_at == data.bars[3].end_at
    assert (hour.open, hour.high, hour.low, hour.close, hour.volume) == (100, 106, 98, 104, 46)
    assert len(observer.views[6].query(timeframe="1H")) == 1
    assert len(observer.views[7].query(timeframe="1H")) == 2
    assert all(not v.query(timeframe="Daily") for v in observer.views[:-1])
    daily = observer.views[-1].query(timeframe="Daily")[0]
    assert (daily.open, daily.high, daily.low, daily.close, daily.volume) == (100, 128, 98, 126, 585)
    assert daily.end_at == daily.known_at == close_at("2024-03-11")
    hours = observer.views[-1].query(timeframe="1H")
    assert len(hours) == 7
    assert hours[-1].end_at - hours[-1].start_at == timedelta(minutes=30)
    assert hours[-1].provenance.unpack()["input_count"] == 2


def test_delayed_known_at_reorders_delivery_and_never_completes_early():
    data = fixture_data(count=6)
    bars = list(data.bars)
    bars[0] = replace(bars[0], known_at=bars[4].end_at + timedelta(minutes=1))
    observer = Observer()
    replay(fixture_data(bars=bars), observer)
    assert [e.base_bar for e in observer.events] == bars[1:5] + bars[:1] + bars[5:]
    assert all(bars[0] not in v.bars for v in observer.views[:4])
    assert all(not v.query(timeframe="1H") for v in observer.views[:4])
    hour = observer.views[4].query(timeframe="1H")[0]
    assert hour.known_at == bars[0].known_at
    assert hour.end_at == bars[3].end_at
    with pytest.raises(ValueError, match="Future"):
        ReplayContext(bars[0].end_at, (bars[0],))
    with pytest.raises(ValueError, match="Noncausal"):
        CompletedAggregator().accept(bars[0], bars[0].end_at)


def test_delayed_daily_final_bar_cannot_complete_at_market_close():
    data = fixture_data()
    bars = list(data.bars)
    bars[0] = replace(bars[0], known_at=close_at(bars[0].session) + timedelta(hours=1))
    observer = Observer()
    replay(fixture_data(bars=bars), observer)
    assert observer.views[-2].as_of == close_at(bars[0].session)
    assert not observer.views[-2].query(timeframe="Daily")
    assert observer.views[-1].query(timeframe="Daily")[0].known_at == bars[0].known_at


def test_ties_multi_symbol_and_deterministic_state_restore():
    data = fixture_data(count=4, symbols=("ALFA", "BETA"))
    observer = Observer()
    first = replay(data, observer)
    second = replay(data, Observer())
    assert first == second and first.hash == second.hash
    assert [t.event.id for t in first.traces] == [t.event.id for t in second.traces]
    assert len({t.event.id for t in first.traces}) == len(data.bars)
    assert not observer.views[0].query(symbol="BETA")
    assert len(observer.views[1].query(timeframe="15m")) == 2
    for cp in first.checkpoints:
        assert StrategyState.loads(cp.state.dumps()) == cp.state
    assert first.run_id != replay(data, Observer(), config=JsonObject.of({"seed": 2})).run_id
    assert first.run_id != replay(data, Observer(), timeframes=()).run_id
    # A restored state gives the same next decision using the detached causal view.
    restored = StrategyState.loads(first.checkpoints[2].state.dumps())
    assert Observer().on_event(observer.views[3], restored, observer.events[3]) == first.traces[3].decision


def test_input_order_duplicates_and_identity_fail_closed():
    data = fixture_data(count=4)
    for bars, reason in [(list(reversed(data.bars)), "ordering"),
                         ([*data.bars, data.bars[0]], "Duplicate"),
                         ([replace(data.bars[0], dataset_id="other"), *data.bars[1:]], "identity")]:
        with pytest.raises(ValueError, match=reason):
            fixture_data(bars=bars)


@pytest.mark.parametrize("field,value", [("open", 0), ("high", 1), ("low", -1),
    ("close", float("nan")), ("volume", -1), ("volume", float("inf")), ("volume", True)])
def test_invalid_ohlcv(field, value):
    with pytest.raises(ValueError):
        replace(fixture_data(count=1).bars[0], **{field: value})


@pytest.mark.parametrize("field", ["start_at", "end_at", "known_at"])
def test_timezone_naive_is_rejected(field):
    bar = fixture_data(count=1).bars[0]
    with pytest.raises(ValueError, match="Timezone"):
        replace(bar, **{field: getattr(bar, field).replace(tzinfo=None)})


def test_known_at_before_completion_and_clock_rewind_rejected():
    bar = fixture_data(count=1).bars[0]
    with pytest.raises(ValueError, match="known_at"):
        replace(bar, known_at=bar.start_at)
    clock = ReplayClock(bar.start_at)
    assert clock.advance(bar.known_at) == bar.known_at
    with pytest.raises(ValueError, match="backwards"):
        clock.advance(bar.start_at)


@pytest.mark.parametrize("day,open_hour,close_hour,count,hours", [
    ("2024-03-08", 14, 21, 26, 7), ("2024-03-11", 13, 20, 26, 7),
    ("2024-11-01", 13, 20, 26, 7), ("2024-11-04", 14, 21, 26, 7),
    ("2024-11-29", 14, 18, 14, 4),
])
def test_dst_and_early_close(day, open_hour, close_hour, count, hours):
    data = fixture_data(day)
    assert len(data.bars) == count
    observer = Observer()
    replay(data, observer)
    daily = observer.views[-1].query(timeframe="Daily")[0]
    assert daily.start_at.hour == open_hour and daily.end_at.hour == close_hour
    assert daily.start_at.minute == 30 and daily.end_at.minute == 0
    assert len(observer.views[-1].query(timeframe="1H")) == hours
    assert all(not v.query(timeframe="Daily") for v in observer.views[:-1])


def test_holiday_outside_session_and_unaligned_bars_rejected():
    bar = fixture_data(count=1).bars[0]
    for changed in [replace(bar, session="2024-11-28"),
                    replace(bar, session="2024-03-09"),
                    replace(bar, start_at=bar.start_at - timedelta(minutes=15)),
                    replace(bar, start_at=bar.start_at + timedelta(minutes=1),
                            end_at=bar.end_at + timedelta(minutes=1), known_at=bar.known_at + timedelta(minutes=1))]:
        with pytest.raises(ValueError):
            fixture_data(bars=[changed])


def test_gaps_never_manufacture_hour_or_daily_and_remain_in_denominator():
    data = fixture_data()
    broken = fixture_data(bars=[b for i, b in enumerate(data.bars) if i != 1])
    observer = Observer()
    result = replay(broken, observer)
    assert broken.gaps == (("ALFA", data.bars[1].end_at.isoformat()),)
    assert len(observer.views[-1].query(timeframe="1H")) == 6
    assert not observer.views[-1].query(timeframe="Daily")
    summary = result.summary.unpack()
    assert summary["coverage_status"] == "UNRESOLVED"
    assert {r["timeframe"] for r in summary["incomplete"]} == {"1H", "Daily"}
    prefix = replay(fixture_data(count=3), RecorderStrategy()).summary.unpack()
    assert prefix["coverage_status"] == "PENDING"
    next_day = fixture_data("2024-03-13", count=1)
    missing_day = fixture_data(bars=[*data.bars, *next_day.bars])
    assert len(missing_day.gaps) == 26


def test_dataset_import_query_hash_and_nested_immutability():
    data = fixture_data(count=4)
    rows = payload(data.bars)
    imported = MarketDataset.from_records(data.dataset_id, rows, data.manifest.unpack())
    assert imported == data and imported.content_hash == data.content_hash
    rows[0]["provenance"]["row"] = 500
    assert imported.bars[0].provenance.unpack()["row"] == 0
    assert data.query(symbol="ALFA", timeframe="15m", start_at=data.bars[1].end_at,
                      end_at=data.bars[2].end_at) == data.bars[1:3]
    with pytest.raises(FrozenInstanceError):
        data.bars = ()
    assert fixture_data(bars=[replace(data.bars[0], volume=999), *data.bars[1:]]).content_hash != data.content_hash
    # Different timezone spellings represent the same instant/content.
    changed = payload(data.bars)
    changed[0]["start_at"] = "2024-03-11T09:30:00-04:00"
    assert MarketDataset.from_records(data.dataset_id, changed, data.manifest.unpack()) == data


@pytest.mark.parametrize("action", ["UNKNOWN", "PRESENT"])
def test_corporate_actions_are_not_silently_certified(action):
    data = fixture_data(count=1)
    with pytest.raises(ValueError, match="corporate action"):
        fixture_data(bars=[replace(data.bars[0], corporate_action=action)])


def test_real_data_and_unsupported_provenance_rejected():
    data = fixture_data(count=1)
    for change in [{"quality": "research"}, {"calendar": "24/7"},
                   {"session_policy": "extended"}, {"captured_at": "2024-01-01T00:00:00Z"}]:
        with pytest.raises(ValueError):
            replace(data, manifest=JsonObject.of({**data.manifest.unpack(), **change}))


class IntentStrategy(RecorderStrategy):
    def on_event(self, context, state, event):
        return Decision(state, (Intent("NO_ACTION", event.base_bar.symbol, ("fixture_only",)),))


class InvalidFillStrategy(RecorderStrategy):
    def on_event(self, context, state, event):
        return Fill("fake", "unimplemented", context.as_of, context.as_of, 1, 1, 0)


def test_intents_recorded_with_provenance_but_strategy_cannot_return_fills(tmp_path):
    data = fixture_data(count=2)
    with ResearchStore(tmp_path / "v2.sqlite") as store:
        result = replay(data, IntentStrategy(), store=store)
        trace = result.traces[0]
        assert trace.decision.intents[0].kind == "NO_ACTION"
        assert trace.strategy_id and trace.specification_hash and trace.state_before
        assert trace.event.as_of == data.bars[0].known_at
        stored = json.loads(store.db.execute("SELECT body FROM v2_traces WHERE sequence=0").fetchone()[0])
        intent = stored["intent_records"][0]
        assert intent == trace.intent_records[0]
        assert intent["id"] != result.traces[1].intent_records[0]["id"]
        assert intent["known_at"] == intent["decision_at"] == data.bars[0].known_at.isoformat()
        assert "price" not in intent["request"]
        with pytest.raises(ValueError, match="never fills"):
            replay(data, InvalidFillStrategy(), store=store)
        statuses = [json.loads(r[0])["status"] for r in store.db.execute("SELECT body FROM v2_results")]
        assert sorted(statuses) == ["COMPLETE", "FAILED"]
        assert not any("fill" in t or "trade" in t for t in TABLES)


def test_store_roundtrip_idempotency_checkpoints_and_collision(tmp_path):
    data = fixture_data(count=8)
    path = tmp_path / "v2.sqlite"
    with ResearchStore(path) as store:
        first = replay(data, RecorderStrategy(), store=store)
        counts = {t: store.db.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in TABLES}
        second = replay(data, RecorderStrategy(), store=store)
        assert first == second
        assert counts == {t: store.db.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in TABLES}
        assert store.load_dataset(data.dataset_id) == data
        assert store.load_checkpoint(first.run_id, 3) == first.checkpoints[3]
        altered = fixture_data(bars=[replace(data.bars[0], volume=999), *data.bars[1:]])
        with pytest.raises(ValueError, match="collision"):
            store.save_dataset(altered)
        trace = replace(first.traces[0], visible_hash="changed")
        cp = replace(first.checkpoints[0], visible_hash="changed", trace_hash=trace.hash)
        with pytest.raises(ValueError, match="collision"):
            store.save_step(trace, cp)
        assert store.load_checkpoint(first.run_id, 0) == first.checkpoints[0]
    with ResearchStore(path) as reopened:
        assert reopened.load_dataset(data.dataset_id) == data


@pytest.mark.parametrize("action", ["UPDATE", "DELETE"])
def test_all_v2_rows_are_immutable(tmp_path, action):
    with ResearchStore(tmp_path / "v2.sqlite") as store:
        replay(fixture_data(count=4), RecorderStrategy(), store=store)
        for table in TABLES:
            sql = f"UPDATE {table} SET body='{{}}'" if action == "UPDATE" else f"DELETE FROM {table}"
            with pytest.raises(sqlite3.IntegrityError, match="immutable"):
                store.db.execute(sql)
            store.db.rollback()


def test_replace_cannot_bypass_immutability(tmp_path):
    path = tmp_path / "v2.sqlite"
    with ResearchStore(path) as store:
        store.save_dataset(fixture_data(count=1))
    with sqlite3.connect(path) as db:
        assert db.execute("PRAGMA recursive_triggers").fetchone()[0] == 0
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            db.execute("INSERT OR REPLACE INTO v2_datasets VALUES('fixture-v1','tamper','{}')")
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            db.execute("INSERT OR REPLACE INTO v2_bars VALUES('fixture-v1','BETA','15m','changed',0,'{}')")


@pytest.mark.parametrize("store_type", [Store, PaperStore])
def test_legacy_schema_and_file_bytes_are_unchanged(tmp_path, store_type):
    path = tmp_path / "legacy.sqlite"
    with store_type(path) as legacy:
        before_schema = list(legacy.db.execute("SELECT sql FROM sqlite_master ORDER BY name"))
        before_schema = [r[0] for r in before_schema]
    original = sha256(path.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match="Foreign/legacy"):
        ResearchStore(path)
    with ResearchStore(tmp_path / "v2.sqlite") as store:
        replay(fixture_data(count=4), RecorderStrategy(), store=store)
    assert sha256(path.read_bytes()).hexdigest() == original
    with sqlite3.connect(path) as db:
        assert [r[0] for r in db.execute("SELECT sql FROM sqlite_master ORDER BY name")] == before_schema


def test_unsupported_schema_fails_before_mutation(tmp_path):
    path = tmp_path / "future.sqlite"
    with sqlite3.connect(path) as db:
        db.execute("PRAGMA user_version=999")
    original = path.read_bytes()
    with pytest.raises(ValueError, match="unsupported"):
        ResearchStore(path)
    assert path.read_bytes() == original


class FailsAfterOne(RecorderStrategy):
    def on_event(self, context, state, event):
        if event.sequence == 1:
            raise ValueError("fixture deliberate failure")
        return super().on_event(context, state, event)


def test_failure_keeps_prior_checkpoint_and_repeated_failure_is_idempotent(tmp_path):
    with ResearchStore(tmp_path / "v2.sqlite") as store:
        for _ in range(2):
            with pytest.raises(ValueError, match="deliberate failure"):
                replay(fixture_data(count=4), FailsAfterOne(), store=store)
        assert store.db.execute("SELECT count(*) FROM v2_checkpoints").fetchone()[0] == 1
        body = json.loads(store.db.execute("SELECT body FROM v2_results").fetchone()[0])
        assert body["status"] == "FAILED" and body["completed_events"] == 1


def test_previous_session_daily_is_retained_over_holiday_boundary():
    first = fixture_data("2024-11-27")
    second = fixture_data("2024-11-29")
    data = fixture_data(bars=[*first.bars, *second.bars])
    observer = Observer()
    replay(data, observer)
    at_second_open = observer.views[len(first.bars)].query(timeframe="Daily")
    assert len(at_second_open) == 1 and at_second_open[0].session == "2024-11-27"
    assert len(observer.views[-1].query(timeframe="Daily")) == 2
    assert not data.gaps


def test_unsupported_timeframes_and_duplicate_aggregation_fail_closed():
    data = fixture_data(count=1)
    for frames in [("4H",), ("Daily", "Daily")]:
        with pytest.raises(ValueError, match="timeframe"):
            replay(data, RecorderStrategy(), timeframes=frames)
    aggregator = CompletedAggregator()
    aggregator.accept(data.bars[0], data.bars[0].known_at)
    with pytest.raises(ValueError, match="Duplicate"):
        aggregator.accept(data.bars[0], data.bars[0].known_at)
    for source in [data, ReplayContext(data.bars[0].known_at, data.bars)]:
        with pytest.raises(ValueError, match="timeframe"):
            source.query(timeframe="4H")


def test_forced_replay_identity_collision_is_not_ignored(tmp_path, monkeypatch):
    import richping.research_v2.store as storage
    with ResearchStore(tmp_path / "v2.sqlite") as store:
        data = fixture_data(count=1)
        store.save_dataset(data)
        spec = {"dataset_id": data.dataset_id, "strategy_id": "one"}
        run_id = store.begin_run(spec)
        monkeypatch.setattr(storage, "digest", lambda value: run_id)
        with pytest.raises(ValueError, match="collision"):
            store.begin_run({**spec, "strategy_id": "different"})
        assert store.db.execute("SELECT count(*) FROM v2_replay_runs").fetchone()[0] == 1


def test_generic_engine_has_no_legacy_execution_or_strategy_plugin_imports():
    import ast
    from pathlib import Path
    import richping.research_v2.replay as module
    for path in Path(module.__file__).parent.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert node.module not in {"engine", "validation", "evaluation", "paper", "feature_window"}
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                assert "h0001" not in ast.unparse(node).lower()
