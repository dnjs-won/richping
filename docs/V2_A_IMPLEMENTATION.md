# V2-A causal replay foundation

Basis: `V2_STRATEGY_RESEARCH_ARCHITECTURE.md`, design commit `f1156b7`.
H0001-r03 remains DRAFT; no strategy or profitability experiment is implemented.

## Investigation and plan

The starting main checkout is `94cc2d2`, with pre-existing changes in cli,
maturity, paper, pipeline and an untracked R1 regression test. These stay in
the original checkout. Implementation uses a separate worktree and branch
`v2-a-causal-replay-foundation` based on `research-capture-contract`.

- Reuse core canonical/digest, aware UTC timestamps and XNYS calendar helpers.
- Adapt Store/PaperStore append-only, transaction, collision and idempotency
  patterns into an isolated database; never open/migrate a legacy database.
- Keep daily Dataset/Engine/feature_window/observe outside v2. Their session
  keys, 61-session features and research availability assumptions do not fit
  intraday causal replay. Dividend feature normalization remains distinct from
  outcome accounting.
- Preserve validation/evaluation time splits, excluded outcome denominators,
  failed trials and research versus forward evidence principles. No evaluation
  adapter or portfolio execution belongs to this phase.
- Existing integrity, dividend, feature_window, validation, evaluation and
  paper tests establish the regression boundary. No legacy code is edited.
- Implement contracts, immutable fixture import, clock/aggregation, generic
  callback and append-only evidence; then focused and full regression tests.

## Compatibility decisions

V2 is a Python API with synthetic fixtures only, not a CLI/provider integration.
The generic engine does not import strategy plugins. Supported timeframes are
data capabilities, not a trading hierarchy. Unsupported configurations fail.
The existing core code hash only covers top-level modules; v2 computes its own
recursive source hash including the reused core, without changing legacy IDs.

## Architecture and contracts

```text
host fixture records -> MarketDataset -> replay -> clock + CompletedAggregator
                                        |              |
                                        |       detached ReplayContext
                                        |              |
                                        |       Strategy -> Decision/Intent
                                        |              |
                                        +------ trace + checkpoint -> ResearchStore

contracts <- market_data/aggregation/store/replay/dummy
v2 modules -> legacy core helpers only
```

There is no import from v2 into legacy production modules. No legacy daily DB,
source row, operational artifact, hypothesis, model, risk or paper logic is edited.
The generic engine never imports a strategy plugin. The recorder is a mechanics
fixture; it counts observations and produces no orders or performance metrics.

- `MarketBar`: frozen, UTC-aware start/end/known timestamps, positive finite OHLC,
  finite nonnegative volume, consistent high/low, `start < end <= known_at`.
  Identity is `(dataset_id, symbol, timeframe, end_at)`; provenance is immutable
  canonical JSON. Corporate action state is explicit.
- `MarketDataset`: frozen tuple, nonempty normalized vintage ID, complete
  synthetic manifest, strict `(end_at, symbol, timeframe)` input order and unique
  identities. Capture cannot precede any record's known time. Non-RTH, unaligned,
  unsupported timeframe, unknown/present action and non-synthetic inputs fail.
  The caller supplies the vintage label; a separate SHA-256 fingerprint covers
  all bars, IDs and manifest. This avoids recursive dataset/bar hash definitions.
  Changed content under the same vintage ID is rejected on persistence.
- `JsonObject` stores canonical text and unpacks into detached mutable copies.
  `StrategyState` includes a plugin-defined schema version and JSON payload;
  dumps/loads roundtrip exactly. The plugin validates its own supported versions.
- `Strategy.initialize(context)` returns state; `on_event(context,state,event)`
  returns `Decision(new_state,intents)`. State updates are explicit, immutable
  values. Strategy parameters belong in its immutable specification. Plugins
  must be deterministic and cannot depend on unrecorded mutable configuration.
- `Intent` is ENTER/ADD/REDUCE/EXIT/HOLD/NO_ACTION, symbol, reason codes, optional
  requested quantity and input snapshot. Its persisted envelope records a
  deterministic intent ID, event ID, strategy/spec hash, decision/known timestamp
  and before/after state. It contains no execution price.
- `Fill` reserves validated execution timestamp/price/quantity/cost plus intent
  and execution-contract IDs for a future executor. Returning fills from the
  strategy callback fails; no execution simulator is implemented here.
- `ReplayEvent` binds run, sequence, availability time, one base bar and newly
  completed bars. The event ID hashes this complete payload.
- `DecisionTrace` includes the event, before/after state, intents, visible-prefix
  hash and previous trace hash. `Checkpoint` persists the post-event strategy
  state, sequence, clock and trace/visible hashes. State can be loaded and reused;
  automatic engine restart from a checkpoint is a later extension.

## Causal clock and aggregation

The host sorts a validated dataset by `(known_at, end_at, symbol, timeframe)` for
delivery. This is deliberately different from import ordering: a late-arriving
older candle must not hide or delay an already available newer candle. The
clock advances monotonically to each delivered bar's `known_at`. Equal timestamps
use the declared tie order and still trigger one callback per base bar.

Initialization receives an empty view at the earliest base interval start.
Each callback receives a frozen tuple containing only delivered base bars and
aggregates derived from those bars. Context and event have no dataset, loader,
generator, store, clock or engine reference. Old contexts remain detached after
later events. Query ranges filter market end times and reject a future endpoint;
availability always remains bounded by the context's own `as_of`.

