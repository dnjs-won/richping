# H0001 1H relative downside setup — bounded design proposal v1

Basis: `v2-c0-extended-session-contract@3a046021939b24068f4c95526496814c983af713`.
**PROPOSED_NOT_FROZEN. H0001 DRAFT / BLOCKED_ON_DECISIONS;
profitability NOT_TESTED; chart parity UNVERIFIED.**
[Machine-readable proposal](../research/decision_proposals/H0001-1h-relative-setup-v1.yaml).
No method, W, m, cutoff, polarity, comparator or lifetime is selected or ranked.
No historical/current outcome lookup, performance backtest, current SOXX/NOK
parameter fitting, price-bottom matching, production/paper/order integration or
main merge is part of this work. A contract test is not economic validation.

## Canonical upstream contracts and source boundary

Read the actual [Research Philosophy](RESEARCH_PHILOSOPHY.md),
[Daily input contract](H0001_DAILY_INPUT_CONTRACT.md),
[Daily trend contract](H0001_DAILY_PRICE_RESEARCH.md),
[Daily blocker contract](H0001_DAILY_BLOCKER_RESEARCH.md), their immutable
[input freeze](../research/decision_records/H0001-daily-input-freeze-v1.yaml),
[trend freeze](../research/decision_records/H0001-daily-trend-freeze-v1.yaml),
[readiness correction](../research/decision_records/H0001-daily-trend-readiness-remediation-v1.yaml),
[blocker freeze](../research/decision_records/H0001-daily-blocker-freeze-v1.yaml),
[r03](../research/hypotheses/H0001-r03.yaml),
[canonical v10](../research/strategy_specs/H0001-r03-draft.yaml),
[C0 specification](V2_C0_H0001_SPECIFICATION.md) and [status](../PROJECT_STATUS.md).
Historical v8/v9 counts and unresolved Daily statements are superseded by the
current records: EMA50 minimum history **174**, lag **5**, DLP-B first READY
**179**; H1-DAILY-LONG and H1-DAILY-BLOCKER are both RESOLVED. Their payloads,
Daily input choices and P2 no-deferred-blocked-signal policy remain unchanged.
Daily blocker W=252/P95 does not supply 1H W, cutoff or polarity.

The only direct 1H setup sources in r03 are:

| Source | Boundary |
|---|---|
| rules.setup[0] | Asset's MACD in a relatively deep downside region versus its own past distribution is a LONG setup candidate |
| rules.setup[1] | Use then-computable percentile, z-score or ATR normalization rather than absolute MACD or a future final minimum |
| rules.setup[2] | 1H GC is not confirmed as required for initial entry |
| rules.trigger[0] | Daily permission and inactive blocker plus 1H downside create setup |
| rules.trigger[1] | Inside that setup, separate 15m downside and reversal/GC form an entry candidate |
| unknowns[4], [5], [6] | Method, rolling history and downside cutoff are undecided |

The YAML preserves these eight statements exactly. This proposal is a new
bounded causal operationalization, not recovered chart settings. It adds no
1H GC requirement, MACD-minimum confirmation, price-low confirmation, RSI,
volume spike, divergence, 4H filter, macro, options or price-structure trigger.
Observed NOK/SOXX cases remain exposed discovery, never independent confirmation.

## Setup role, independent raw state, and field boundary

1H downside is **SETUP / CONTEXT**, not an entry signal. Conceptually:
`Daily BULLISH AND Daily exhaustion NORMAL AND 1H setup active` permits
waiting for a separately specified 15m trigger. It does not mean BUY.

| Proposed raw label | Meaning |
|---|---|
| DOWNSIDE_EXTREME | Required operands READY and the selected causal downside predicate true; neither BUY nor PRICE_BOTTOM |
| INACTIVE | Required operands READY and predicate false; not BEARISH |
| UNAVAILABLE | History, continuity, feature, known_at, session/input or finite-calculation failure, with reason; not INACTIVE |

Propose materializing an **independent raw 1H record before the Daily policy
join**, supported by existing immutable product-state transport. Do not calculate
it only when Daily allows entry: that loses the ungated denominator. Daily
trend/exhaustion, macro/options/sector/fundamentals and outcomes are not classifier
inputs. A Daily gate change cannot rewrite the raw result. Lifecycle may later
remain active after raw state becomes INACTIVE; it is a separate record.
An unresolved definition is a design question, not a measured UNAVAILABLE state.

