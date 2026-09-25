# Richping v2 Strategy Research Architecture

Status: DESIGN / implementation not started  
Initial hypothesis: `research/hypotheses/H0001-r03.yaml`

## 1. Goal

Richping v2 is not a MACD engine. It is a strategy-neutral, point-in-time event research engine that can encode H0001-r03 as its first strategy plugin and later run other hypotheses without changing the replay core.

The existing repository remains the project. Existing daily baseline, immutable datasets, recommendation/outcome contracts, research/shadow separation, corporate-action guards, experiment records, paper ledger, risk cohort, and operational evidence are preserved. v2 is added alongside them; existing production/shadow behavior is not rewritten merely to support H0001.

Immediate milestone: make H0001-r03 mechanically specifiable and causally replayable on Daily + 1H + 15m data. Profitability testing starts only after the engine contract and H0001 executable specification are frozen.

## 2. Preserve vs extend

Preserve and reuse where the contract is compatible:

- `core.py`: canonical serialization, hashing, aware timestamps, exchange-session helpers, code provenance.
- immutable dataset/version philosophy and content hashes.
- `known_at` / cutoff discipline and fail-closed missing-data behavior.
- research vs shadow distinction.
- experiment registration and preservation of failed trials.
- COMPLETE / PENDING / UNRESOLVED semantics where applicable.
- corporate-action evidence and dividend/split safety principles.
- cost stress, block/time-aware evaluation, purge/embargo principles.
- append-only paper/event ledger ideas and deterministic idempotency.
- SPY comparison and explicit limitations.
- risk-state/promotion contracts remain authoritative for the legacy production system.

Do not force intraday v2 data into the current `bars(dataset_id,ticker,session)` schema. That key cannot represent multiple bars per session/timeframe. Do not mutate old immutable datasets or silently migrate historical evidence.

## 3. Boundary

Three layers are deliberately separate:

```text
Research hypothesis
        |
        v
Strategy specification/plugin       <- H0001 lives here
        |
        v
Generic v2 research engine           <- no MACD-specific decisions
        |
        +--> immutable market data
        +--> causal timeframe aggregation
        +--> feature services
        +--> event replay clock
        +--> execution/portfolio simulation
        +--> trade/event evidence
        +--> evaluation / walk-forward
```

The engine may know what a feature is and how to request it, but must not know that "MACD extreme means buy", that HH/LH means exit, or that H0001 uses Daily/1H/15m. Those are plugin/specification concerns.

## 4. Proposed package layout

```text
richping/
  ...                         # legacy modules preserved

  research_v2/
    contracts.py              # Bar/Event/Intent/Fill/Trade/Strategy protocol
    market_data.py            # immutable intraday dataset + provenance
    aggregation.py            # causal 15m -> 1h/daily views
    clock.py                  # replay clock and availability rules
    features/
      registry.py             # generic feature provider interface
      macd.py                 # MACD calculation only; no trading rule
      relative.py             # rolling percentile/z-score/ATR normalization
      structure.py            # causal swing/HH/HL/LH/LL primitives
      volatility.py
    strategy/
      base.py                 # strategy protocol/state serialization
      registry.py
      h0001_r03.py            # only H0001-specific state machine/rules
    execution/
      simulator.py            # intent -> deterministic fill
      costs.py
      portfolio.py            # cash/positions/lots/adds
    replay/
      engine.py               # bar-by-bar orchestration
      evidence.py             # append-only decision/event trace
    evaluation/
      trades.py               # lifecycle metrics
      walkforward.py
      bootstrap.py
      benchmark.py
    store.py                  # isolated v2 research SQLite
```

Names may change during implementation, but dependency direction must remain one-way: generic engine must never import `h0001_r03`.

## 5. Core contracts

### MarketBar

Minimum identity:

```text
dataset_id
symbol
timeframe
start_at
end_at
session
open/high/low/close/volume
known_at
source/provenance
corporate_action state
```

Primary identity is `(dataset_id, symbol, timeframe, end_at)`, not session alone.

`end_at` is market-event time. `known_at` is when Richping is allowed to use the value. Replay decisions may only read records with `known_at <= replay_as_of`.

### Strategy protocol

Conceptual interface:

```python
class Strategy:
    strategy_id: str
    specification_hash: str

    def initialize(self, context) -> StrategyState: ...
    def on_event(self, context, state, event) -> list[Intent]: ...
```

A strategy receives only causal views exposed by the context. It cannot access the full future dataset directly.

### Intent

Generic intent types: ENTER, ADD, REDUCE, EXIT, HOLD/NO_ACTION. Intent records include strategy/spec hash, symbol, decision_at, known_at, reason codes, state-before/state-after, requested sizing, and input feature snapshot.

### Fill

