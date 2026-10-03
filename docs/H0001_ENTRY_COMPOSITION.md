# H0001 initial-entry composition v1

This is a detached candidate research stream, not an order, fill, simulated
trade or portfolio. No outcomes are queried. The immutable preregistration is
`research/decision_records/H0001-entry-composition-freeze-v1.yaml`, written
before dataset loading and actual candidate replay. H0001 executable v13
resolves only this scope and remains DRAFT for the full strategy.

## Gates and processing

After complete atomic publication, evaluate authoritative Daily, the existing
1H raw classifier and frozen lifetime, then the existing 15m evaluator. Verify
explicit position evidence, then initial-entry consumption, evaluate and emit.
Same-batch 1H activation and 15m trigger are eligible after publication finishes.

All four joined roles must be READY, nonfuture, fresh and compatible. Daily
must be BULLISH, exhaustion NORMAL, frozen 1H episode ACTIVE, frozen 15m trigger
TRUE, position evidence FLAT, and the episode's initial right unconsumed.
Unavailable inputs take precedence over false predicates. OPEN is ineligible
for initial entry; missing evidence is UNAVAILABLE. Continuity/origin loss is
UNAVAILABLE rather than a measured false signal.

Daily remains RTH/PIT split adjusted, EMA50 close/positive five-observation
slope with N179 joint readiness. Exhaustion remains positive MACD_LINE,
current-inclusive empirical midrank W252/P95, N381 readiness. 1H remains
negative MACD_LINE W320/P05 with K2 last-extreme refresh. 15m remains negative
MACD_LINE W192/P10 at the first extreme, age 0..4 without refresh, the first
GC (`previous MACD <= signal`, `current MACD > signal`) and higher completed
close on that GC. The first GC consumes its arm even when price fails.
These classifiers/evaluators are reused, not copied or modified.

## Evidence and consumption

`RESEARCH_ENTRY_POSITION_EVIDENCE_V1` carries symbol, exact decision as_of,
known_at, state, version, explicit provenance and canonical hash. Its mode
`CANDIDATE_ONLY_FLAT_RESEARCH_MODE_V1` explicitly admits initial-entry
opportunities against fixed dataset hashes. It makes no claim about an actual
portfolio and is forbidden for execution or portfolio evaluation. Candidate
emission never changes FLAT to OPEN.

`H0001_INITIAL_ENTRY_EPISODE_IDENTITY_V1` reuses the frozen lifetime episode
ID: digest of symbol, activation raw state hash, activation as_of and lifetime
contract hash. Refresh retains that ID and its consumed initial right. At most
one INITIAL_ENTRY_CANDIDATE can occur in that episode. Later triggers are
recorded as initial-entry ineligible, without assigning an ADD meaning.

Expiry, Daily cancellation or 1H continuity/origin/unavailability cancellation
ends that right. Only a new completed 1H extreme activating a new episode can
create a new initial right. Same-identity recovery cannot automatically restore
the old episode. Consumption does not own position, ADD, exit or re-entry.

## Timing, identity and artifacts

The existing mixed-profile join rejects partial publication. The composer
checks the actual latest expected Daily/1H/15m identities. The 15m evaluator
owns its arm, first-GC consumption and correction/poll watermark. Delayed
members may advance that memory in end order; only the latest expected 15m
identity may emit. A composer watermark additionally prevents reviving a
trigger whose original decision was unavailable. There is no deferred queue.

Candidate ID includes symbol/type, decision as_of, completed 15m end, Daily
state refs, episode/state hash, frozen trigger/original extreme ref, position
evidence hash, specification and composer hashes, and causal input hash.
The JSON event stream is immutable and idempotent. Same identity with a
different payload, or a changed artifact at an existing path, is a collision.
No future data or return labels are serialized.

Run from the implementation worktree:

```powershell
.venv\Scripts\python -m scripts.h0001_entry_offline_proof
.venv\Scripts\python -m pytest -o cache_dir=var/pytest-entry-composition-cache
```

The proof independently reloads admitted Daily
`soxx-yahoo-rth-daily-pit-20261003-v2` and intraday
`soxx-yahoo-15m-20261003-v1` twice. Socket/provider calls are denied; SQLite
reads permit only `v2_bars`/`v2_datasets`. All 2,624 batches, 829 joint READY
joins, event IDs, payload hashes, denominators and stream hashes must match.
The joined stream must also match the existing action/unit proof. Identical
prepared Daily classifications can be cached, but the selector/transform
still runs at every batch; expected-session or input changes invalidate reuse.

Denominators are atomic-batch occupancy counts. GC/price counts are completed
15m observations within that stream. Actual arm cancellations/first-GC
rejections are separate from repeated cancellation evaluations with no arm.
Evidence lives in `research/data_evidence/h0001-entry-composition-20261003/`.
Empty candidate streams are valid; thresholds are never changed to increase
counts. Sparse opportunities may make the existing longer-history backlog a
future efficacy blocker.

Actual result: both offline runs contain zero candidates, with identical event
stream hash `f794a31903da1a110497b4badd58ffdc4bf0e3ce6cf7ec089c68597e6e781d46`.
There are 721 Daily BULLISH batches, 2,624 exhaustion NORMAL batches and 829
joint READY batches. Within joint READY, 364 are Daily NOT_BULLISH and 465
are ineligible because 1H is not ACTIVE. Independent hourly diagnostics find
208 READY 1H publications out of 656, with zero downside extremes. There are
no 1H activations, eligible 15m arms or composed triggers. GC primitives still
occur 92 times (80 price passes, 12 failures). Missing 1H warmup accounts for
1,795 unavailable candidate evaluations. Actual cancellation count is zero;
repeated 15m cancel evaluations are reported separately. This is ZERO_SIGNAL
for signal generation, with efficacy and all outcomes NOT_RUN.

All 1,346 tests passed in two disjoint partitions, including 55 new tests.
`test-report.json` and the two JUnit receipts record zero errors/failures/skips.

Phase exit 5 can complete after actual repeat evidence and tests. Exit 6 stays
open. Efficacy requires preregistration of sample unit, horizons, metric,
baseline/comparison, cost scope, null/pass/reject, chronological split,
confirmation/discovery boundary, uncertainty and multiple-testing accounting
before any outcome access. Research bar-end availability remains an assumption,
not reconstructed historical delivery/revision latency or live/shadow PIT.