Initial field boundary **F1=MACD_LINE=EMA12−EMA26** follows “MACD deeply down.”
Histogram measures line−signal, and signal has its own smoothing; neither is
the stated setup basis. Histogram belongs to exit-watch/other momentum questions.
Exclude histogram, signal line, slope, price return, RSI, volume, OBV and
divergence. Review-only F2 `MACD_LINE/ATR` is **R3's transform**, not an extra
field dimension; divide once. No ratio×percentile/z-score composition is proposed.

## Exactly three relative meanings; no champion

Audited code: [MACD](../richping/research_v2/features/macd.py),
[relative transforms](../richping/research_v2/features/relative.py),
[ATR](../richping/research_v2/features/volatility.py),
[feature contracts](../richping/research_v2/features/contracts.py),
[continuity](../richping/research_v2/features/continuity.py).

| Candidate | Quantity / units | Scale and cross-symbol meaning | Outliers / limitation | Threshold form |
|---|---|---|---|---|
| R1 ROLLING_PERCENTILE(MACD_LINE) | Recent empirical own-history rank; dimensionless | Increasing scalar transformations preserve rank apart from numerical effects; same rank is not same return or risk | Magnitude has less influence; occupancy, W, self-inclusion and ties matter | p < q or p <= q, lower-tail q unselected |
| R2 ROLLING_ZSCORE(MACD_LINE) | Distance from local mean in local standard deviations | Positive affine scalar transformations preserve score apart from numerical effects; no common tail probability/risk | Distance magnitude retained; mean/std sensitive to outliers; self-inclusion can damp extreme; ddof and zero variance matter | z < c or z <= c, negative c unselected |
| R3 MACD_LINE / ATR | EMA spread in current range-volatility units | Common positive OHLC price-unit scaling cancels; not own-history rank or equal account risk | ATR shocks change denominator and can compress ratio; fixed ratio threshold required | ratio < c or ratio <= c, negative c unselected |

R1 closely matches the own-distribution question without a shape assumption.
R2 measures local distance; **do not interpret it as Gaussian tail probability**.
R3 reduces price/volatility scale differences but asks a different question: it
does not directly establish “deep versus own historical distribution.” Retaining
R3 at freeze needs an explicit semantic rationale. These facts do not rank methods.

R3 reuses `positive_causal_scale_v1` +
`atr_wilder_sma_seed_first_high_low_v1`. ATR starts with high−low TR, then includes
previous-close gaps; SMA of first p TR seeds Wilder recursion over the full
visible prefix. It is not a rolling p-bar SMA. Require A>=p, both operands READY,
positive ATR, same symbol/timeframe/as_of/input-end and finite ratio. Normalize
input_count=2 counts operands, not independent observations. ATR p/A are unselected.

The actual [C0 capability gate](../richping/research_v2/strategy/capabilities.py)
requires explicit primitive parameters plus field for R1/R2 and window equal
to declared lookback. For R3 it admits nested `macd_atr_normalization_v1`
ATR/normalization contracts, requires ATR period equal to that same declared
lookback and denominator field `atr`. Thus that existing field means **ATR
scale period p** for R3, not a historical-distribution W. Do not add a second
W or normalize twice. Generic admission supports line/signal/histogram; this
proposal bounds the initial family to F1 without changing that gate. Admission
is neither method selection nor an implemented H0001 setup classifier.

## Current-inclusive and prior-only audit

CURRENT_INCLUSIVE uses `x_t` plus up to W−1 previous slots. V2-B supports only
this convention. Percentile version `rolling_empirical_midrank_v1` computes
`(less + .5*equal)/K` including self: unique minimum `1/(2K)`, unique maximum
`1−1/(2K)`, all-equal rank .5. Z-score version `rolling_zscore_ddof_v1` uses
current-inclusive mean/variance, ddof explicitly 0 or 1, m>ddof; zero variance
is UNDEFINED, not z=0. Causal self-inclusion is not future leakage.