Execution simulator converts intents into fills according to a separately versioned execution contract. Strategy code cannot directly assign a favorable historical fill.

### Trade lifecycle

A completed trade is reconstructed from fills rather than assumed from a fixed horizon:

```text
trade_id
strategy_id/spec_hash
symbol
entry fills[]
weighted average entry
exit fills[]
entry/exit timestamps
holding minutes/sessions
gross/net return
MAE/MFE
MFE capture ratio
costs
status
```

## 6. Causal multi-timeframe replay

The smallest authoritative input for H0001 should be 15-minute RTH bars unless the data contract later requires a finer base feed.

At each 15m close:

1. advance replay clock to the bar's usable `known_at`;
2. expose only bars known by that instant;
3. update completed 15m features;
4. causally aggregate/update 1H state only when the configured 1H bucket is complete;
5. update Daily state only from information legally available at that instant;
6. update causal swing/price-structure state;
7. call the strategy plugin;
8. persist decision trace and intents;
9. simulate fills using the declared execution timing;
10. update lots, cash, exposure and trade lifecycle;
11. persist state snapshot/checkpoint.

No partially completed higher-timeframe candle may be exposed as a completed 1H/Daily candle. If H0001 later explicitly wants partial higher-timeframe information, that must be a distinct feature with a distinct contract.

Replay must be deterministic: same dataset + strategy spec + execution spec + seed/config => same event/fill/trade hashes.

## 7. H0001-r03 as first plugin

The engine does not implement these rules. `strategy/h0001_r03.py` does.

Candidate state machine:

```text
DISABLED
  -> DAILY_LONG_ALLOWED
  -> SETUP_1H_DOWNSIDE_EXTREME
  -> ENTRY_READY_15M
  -> POSITION_OPEN
  -> FAILED_REVERSAL / ADD_READY
  -> POSITION_OPEN
  -> EXIT_WATCH_WEAK | EXIT_WATCH_STRONG
  -> EXIT_CONFIRMATION
  -> FLAT
```

The executable H0001 specification must parameterize, rather than hard-code into the engine:

- Daily LONG regime and exhaustion blocker.
- relative-MACD normalization and rolling lookback.
- 1H/15m downside thresholds.
- 15m GC/reversal trigger.
- definition of failed first reversal.
- maximum adds, tranche sizing and total risk.
- 1H upper extreme / histogram / slope / DC watch logic.
- causal swing algorithm.
- HH failure, LH and valid-HL break definition.
- weak vs strong EXIT-WATCH confirmation.
- order timing/fill rule.
- stop/max holding/overnight policy.

Until these unknowns are frozen, H0001 remains DRAFT and may be replayed only for engine fixtures, not claimed as a strategy performance test.

## 8. Relative MACD service

MACD feature code outputs raw MACD, signal, histogram and causal derivatives only.

A generic relative-feature layer can transform any scalar feature by methods such as:

- rolling percentile;
- rolling z-score;
- ATR-normalized value where dimensionally appropriate.

All rolling windows end at the current known observation. No full-sample normalization. Method/lookback/min-history are part of the strategy specification hash.

This separation lets later strategies reuse MACD or relative transforms without inheriting H0001 rules.

## 9. Causal price structure

Price structure must not use hindsight pivots.

The engine should support interchangeable causal swing detectors, for example:

- k-right-bar confirmed pivot, usable only at confirmation time;
- ATR/directional-change reversal, usable only after the reversal threshold occurs.

The detector emits events such as `SWING_HIGH_CONFIRMED` and `SWING_LOW_CONFIRMED` with both `pivot_at` and `confirmed_at`. Strategy decisions may use the event only at or after `confirmed_at`.

HH/HL/LH/LL classification is derived from confirmed swings. H0001's exact detector is a strategy-spec choice, not an engine default disguised as truth.

## 10. Data contract

The current yfinance daily contract is insufficient for long-history H0001 validation. v2 therefore separates the engine from providers.

A v2 dataset manifest must include:

- provider/adapter version;
- symbols/universe and membership limitations;
- raw/base timeframe;
- timezone and exchange calendar;
- RTH/extended-hours policy;
- capture/retrieval time;
- price adjustment basis;
- corporate-action evidence;
- known-at policy;
- coverage/gaps/duplicates diagnostics;
- immutable content hash.

Provider choice is an implementation milestone, not part of H0001. CSV/parquet import should be supported so a paid intraday provider can be added later without changing replay or strategy code.

Do not claim historical point-in-time or survivorship-free evidence unless the selected source actually supports it.

## 11. Storage isolation

Create a separate v2 research SQLite DB/schema first. Do not alter the existing production DB schema merely to gain intraday support.

Suggested append-only entities:

