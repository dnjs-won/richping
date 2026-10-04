# H0002 independent price defense research

The owner selected `PRICE_STRUCTURE_VOLUME_DEFENSE_REVERSAL` on 2026-10-04.
The falsifiable question is whether revisiting a previously formed price defense
zone and failing to break down predicts positive direction over a later frozen
horizon. No actor, order block, institution or causal buying pressure is inferred.

This action is observation → hypothesis → causal primitives → minimal candidate
→ frequency/readiness only. It does not freeze an investment signal or register
an outcome experiment. The single provisional definition is in
`research/strategy_specs/H0002-r01-candidate.yaml`, written before execution.
There is no parameter grid or definition search. An alternative volume-profile,
multi-session touch cluster or multi-bar reclaim would change meaning and needs
an owner decision before execution.

The proposed zone uses the most recent compatible pair of strict, right-confirmed
local lows within 128 completed 15m bars. Lows must be four slots apart. The center
is their midpoint and half-width is half the trailing median bar range. The pair
must fit inside that width and the publication close must be above the upper edge.
Only two interactions are required. Formation bars include the publication bar,
which confirms a past low; the resulting zone cannot signal on that same bar.
Published boundaries never move. It expires after 128 slots or on the first close
below its lower edge; an old pair cannot republish the same zone.

One whole bar above the zone rearms a visit. A low at the upper edge is a touch;
below it is penetration. During the resulting visit, a low strictly below the
lower edge and close strictly above the upper edge produces one candidate. No
wick, momentum or volume AND filter is required. Wick fraction and close recovery
are causal diagnostics. The only comparator adds current volume ≥ median of the
previous 20 bars. Null volume is unavailable, a recorded zero is an observation,
and an all-zero baseline is unavailable. Price-only works with no volume.

H0002 independently proposes the full admitted 04:00–20:00 ET stream, rather than
introducing a new aggregation/context. This session meaning must be approved at
freeze. Weekend/holiday closures consume no bar steps. Gaps reset warmup and active
zones; invalid input and incompatible vintage/revisions fail closed. Historical
bar-end availability is assumed as in the admitted vintage, not actual live PIT.
The certificate is ex-post price-unit admission, not a strategy feature. Cash
dividends are not normalized/reinvested here and outcome accounting is separate.

`READY` zone construction means the full causal window and positive width are
available, even if no compatible pair exists. `UNAVAILABLE` records warmup, gap or
missing/zero-baseline volume; `INVALID` records bad OHLC/volume, clocks or identity.
Active-zone bars, unique zones, reentries, primitive occurrences, deduplicated visit
candidates and candidate sessions are separate denominators. Rejection occurrences
after the first candidate in a visit are diagnostic, never additional candidates.

H0001 uses MACD extremes, GC/reversal and Daily/1H/15m composed momentum state.
H0002 uses repeated historical lows, zone interaction and price reclaim with optional
volume. Its module takes no H0001 state or feature. H0001 remains
`FROZEN / AWAITING_FUTURE_CONFIRMATION / HISTORICALLY_SPARSE`; its fixed 126-session
track stays separate. Prior anecdotal and H0001 data exposure are discovery exposure.

Before outcomes, freeze: zone/pivot/window/width/selection/creation/expiry/invalidation;
session scope, readiness/gap/revision rules; revisit/visit/dedup/rejection/timing;
primary and comparator roles, volume availability; source/spec/code/event hashes.
Then preregister horizon/entry anchor, null/control, complete/pending/unresolved label
denominators, clustering/uncertainty, evidence floor, multiple testing, costs scope,
untouched future confirmation/calendar/stopping and disposition rules. No horizon
is inherited from H0001 and no outcome accessor is provided in this action.

Frequency evidence and final test results are recorded separately in
`docs/H0002_FREQUENCY_RESULTS.md`; this preexecution contract remains byte-preserved.