PRIOR_ONLY uses W past reference slots through t−1; current x_t is query only.
Analogous empirical midrank can be 0 below all prior values or 1 above all;
current value does not move prior mean/std. Ties/ddof/partial-reference choices
still need a contract. **Both specs reject include_current=False.** Slicing and
calling existing primitives scores the last prior value, not today's query.
This is a capability gap; no prior-only engine is added. Future observations
are forbidden in both. Generic support does not select H1 conventions.

## 1H session, observation units, and lookback bands

Inherit H1-SESSION **RTH_EXTENDED / US_EQUITY_EXTENDED_04_20**, America/New_York,
04:00–20:00 ET, base 15m. [CompletedAggregator](../richping/research_v2/aggregation.py)
anchors to 04:00 and requires four constituents per completed 1H bucket:
04:00–05:00 through 19:00–20:00, **16 observations per standard session**.
Continuity version `us_equity_extended_04_20_completed_grid_v1`; aggregation
`us_equity_extended_04_anchored_full_session_v1`. Calendar closures have no steps;
overnight does not reset EMA. Extended early-close/nonstandard dates still fail
closed as **V2-D_BLOCKER**, with no skipping, padding or resolution here.

W counts **completed selected 1H observations**, never calendar hours/days.
An illustrative W=256 would correspond to about 16 full sessions; it is not a
selected W. Calendar descriptions below express memory meaning, not executable
date windows or sweep bounds:

| Band | Meaning | Tradeoff |
|---|---|---|
| SHORT | About 10–20 trading sessions of 1H observations | Fast adaptation; recent noise/regime sensitivity; extreme reference moves quickly |
| MEDIUM | About 1–3 trading months of observations | Intermediate memory; no optimality claim |
| LONG | Longer than MEDIUM | Stable reference; older regimes and longer warmup |

Next freeze chooses one observation count with semantic rationale. Do not infer
W from the current SOXX case or copy the Daily blocker count.

## Polarity, cutoff and equality

POL0 uses relative downside only. POL1 uses relative downside AND MACD_LINE<0.
A low rank in a very positive MACD regime can still be positive: POL0 permits
that interpretation while POL1 requires negative fast/slow spread. Both remain
unselected. R3 with positive ATR and a negative cutoff already implies negative
MACD, so POL1 is algebraically redundant there, not another search dimension.

R1 requires lower-tail q; R2 negative z cutoff; R3 negative ratio cutoff. No
numeric cutoff is proposed. H1-COMPARATOR independently owns STRICT (`LT`) vs
INCLUSIVE (`LE`). Equality must be explicit even if a chosen percentile cutoff
is unattainable on the midrank lattice. No silent rounding/tolerance. Neither
window minimum nor final future MACD/price bottom is a setup threshold.

## Generic readiness derivation and tested indexing

Inherit MACD 12/26/9, first-observation EMA seed, signal from first MACD,
full contiguous visible prefix, no reset, **M=130**. MACD first READY is
one-based observation M / zero-based index M−1; earlier projection slots stay
NOT_READY and are not deleted. Let N count completed 1H observations from
that origin, K=min(W,N), and m be transform admission count (0<m<=W):

```text
MACD: full-prefix continuity and N >= M
relative: selected-slot continuity and K >= m and every K slot READY and finite
for retained MACD slots: N >= M + K - 1
CURRENT_INCLUSIVE full W: N_first_ready = M + W - 1
PRIOR_ONLY full W + READY current query: N_first_ready = M + W (unimplemented)
R3: N >= max(M,A), plus positive ATR, aligned operands and finite ratio
```

For M>1, setting m<W does not automatically permit early readiness: before
N reaches W, the retained window includes origin warmup; thereafter warmup
remains until displaced by W READY values. Tests use several small arithmetic
windows on synthetic **extended 1H** bars to verify the off-by-one boundary,
including m<W; those fixture counts are not H0001 W choices. Z-score also needs
nonzero finite variance. Internal gaps invalidate MACD full-prefix continuity
even if the last relative window is locally contiguous. Scalar known_at must
be <=as_of; unavailable status/reason maps to raw UNAVAILABLE. Readiness is
computational admission, not statistical sufficiency or economic validity.

## Creation and persistence are separate: bounded lifetime matrix

