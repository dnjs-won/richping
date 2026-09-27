"""Generic replay orchestration. No features, execution or strategy-specific rules."""

from dataclasses import dataclass
from hashlib import sha256
from importlib.metadata import version
import inspect
from pathlib import Path
import platform

from .. import core
from ..core import digest
from .aggregation import AGGREGATION_VERSION, CompletedAggregator
from .clock import ReplayClock
from .contracts import (CONTRACT_VERSION, Checkpoint, Decision, DecisionTrace, JsonObject,
                        ReplayContext, ReplayEvent, Strategy, StrategyState, nonempty, payload)
from .market_data import availability_order, market_order


def code_provenance(strategy):
    root = Path(__file__).parent
    sources = {p.relative_to(root).as_posix(): p.read_text(encoding="utf-8")
               for p in sorted(root.rglob("*.py"))}
    sources["legacy/core.py"] = Path(core.__file__).read_text(encoding="utf-8")
    module = inspect.getmodule(type(strategy))
    path = getattr(module, "__file__", None)
    if path is None or not Path(path).is_file():
        raise ValueError("Strategy source file required for code provenance")
    return {"engine_hash": digest(sources), "strategy_module": module.__name__,
            "strategy_class": type(strategy).__qualname__,
            "strategy_code_hash": sha256(Path(path).read_bytes()).hexdigest(),
            "python": platform.python_version(), "exchange_calendars": version("exchange-calendars"),
            "tzdata": version("tzdata")}


@dataclass(frozen=True, slots=True)
class ReplayResult:
    run_id: str
    traces: tuple[DecisionTrace, ...]
    checkpoints: tuple[Checkpoint, ...]
    summary: JsonObject

    @property
    def hash(self):
        return digest(payload(self))


def replay(dataset, strategy: Strategy, *, store=None, timeframes=("1H", "Daily"),
           config=JsonObject(), experiment_id="fixture-only", hypothesis_revision=None):
    """One callback per base bar, ordered by (known_at, end_at, symbol, timeframe).

    Tied known_at values still deliver one record per event in the declared order.
    Later records at the same time are withheld until their own delivery event.
    No wall time, implicit research bypass, execution or portfolio is involved.
    """
    nonempty(strategy.strategy_id)
    nonempty(experiment_id)
    if not isinstance(strategy.specification, JsonObject) or not isinstance(config, JsonObject):
        raise ValueError("Immutable specification/config required")
    aggregator = CompletedAggregator(timeframes)
    specification_hash = digest(payload(strategy.specification))
    spec = {"contract": CONTRACT_VERSION, "mode": "SYNTHETIC_RESEARCH",
            "dataset_id": dataset.dataset_id, "dataset_hash": dataset.content_hash,
            "strategy_id": strategy.strategy_id, "specification_hash": specification_hash,
            "strategy_specification": payload(strategy.specification), "config": payload(config),
            "aggregation": AGGREGATION_VERSION, "timeframes": list(aggregator.timeframes),
            "order": "known_at,end_at,symbol,timeframe", "code": code_provenance(strategy),
            "execution_contract": "none_v2_a", "experiment_id": experiment_id,
            "hypothesis_revision": hypothesis_revision}
    run_id = digest(spec)
    if store is not None:
        store.save_dataset(dataset)
        store.begin_run(spec)
    clock = ReplayClock(min(b.start_at for b in dataset.bars))
    visible, traces, checkpoints = [], [], []
    try:
        state = strategy.initialize(ReplayContext(clock.as_of))
        if not isinstance(state, StrategyState):
            raise ValueError("Strategy initialize must return StrategyState")
        for sequence, bar in enumerate(sorted(dataset.bars, key=availability_order)):
            clock.advance(bar.known_at)
            completed = aggregator.accept(bar, clock.as_of)
            visible.extend(completed)
            context = ReplayContext(clock.as_of, tuple(sorted(visible, key=market_order)))
            event = ReplayEvent(run_id, sequence, clock.as_of, bar, completed)
            before = state
            decision = strategy.on_event(context, before, event)
            if type(decision) is not Decision:
                raise ValueError("Strategy must return Decision, never fills")
            if any(i.symbol not in {b.symbol for b in context.bars} for i in decision.intents):
                raise ValueError("Intent symbol has no causal observation")
            state = decision.state
            visible_hash = digest(payload(context.bars))
            trace = DecisionTrace(event, spec["strategy_id"], specification_hash, before, decision,
                                  visible_hash, traces[-1].hash if traces else None)
            checkpoint = Checkpoint(run_id, sequence, clock.as_of, state, trace.hash, visible_hash)
            if store is not None:
                store.save_step(trace, checkpoint)
            traces.append(trace)
            checkpoints.append(checkpoint)
        incomplete = aggregator.incomplete()
        summary = {"status": "COMPLETE", "evidence": "SYNTHETIC_ENGINE_FIXTURE",
                   "events": len(traces), "last_trace_hash": traces[-1].hash,
                   "coverage_status": "UNRESOLVED" if dataset.gaps or any(
                       r["status"] == "UNRESOLVED" for r in incomplete) else "PENDING" if incomplete else "COMPLETE",
                   "gaps": payload(dataset.gaps), "incomplete": list(incomplete),
                   "execution": "NOT_IMPLEMENTED"}
        if store is not None:
            store.finish_run(run_id, summary)
        return ReplayResult(run_id, tuple(traces), tuple(checkpoints), JsonObject.of(summary))
    except Exception as exc:
        if store is not None:
            store.finish_run(run_id, {"status": "FAILED", "completed_events": len(traces),
                                     "error_type": type(exc).__name__, "error": str(exc)})
        raise
