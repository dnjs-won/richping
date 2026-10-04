# H0002 v1 signal freeze and efficacy preregistration

2026-10-04 owner decision: historical repeated price zones followed by a strict
same-bar failed downside break are frozen as an independent LONG directional
hypothesis. Price/OHLC/time drive the primary; volume is optional. No actor intent,
MACD, Daily/H1 context or H0001 state is assumed. The original hypothesis,
provisional spec, signal implementation and discovery stream remain unchanged.

The authoritative new records are `H0002-signal-freeze-v1.json`,
`H0002-r01-frozen-v1.yaml` and `H0002-efficacy-preregistration-v1.yaml`.
The manifest binds them, implementation, calendar/runtime and all prior tracked
files (except mutable status and Git attributes) by hash. Source uses the existing
explicit LF preservation policy; archived data/evidence remain byte exact.

Zone construction uses the most recent compatible pair of strict confirmed
three-bar lows in 128 completed slots, separated by at least four slots. The
midpoint is the center; half the median bar range is the half-width. Boundaries
publish only above the zone and become usable on the next bar. They never move.
The first close below the lower edge invalidates the zone; at creation index +128
it expires before processing that bar. Session closures use no slots. A gap,
unsupported calendar session or uncertified unit transition requires a fresh
stream/warmup, never a manually repaired zone.

Publication starts armed. Inclusive upper touch enters a visit; a whole bar above
the zone rearms. One event per visit requires `low < lower AND close > upper` on
one completed bar. Equality and a later recovery without a new same-bar break
do not trigger. A later bar within a visit may qualify only if that bar itself
strictly breaks and reclaims. No wick/color filter or multi-bar trigger exists.

Primary `PRICE_DEFENSE_REVERSAL_V1` is independent of volume. Nested comparator
`PRICE_DEFENSE_REVERSAL_VOLUME_CONFIRM_V1` requires current volume / median of
the previous 20 bars >=1. Missing volume and a zero median are UNAVAILABLE;
current zero is a real zero. No time-of-day normalization or volume superiority
claim is registered. Nested means subset, not necessarily a proper subset on
every future sample.

Discovery is 2026-05-05..08-13: 70 sessions, 4,480 eligible bars, 14 primary events
in 12 sessions and 11 comparator events in 10 sessions. This is structural
frequency evidence, never confirmation, power certification or performance.

The primary outcome horizon is four subsequent scheduled 15m slots: one observed
trading hour. Secondary 64/192-slot horizons describe persistence and cannot
replace the primary. Overnight closures consume no slot; missing scheduled data
cannot be compressed. The label is forward close / signal close -1, a gross
price direction mark, not a fill or net profit. MFE/MAE are outside v1.

The frozen baseline uses five most recent non-event anchors from the preceding
20 official sessions, matching exact local slot and sign of the prior four-slot
price change. Selection uses only metadata known at the event. Inadequate matching
is UNRESOLVED, never relaxed. Controls may be reused; overlapping event/control
windows remain reported. Absolute direction and matched timing excess must both
be positive for PASS. This is observational association, not causal actor proof.

Confirmation has ten official embargo sessions after registration, then exactly
252 official anchor sessions, 2026-10-19..2027-10-19. Follow-up ends 2027-10-22;
the fixed receipt deadline is 2027-10-23 20:00 ET. Warmup/control input begins
2026-09-21. New interval-specific immutable Alpaca coverage/action/unit admission
is required. Unsupported early-close days remain UNAVAILABLE in denominators,
not RTH substitutes; supported-day omissions prevent complete inference.
One terminal inference only; no outcome monitoring, count-based stopping or
result-driven extension. Future calendar amendments must be explicit before
outcomes. Neither H0001's separate 126-session contract nor its state changes.

Inference requires 40 complete events, 20 distinct event sessions and eight
occupied fixed 25-session blocks. This is a breadth floor, not a power claim.
Session-balanced means and a 10,000-replicate circular moving 25-session block
bootstrap preserve the full 252-day grid. Both families share resampling indices;
Bonferroni-adjusted 97.5% intervals apply per family. Only the price primary can
establish H0002 PASS. Volume never rescues/promotes itself; secondary horizons
remain descriptive. Every emitted primary must have a resolved primary label
and five resolved controls; no silently selected complete cases.

Disposition precedence is INVALID/FAIL_CLOSED, PENDING, UNRESOLVED, ZERO_SIGNAL,
INSUFFICIENT_EVIDENCE, PASS, REJECT, INCONCLUSIVE. PASS needs both lower bounds >0;
REJECT needs at least one upper bound <0. Equality is inconclusive. Rejection
means evidence against the joint positive thesis, not proof of no effect.
PASS permits further research, never production admission or profitability.

This action seals and verifies metadata only; it constructs no market dataset,
replays no prices and calls no outcome, forward window, database or network
accessor. Targeted/full regression separately exercise causal synthetic fixtures
and the previously sealed frequency-only replay, with no real H0002 outcomes.
The nonempty label/control/bootstrap evaluator is an executable design, not an
implemented or run efficacy claim. Next P0 is `H0002_FIRST_EFFICACY`: implement
that adapter and bounded exploratory discovery reporting under this contract.
Confirmation remains asynchronous/PENDING; after that disposition the project
can route H0003 independent intake without waiting a year.