| Family | Proposed active context | Additional choice | Benefit / risk |
|---|---|---|---|
| L0 CONTEMPORANEOUS_ONLY | Latest causally completed 1H predicate must be true at 15m trigger; false ends setup | No K/recovery parameter | Simple, little memory; slight 1H recovery may remove setup before 15m reversal |
| L1 LATCH_UNTIL_1H_RECOVERY | Extreme activates episode; persists until explicit recovery boundary crossed | Recovery boundary/equality | Accommodates timing separation; extra parameter and potentially old context |
| L2 FIXED_EXPIRY | Extreme activates episode for K completed 1H observations | K/counting/expiry equality | Explicit lifecycle; expiry may be early or context stale |

No lifetime champion. Price low, MACD relative low and 15m GC/reversal need not
coincide. Too-short lifetime misses a later trigger; long latch can retain a
downside context after substantial recovery. Do not fit K/recovery to anecdotes.
Freeze activation-bar counting, repeated-extreme refresh/retrigger, session
carry, expiry/cancel reasons, UNAVAILABLE behavior and Daily gate-loss/reset
ownership explicitly. UNAVAILABLE must not silently become INACTIVE or grant
eligibility. Daily blocker no-queue contract remains: an old blocked trigger
cannot execute automatically later. Episode persistence does not revive it.

## Completed-bar timing and downstream ownership

At 05:37 ET, use latest causally delivered completed 04:00–05:00, never the
in-progress 05:00–06:00 MACD. Aggregated end<=as_of is necessary but not enough:
known_at=max(all four actual constituent arrivals) can exceed end. Missing
constituents prevent publication. [Replay](../richping/research_v2/replay.py)
publishes equal-known_at batches atomically after all constituents are aggregated.
Delayed repair creates a current evidence vintage, never rewrites an old state.
The generic continuity check makes no leading/trailing freshness claim; how a
latest expected missing bucket affects eligibility must be explicit in the
future timing/lifecycle contract, with no implicit stale permission.

This proposal ends at context in which a 15m trigger can be evaluated. It leaves
H1-M15-RELATIVE-METHOD/LOOKBACK/RELATIVE-CONVENTIONS/DOWNSIDE/COMPARATOR/GC/
CONJUNCTION/REVERSAL unchanged, and designs no entry timing, add or re-entry.
H1-GC-ROLE remains UNRESOLVED; 1H GC is not made an entry requirement.
H1-STATE-TRANSITIONS and global H1-DECISION-TIMING remain unresolved.

## Conceptual comparison and multiple-testing boundary

All inherited Daily/downstream/data controls are identical within a future
comparison. Each S1–S3 row inherits its full audit above and in the YAML:

| Arm | Field / units | Window / readiness | Scale / outlier / cross-symbol meaning | Threshold / leakage risk |
|---|---|---|---|---|
| S0 NO_1H_DOWNSIDE_SETUP_FILTER | None | No filter; common-availability protocol must be frozen | Ungated denominator; no transform | None; changing baseline/denominator after results leaks selection |
| S1 R1 | MACD_LINE → rank | W/m slots; all READY | Local empirical rank; order sensitive, not magnitude dominated; no equal risk | q with LT/LE; future reference/incomplete bar/tuning forbidden |
| S2 R2 | MACD_LINE → local std units | W/m/ddof; all READY, positive variance | Local distance; outlier sensitive; not Gaussian tail probability | Negative z with LT/LE; future fitting/incomplete bar/tuning forbidden |
| S3 R3 | MACD_LINE → ATR ratio | ATR p/A; aligned READY, ATR>0 | Volatility scale; denominator shocks; not historical rank or account risk | Negative ratio with LT/LE; future scale/incomplete OHLC/tuning forbidden |

S0 is a counterfactual/denominator comparator candidate, not a live strategy
candidate; no fabricated READY/INACTIVE state when calculation is omitted.
No ranking. Next freeze retains **one canonical tuple plus at most one comparison
candidate**. S0 counts against that comparator budget if retained; method-vs-method
and S0 must not silently create three arms. H1-COMPARATOR is the predicate's
equality operator, distinct from the comparison candidate.