This is an API capability boundary for trusted Python plugins, not an OS sandbox
against hostile code using introspection, filesystem/network access or globals.
Run/dataset hashes identify an input vintage; they are not feature inputs.

Aggregation convention `xnys_open_anchored_short_final_v1`:

- Input intervals are `[start_at,end_at)` on the XNYS RTH 15m grid. Calendars
  determine actual session open/close; no fixed UTC offset or weekday fallback.
- 1H buckets start at session open: 09:30–10:30, 10:30–11:30, etc. The final
  bucket is truncated at the official close and is complete only at that close.
  A regular day has six full hours plus 15:30–16:00; a 13:00 early close has
  three full hours plus 12:30–13:00. The shorter final bucket is an explicit
  exception to four 15m inputs, never an intermediate partial candle.
- Daily is aggregated directly from all expected 15m RTH slots. It does not
  depend on the requested hour view. Callers can request either or neither
  higher timeframe; there is no trading hierarchy in the engine.
- Completion requires exact grid coverage, `bucket_end <= as_of`, and every
  constituent delivered with `known_at <= as_of`. OHLC is first/max/min/last,
  volume is summed, and aggregate `known_at` is the maximum constituent time.
  Late input can complete an earlier bucket only at its actual arrival.
- Missing bars are never filled. Dataset diagnostics retain missing slots from
  each symbol's first session open through its last provided bar, including
  entirely missing intermediate trading days. The trailing fixture may be an
  intentional session prefix. Pending buckets remain PENDING; elapsed incomplete
  buckets are UNRESOLVED. Neither appears in completed views.
- Replay `status=COMPLETE` means all supplied events were processed. Separate
  `coverage_status` is COMPLETE/PENDING/UNRESOLVED; it is not a trade outcome or
  a profitability claim. Holidays do not generate expected trading slots.

The reused calendar currently supports 1990–2035. DST and the 2024-11-29 early
close are covered by fixtures. Supporting a different calendar or timeframe
requires a new explicit data/aggregation contract.

## Evidence storage and provenance

`ResearchStore(path)` requires its own SQLite file. A read-only preflight rejects
foreign/legacy schemas before DDL or journal writes. `application_id`,
`user_version=1`, schema hash and trigger presence identify the store. Unsupported
versions are rejected; there is no migration path in V2-A.

Tables are `v2_metadata`, `v2_datasets`, `v2_bars`, `v2_replay_runs`, `v2_traces`,
`v2_checkpoints`, `v2_results`. Intents live inside decision trace envelopes;
there are no placeholder fills/trades/evaluation tables. Bar identity also has
an input-sequence uniqueness constraint. Traces use `(run_id,sequence)` plus
unique event ID; checkpoints reference that same trace identity.

All rows have UPDATE/DELETE guards. Insert guards also prohibit REPLACE from
deleting/replacing an existing primary or alternate unique identity, including
on external SQLite connections with recursive triggers disabled. Store methods
compare the complete existing row before treating a repeat as idempotent;
different content fails. Dataset writes and trace/checkpoint pairs are atomic.
Trace chains, state continuity, checkpoint matching and strategy/dataset
provenance are checked. A finalized run cannot grow additional traces.

Run identity includes dataset ID/hash, strategy ID/specification/hash, engine
and strategy module code hashes, Python/calendar/tzdata versions, contract,
aggregation convention/timeframes, config (including seed if supplied),
experiment reference, optional hypothesis revision and `none_v2_a` execution
contract. The engine code hash includes recursive v2 source and reused core.
It does not alter legacy `core.code_hash()` or legacy model IDs.

Run registration precedes strategy initialization. On strategy failure, prior
committed steps/checkpoints remain and a FAILED terminal record is appended.
Identical reruns reuse evidence. Different results under the same run identity
are collisions, not updates; code/spec changes produce a new run identity.
Default experiment provenance is explicitly `fixture-only`, never research OOS,
fresh shadow, forward paper or live-fill evidence.

## Tests and remaining scope

The hidden-future test constructs eight bars before replay, then checks that the
observer sees exactly prefixes of length 1 through 8. It checks future query
rejection, lack of dataset/loader capabilities, frozen retained contexts, and
unchanged early contexts when later highs/closes are changed. Other fixtures
cover exact completion, hand-calculated OHLCV, delayed arrival, same-time symbols,
state restoration, repeated event/result hashes, gaps, DST, holidays, early
close, immutable rows, identity collisions, failed-run preservation and bytewise
legacy/paper DB preservation.

Validation results are recorded in PROJECT_STATUS.md after the final suite.

Limitations and follow-up:

- Fixture API and small in-memory replay only. No intraday provider, CSV/parquet
  file adapter, streaming retention policy or performance benchmark yet.
- Stored state restoration is supported, but automatic replay continuation and
  aggregator reconstruction from checkpoints are not implemented. A rerun from
  the beginning is deterministic and idempotent.
- V2-B: add strategy-neutral feature services with hand-calculated parity,
  warmup and future-leakage fixtures; causal structure must publish confirmation
  time. Do not put H0001 trading decisions in these services.
- V2-C: freeze executable hypothesis parameters before implementing H0001.
- Later execution/data/evaluation phases must explicitly define intent timing,
  costs, cash accounting, real corporate-action evidence, source quality and
  validation adapters reusing the existing evaluation principles. Synthetic
  confirmed-no-action metadata is not certification for real market data.
- No legacy bug fix is bundled. Legacy research modes have daily availability
  assumptions, Store's save_dataset has a same-ID early return, and core's
  top-level code hash does not include subpackages. Those contracts were isolated
  or handled locally instead of silently changed.