```text
v2_datasets
v2_bars
v2_strategy_specs
v2_experiments
v2_replay_runs
v2_decisions
v2_intents
v2_fills
v2_trade_events
v2_trades
v2_daily_nav
v2_checkpoints
```

Immutable source/spec/evidence tables receive UPDATE/DELETE guards like the current Store/PaperStore. Derived reports may be regenerated from immutable events.

Every result must be traceable to:
`hypothesis revision + strategy spec hash + dataset hash + code hash + execution contract + experiment id`.

## 12. Evaluation

H0001 is event/trade based, so the legacy fixed 5-session outcome is not its label.

Minimum evaluation set:

- number of independent signal events and completed trades;
- gross/net expectancy;
- win/loss distribution and payoff ratio;
- MAE/MFE;
- MFE capture ratio;
- holding time;
- turnover and costs;
- add/re-entry contribution;
- drawdown from explicit portfolio NAV;
- capital utilization;
- performance by regime/time period/symbol;
- benchmark comparison over aligned capital/time exposure where defensible.

Do not optimize win rate alone.

Walk-forward remains chronological. Discovery, parameter selection, validation and OOS/confirmation periods must be explicit. Purge/embargo must be derived from the event/holding dependency rather than blindly copying the legacy 21-session value.

The recent NOK/SOXX examples used to create H0001 are discovery examples and cannot serve as independent confirmation evidence.

## 13. Testing requirements

Before any profitability claim, automated tests must cover:

- future bar inaccessible before `known_at`;
- incomplete 1H/Daily bar inaccessible as completed;
- aggregation boundaries around session open/close and holidays;
- MACD parity against hand-calculated fixtures;
- rolling relative transform uses past only;
- pivot usable only at `confirmed_at`;
- HH/HL/LH/LL deterministic fixtures;
- H0001 state transitions including failed reversal/add and new-HH reset;
- no blind averaging while downside momentum merely continues;
- intent/fill separation;
- cost arithmetic and integer/declared sizing;
- replay idempotency and deterministic hashes;
- missing/gap/corporate-action fail-closed behavior;
- original legacy DB/artifacts unchanged;
- existing full pytest suite remains green.

A hidden-future fixture should replay a hand-inspected sequence one 15m bar at a time and assert that the strategy cannot see the later low/high.

## 14. Implementation sequence

### V2-A — contracts and replay skeleton

Add v2 contracts, isolated store, replay clock, immutable intraday dataset/import path, causal aggregation, and deterministic event trace. No H0001 trading decisions yet.

Acceptance: synthetic 15m fixture replays into correct 15m/1H/Daily known-at views with no future access; existing tests unchanged and green.

### V2-B — reusable features

Add MACD, relative transforms and causal price-structure services with hand-calculated and leakage tests.

Acceptance: features are strategy-neutral and reproducible from past-only bars.

### V2-C — H0001 executable specification

Convert r03 unknowns required for execution into an explicit versioned strategy spec. Do not choose thresholds by silently fitting the same evaluation sample. Implement H0001 plugin/state machine only after the spec is frozen.

Acceptance: synthetic scenarios reproduce entry, failed reversal/add, HOLD, weak/strong EXIT-WATCH, new-HH reset and structural exit.

### V2-D — historical intraday research dataset

Choose/import a data source, produce coverage report, freeze immutable dataset manifest, document limitations.

Acceptance: sufficient clean coverage exists for the declared discovery/validation design.

### V2-E — experiment and walk-forward

Register experiment before running it. Replay H0001, produce lifecycle outcomes, costs/stress, time/symbol/regime slices, and aligned benchmark diagnostics.

Acceptance: result is reproducible from immutable inputs and classified REJECTED / INCONCLUSIVE / CANDIDATE according to a predeclared rule. No automatic production promotion.

### V2-F — forward paper integration

Only after research machinery is trustworthy, adapt generic intents/fills/trades to the existing paper/risk philosophy. Keep forward evidence separate from historical research.

## 15. Explicit non-goals for the first build

- no automatic strategy discovery;
- no parameter optimizer;
- no automatic champion promotion;
- no broker/live orders;
- no options/GEX/Max Pain dependency;
- no order-block/VP/OBV/VWAP requirement;
- no rewrite of the legacy daily baseline;
- no attempt to prove H0001 profitable while its execution-critical unknowns remain unresolved.

## 16. First Codex implementation boundary

The first implementation request should be V2-A only.

It should create the generic contracts/store/replay/aggregation foundation and tests, while preserving all existing behavior. It must not implement H0001 MACD thresholds, optimize parameters, fetch a large historical dataset, modify the legacy production DB, or run a profitability backtest.

This keeps the first change auditable and establishes the causal engine on which H0001 and later strategies can safely run.