Forbid `field × transform × lookback × threshold × polarity × comparator ×
lifetime` grids, including 3×5×5×2×2×3; forbid crossing with Daily trend/blocker
families. Before outcomes freeze field/method/W/m/reference/ties/ddof/ATR/polarity/
cutoff/operator/lifetime as one small explicit tuple and trial budget. Post-result
changes require new revision/preregistration and viewed data become discovery.
Keep failed/null/inconclusive trials. Tuple freeze still does not complete the
performance protocol or real-data capability prerequisites.

## Preregistered future denominators and trace

Preserve total eligible completed 1H observations; MACD READY; relative READY;
UNAVAILABLE; downside extremes; Daily permission active; blocker NORMAL; Daily
allowed AND 1H extreme overlap; setup activations/durations/expiry/cancellation;
15m trigger opportunities inside **and outside** setup; completed entries;
no-entry setups; later MAE/MFE/forward outcomes; sample suppression ratio.
Distinguish symbol-observation, 15m opportunity and episode units. For S0, use
stable prefilter otherwise-eligible 15m opportunities: removed by setup / all
same prefilter opportunities, zero denominator=null. Report availability loss
separately from READY-predicate suppression and specify matched-availability vs
coverage diagnostics before results. Retain PENDING/UNRESOLVED/missing outcomes
and reasons. A few favorable survivors cannot establish alpha; recommendation
returns/cohort drawdown cannot be called account results without capital/NAV.

Future immutable trace must retain symbol/as_of/latest completed 1H end/MACD
line/method/value/version/hash/window/readiness/threshold/operator/raw state/
activation_at/expiry or cancel reason/latest state known_at/input hash/source
vintage/downstream 15m trigger ref/Daily permission refs. Add episode ID,
session/price basis/action vintage/input-contract hash, raw/lifecycle versions,
status/reason/reference count. Labels attach later in separate maturity records,
never become classifier inputs or rewrite old snapshots. No actual logger here.

## Capability audit, inventory and next freeze

| Available on supported synthetic profiles | Missing composition / real data |
|---|---|
| 15m causal bars, completed 1H aggregation, 1H MACD line | H0001 1H setup classifier and actual transition predicate |
| PercentileSpec, ZScoreSpec, ATRSpec, NormalizeSpec | Prior-only reference/query engine; setup lifetime evaluator |
| Continuity/readiness, causal input/spec/result hashes | Activation/cancellation logger and 15m trigger coupling |
| Immutable StrategyState/JsonObject/DecisionTrace/ResearchStore | Real PIT action transform, mixed-profile join, freshness selector, provider provenance, extended early-close |

[StrategyState/DecisionTrace](../richping/research_v2/contracts.py) transport
immutable product axes but do not validate H0001 episodes. FeatureResult has
**no explicit known_at field**; future composition must retain maximum actual
bar/scalar/action dependency arrival. A full dataset hash may cover future
data; preserve the causal prefix hash separately. No runtime/schema/classifier,
prior-only engine, event logger or order engine is added in this design.

Actual parser: **78 decisions / 10 resolved / 68 unresolved IDs / C1 44 /
performance 17 / optional 7 / 95 unresolved paths**, unchanged. Executable v10
and r03 remain byte-identical modulo checkout EOL; canonical hash remains
`b9a2c69ce9ea27010b7846339bf052401b3c836dc39c0538ab3e411cb59dd7f4`.
Six target decisions plus GC role/state transitions stay UNRESOLVED. Proposal
questions add no executable ID/path. C1/profitability/plugin export stays blocked.

Next freeze must choose: F1/method; at most one comparator arm including S0;
W/m/full or partial/reference convention for R1/R2, or ATR p/A/seed/scale for R3;
ties/ddof/zero-variance; POL0/POL1; cutoff units/value and LT/LE; L0/L1/L2 and
conditional recovery/K; activation/counting/expiry/retrigger/session carry/
unavailable and Daily gate-loss handling; immutable provenance and denominator/
availability/trial protocol. Separate GC/15m/timing/state-transition bundles
and full PIT universe/data/splits/costs/fills/capital/metric/null/pass-reject/
purge/embargo registration remain required before performance evaluation.

Contract-preservation and synthetic primitive fixtures validate only these
design boundaries and indexing. Full regression/CLI/diff results are recorded
in PROJECT_STATUS.md; none proves economic validity, profitability or chart parity.
