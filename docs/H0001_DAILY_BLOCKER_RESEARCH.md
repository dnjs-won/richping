# H0001 Daily exhaustion blocker — bounded research proposal v1

Basis: `v2-c0-extended-session-contract@819e6ffebb11e9cb0b5f08bc7d98e4523c98249a`.
**DESIGN / PROPOSAL ONLY. H1-DAILY-BLOCKER UNRESOLVED; H0001 DRAFT;
profitability NOT_TESTED; chart parity UNVERIFIED.**
Companion: [machine-readable proposal](../research/decision_proposals/H0001-daily-blocker-v1.yaml).
No selected tuple, champion, performance experiment, outcome lookup, historical
backtest, current chart analysis or production/paper change. No main merge.

The source r03 and executable v9 are preserved byte-for-byte modulo Git checkout
line endings. H1-DAILY-LONG remains RESOLVED:
`close > EMA50 AND EMA50_t > EMA50_(t-5)`, with minimum_history=174 for **each
EMA operand**, so canonical DLP-B first becomes READY at current 179 / lag 174.
The [readiness remediation](../research/decision_records/H0001-daily-trend-readiness-remediation-v1.yaml)
and [Daily input freeze](H0001_DAILY_INPUT_CONTRACT.md) remain authoritative.
This proposal reuses completed RTH_DAILY / PIT_SPLIT_ADJUSTED_OHLC / strict latest
expected completed session for exhaustion; reuse is proposed here, not a new
executable freeze or observed-chart reproduction claim.

## Source boundary: statement, context, and new design

Zero-based paths in [H0001-r03](../research/hypotheses/H0001-r03.yaml):

| Evidence | Exact recorded content / limit |
|---|---|
| `rules.regime[1]` | “일봉이 상방 상대 극단/과열 및 하락 전환 위험 상태라면 신규 롱을 차단하거나 축소하는 별도 blocker가 필요하다는 방향을 둔다.” |
| `rules.regime[4]` | “일봉 상승 레짐과 상방 exhaustion/blocker의 정확한 수학적 정의는 unknown이다.” |
| `rules.trigger[0]` | “일봉 롱 레짐이 허용되고 일봉 exhaustion blocker가 활성화되지 않은 상태에서 1시간봉 상대 MACD 하방 극단이 setup을 만든다.” |
| `unknowns[1]` | “일봉 upper-exhaustion blocker의 상대 MACD threshold와 차단/축소 방식” |
| `rules.setup[1]`, `unknowns[4:6]`, `required_data[4:6]` | Causal relative MACD alternatives, history and warmup context. Setup wording directly concerns **1H**; it does not freeze a Daily transform or field. |

The direction is a separate Daily upper-relative exhaustion concern, possibly
blocking or reducing new LONG exposure. Daily field, formula, transform,
lookback, threshold, readiness and action are unknown. **B1/B2 are new bounded
operationalizations**, not recovered historical strategy rules. Histogram
contraction and falling MACD/signal in `rules.exit` concern 1H EXIT-WATCH; they
do not authorize a Daily deterioration conjunction or forced exit.

Rising rates/oil, dollar, VIX, NQ reversal, option strike/GEX, sector rotation,
fundamental deterioration, a single Daily drop and news events are **not existing
H1-DAILY-BLOCKER evidence**. r03's options narrative is an alternative explanation,
not a core gate. [Research Philosophy](RESEARCH_PHILOSOPHY.md) requires observable
states to remain separate from causal explanation. EXTENDED will be a defined
measurement label; it will not prove exhaustion or predict a reversal.

## Independent raw state and lifecycle

Store a product of independent records for:
`daily_trend_permission`, `daily_exhaustion_state`, `daily_price_shock_state`,
`macro_state`, `sector_leadership_state`, `options_flow_state`, `fundamental_state`.
This study owns **only daily_exhaustion_state**. Price shock/crash protection
requires separate later research/decision provenance; no formula is proposed here.

| Raw exhaustion label | Proposed meaning after a predicate is frozen |
|---|---|
| NORMAL | All inputs READY and the selected causal exhaustion predicate is false. **Not SAFE**. |
| EXTENDED | All inputs READY and the selected causal upper-exhaustion predicate is true. **Not BEARISH; not SELL**. |
| UNAVAILABLE | Calculation is unavailable due to history/input/feature/readiness/freshness/action evidence or another calculation failure. **Not NORMAL**. |

An unresolved definition is a design question, not a measured NORMAL or a
working classifier. B0 does not fabricate NORMAL when it omits calculation.
Generic feature NOT_READY/UNDEFINED reasons must remain visible when composed
into an unavailable raw state. State computation and action policy have separate
versions, hashes and provenance; threshold plus action must not become one enum.

All nine trend × exhaustion combinations are valid: each of
`BULLISH / NOT_BULLISH / UNAVAILABLE` with each of `NORMAL / EXTENDED / UNAVAILABLE`.
Examples also preserve `(BULLISH, EXTENDED, NORMAL shock)`,
`(BULLISH, NORMAL, ADVERSE_SHOCK)`, `(BULLISH, EXTENDED, ADVERSE_SHOCK)` and
`(HOSTILE macro, BULLISH trend, NORMAL exhaustion)`.

Trend loss never resets exhaustion to NORMAL; EXTENDED never overwrites trend
as NOT_BULLISH. Shared inputs can independently make both axes unavailable,
with their own reasons. A Daily drop of -8% or rates +30bp / oil +5% / VIX spike
does not directly assign exhaustion. A price shock can naturally change the
close history, MACD or ATR; that is different from injecting a shock flag,
return cutoff or macro input into this classifier.

Same fresh input preserves raw state and causal hash at a later as_of. A newly
expected but undelivered Daily produces UNAVAILABLE for this axis, with no stale
NORMAL/EXTENDED fallback. Late evidence recomputes a current vintage only from
actual known_at, never backdates or edits old snapshots. Each record must retain
state/status/reason, symbol/as_of/session, profile/price basis/series role,
input end and max actual known_at, causal input hash, source/action vintage,
feature specification and state definition version/hash. Full dataset hashes
may identify an evidence envelope; they cannot replace a causal prefix hash.

## Bounded candidate family and MACD meaning

| ID | Question | Field | Still open |
|---|---|---|---|
| B0 — NO BLOCKER | Does a blocker add incremental value over canonical Daily trend only? | None required | Comparison availability/protocol; optional raw observation with P0 |
| B1 — line upper relative extreme | Is the medium-term fast/slow EMA spread unusually high relative to its own causal history? | `macd_line` | Transform, window, threshold, readiness, equality, polarity |
| B2 — histogram upper relative extreme | Is the **positive** MACD-to-signal momentum spread unusually high relative to its own causal history? | `histogram` | Transform, window, threshold, readiness, equality, explicit positivity contract |

MACD line = fast close EMA − slow close EMA. Signal is an EMA of that line;
histogram = line − signal. The line may remain high while histogram contracts;
a high positive histogram asks about a different spread. Neither is equivalent
to “MACD high.” Both raw fields use price units: a fixed absolute MACD number
does not represent the same past-relative position across price scales/assets.
The upper relative rank of a negative series can also be high; do not infer
positive spread merely from rank. B2's positive-spread interpretation must be
explicit in its later predicate; B1 polarity remains a freeze question.

Only B0/B1/B2 are initial members. No RSI, stochastic, Bollinger, ADX, price/EMA
distance, volume, OBV, divergence, HH/HL, dual-MA, multi-indicator AND/OR, macro
or options. DLP-C is deferred **Daily trend geometry**, not an exhaustion family
member. No B1/B2 ranking or field champion is selected.

## Relative transform audit against actual V2-B code

Sources: [relative.py](../richping/research_v2/features/relative.py),
[macd.py](../richping/research_v2/features/macd.py),
[volatility.py](../richping/research_v2/features/volatility.py),
[feature contracts](../richping/research_v2/features/contracts.py),
[continuity](../richping/research_v2/features/continuity.py).

| Property | Rolling percentile | Rolling z-score | MACD / ATR |
|---|---|---|---|
| Economic quantity | Empirical own-history rank | Distance from local mean in local standard-deviation units | Current EMA/momentum spread in current range-volatility units |
| Scale invariance | Strictly increasing scalar transforms preserve ranks, except finite-precision effects | Positive affine scalar transforms, except finite-precision effects | Common positive price-unit scaling cancels; no claim of general affine invariance |
| Cross-symbol comparability | Dimensionless local rank, not common distribution/risk | Dimensionless local dispersion, not equal tail probability/risk | Dimensionless scale ratio, not a historical rank or equal account risk |
| Outliers | Magnitude does not dominate rank; order/window occupancy still matter | Mean/variance sensitive; self-inclusion can damp current extreme | Range/gap shocks affect Wilder ATR and may compress ratio |
| Distribution assumption | Empirical; no Gaussian assumption | No normality needed to calculate; Gaussian-tail probability interpretation unsupported | No distribution fitted; ratio alone is not own-history extremeness |
| Current observation | Included in reference, only supported option | Included in mean/variance, only supported option | Current numerator and current TR/ATR included |
| Ties | `(less + 0.5*equal)/count`, including self; all equal rank 0.5 | No rank ties; equal values same score, all-equal variance UNDEFINED | No rank ties; denominator must be strictly positive |
| Minimum history | Positive explicit m ≤ W, all selected slots READY | Explicit m ≤ W and m > ddof; ddof 0/1, unselected here | Both operands READY; ATR min_history A ≥ period p; positive ATR |
| Window | Last min(W,N) slots, includes t, observation counts not calendar days | Same | SMA seed first p TR; Wilder recursion over full visible prefix, not rolling p-bar SMA |
| Readiness | Contiguity → count → every selected status; no dropping warmup/missing slots | Same, then zero variance/nonfinite UNDEFINED | Full-prefix continuity and operand readiness; unaligned operands raise; zero/nonpositive scale UNDEFINED |
| known_at | ScalarSeries rejects points known after as_of; MACD point arrival is max of full prefix | Same | Both causal snapshots align on symbol/timeframe/as_of/end; output lacks explicit known_at |

PercentileSpec version is `rolling_empirical_midrank_v1`; ZScoreSpec is
`rolling_zscore_ddof_v1`; NormalizeSpec is `positive_causal_scale_v1` and
ATRSpec is `atr_wilder_sma_seed_first_high_low_v1`. Specifications, source field,
parameters and actual causal inputs participate in hashes. Rolling input hash
also includes source series input hash. Normalize's input_count is **two
operands**, not a count of independent Daily observations; overlapping histories
cannot be added to claim more evidence.

**ATR ratio is a semantic mismatch if used alone for B1/B2's own-history
distribution question.** It is a supported volatility scale capability, not a
percentile. Later either defer it or explicitly register the changed meaning
before outcomes. Do not quietly add ratio × percentile/z-score combinations.
No transform champion is chosen; next freeze should retain **one canonical
transform and at most one comparator** with a semantic rationale, not a sweep.

### Current-inclusive versus prior-only

Current-inclusive reference at t contains x_t plus up to W−1 earlier completed
values. Midrank includes the current equality; for K observations a unique
maximum ranks `1−1/(2K)`, not 1. Z-score's current value also affects its own
mean and variance. This is causal because only values known by as_of are used.

Prior-only reference has up to W earlier values ending at t−1; x_t is the query,
excluded from the reference. Applying the analogous midrank formula to that
reference allows rank 1 above all prior values. The current value does not
affect prior mean/variance. Reference ties and minimum/full-window semantics
still need an explicit contract. Future observations are forbidden in both.

Actual PercentileSpec **and ZScoreSpec reject include_current=False**. Slicing
a series and calling today's function would score its last prior value, not x_t
against that reference. Prior-only requires a new versioned reference/query
primitive; none is implemented here. Generic current-inclusive midrank does
**not automatically select the H1 blocker convention**.

### Parameter meaning and observation counts; no values selected

Existing v9 MACD capability is 12/26/9, first-observation EMA seed, signal starts
at first MACD observation, full visible contiguous history, no session reset,
**MACD min_history M=130**. These inherited facts do not choose a blocker window
or replace trend EMA50 minimum_history=174. MACD warmup slots remain unavailable
in `macd_series`; they are not removed to build a cleaner distribution.

Let N be completed Daily observations from that origin, W reference slots,
m transform minimum count, K=min(W,N). Current implementation needs K≥m,
all K slots READY, and (for MACD) `N≥M+K−1`. With M=130, the first complete
ready rolling window requires **N≥129+W**, even if m<W: an earlier retained
warmup slot blocks the whole selected window. A future prior-only full W
reference plus current query needs **N≥M+W**; partial reference behavior is
unresolved and unimplemented. Raw ATR ratio needs `N≥max(M,A)`, A≥p and ATR>0.
Canonical trend availability remains an independent intersecting requirement.

W defines the local reference memory; m defines computational admission, not
statistical sufficiency. Percentile threshold means an upper empirical position;
z cutoff means local dispersion units and requires ddof; ATR period/seed,
minimum history and ratio cutoff mean volatility scale. Equality/sign semantics
are part of the predicate. **No W, m, percentile cutoff, z cutoff, ATR period,
ATR multiple or histogram absolute cutoff is selected.** There is no numeric
parameter grid. Readiness is not evidence of economic usefulness.

## Separate action policy candidates

| ID | Action when raw EXTENDED | Existing position HOLD/EXIT | Initial C1 feasibility |
|---|---|---|---|
| P0 OBSERVE_ONLY | Record raw state; no exhaustion permission effect | Unaffected | Signal observation candidate; no evaluator. B0 has equivalent trading permission behavior, with raw calculation optional. |
| P1 BLOCK_NEW_ENTRY_ONLY | Block new initial LONG entry only | Unaffected; no exhaustion veto on adds | Requires explicit initial/add/re-entry event semantics and gate timing |
| P2 BLOCK_NEW_ENTRY_AND_ADD | Block initial LONG and scale-in/add | Unaffected; no liquidation | Requires add/re-entry and setup lifecycle contracts |
| P3 REDUCE_SIZE | Reduce new exposure under a separate sizing contract | No forced liquidation | **Defer: PERFORMANCE / PORTFOLIO dependency**, H1-SIZING/H1-EXPOSURE unresolved; V2 capital/fill/cost composition absent |

P1/P2 do not authorize adds otherwise; H1-ADD-POLICY still owns eligibility.
Flat re-entry scope must be frozen explicitly rather than inferred from the word
“new.” NORMAL removes only an exhaustion veto, not other strategy gates.
UNAVAILABLE is distinct from NORMAL; its action handling must be frozen without
implicit fail-open conversion. Cadence, setup cancellation/expiry and simultaneous
signal interactions remain with H1-DECISION-TIMING / H1-STATE-TRANSITIONS.

No P0/P1/P2/P3 champion or reduction fraction. **Forced EXIT is excluded.**
Existing exit remains the separate 1H EXIT-WATCH + 15m price-structure contract,
itself still awaiting its existing choices; this proposal does not solve it.
Legacy Richping paper accounting exists separately but is not a V2 H0001 sizing
contract and cannot be silently inherited to make P3 executable.

## Conceptual comparison, multiple testing, and denominators

E0 = canonical Daily trend + B0; E1 = same trend + B1; E2 = same trend + B2.
These are conceptual comparisons only. No executable performance experiment
is registered: transform/window/threshold/action are all unselected.
Keep eligible PIT universe, Daily series, canonical trend, downstream setup/
trigger/exit rules, costs, capital/fills, chronological split and opportunity
identity aligned. Separately report availability loss instead of selecting only
an attractive surviving sample. Do not cross this with DLP-A/B/C trend research.

Searching `field × transform × lookback × threshold × action` and picking the
best performer is forbidden. A 2×3×4×5×3 search would be 360 trials, not one.
Before any outcomes: freeze a small explicit tuple family and trial budget,
then full dataset/universe/splits/cost/metric/null/pass-reject protocol using
the existing validation engine where compatible. Failed/null/inconclusive
trials remain in history. Post-result variants require a new registered revision;
viewed data become discovery evidence. Current SOXX/2026 and 2026-10-01 reversal
are not selection criteria or independent confirmatory evidence.

Required future preregistered diagnostics:

- Total Daily observations; trend BULLISH observations; exhaustion NORMAL,
  EXTENDED and UNAVAILABLE counts, including trend × exhaustion cross-tabs.
- H0001 setup opportunities before blocker; blocker-removed setups; actual
  signals; completed trades; capital exposure time; turnover.
- After-cost return; MAE; MFE; drawdown; blocked trades' counterfactual forward
  outcomes; sample suppression ratio.

Preserve symbol-session and opportunity-event units separately. Proposed
suppression ratio is exhaustion-blocked otherwise-eligible opportunities /
the same preblock eligible opportunities; zero denominator is null. Readiness
suppression is separate from EXTENDED policy suppression. Retain COMPLETE,
PENDING and UNRESOLVED outcomes and reasons. A higher win rate on a few remaining
trades is not alpha. Return/cohort drawdown is not account performance; account
metrics require declared capital/NAV accounting.

## Counterfactual logging and actual capability gaps

Future blocking must retain preblock setup/signal records, with stable event,
symbol/as_of/episode and initial/add/re-entry identity, conditions, all axis
records, state/policy/spec/input hashes, data/action vintages and blocking reason.
For a **fully eligible preblock signal**, preserve:

```yaml
decision: BLOCKED_BY_DAILY_EXHAUSTION
counterfactual_signal:
  would_have_entered_without_blocker: true
```

A setup alone does not imply would-have-entered: lower-timeframe trigger and
other permissions must qualify under the frozen baseline. Hypothetical fill,
cost and forward-outcome contracts must be versioned and distinct from actual
orders/fills. Later outcome writer attaches labels at their actual maturity;
future labels never enter raw state or decision. Missing/PENDING/UNRESOLVED
counterfactual outcomes remain in denominators, never disappear or become zero.

| Capability | Actual status |
|---|---|
| Completed Daily aggregation, MACD line/histogram, causal projection | Available for supported synthetic profiles; no partial Daily; delayed constituents need actual arrival |
| Percentile/z-score, ATR/normalization, rolling readiness/continuity | Available as audited primitives; no threshold or exhaustion classifier |
| Feature/spec/input/result hashes; scalar known_at | Available. **FeatureResult lacks an explicit known_at field**; future composer must derive/preserve max actual dependency arrival, including action evidence |
| Immutable StrategyState/JsonObject, DecisionTrace, ResearchStore | Can carry metadata in immutable state/trace envelopes. No H0001 preblock event logger, counterfactual trade lifecycle, label evaluator or reporting contract |
| Exhaustion classifier and blocker policy evaluator | NOT_IMPLEMENTED; no new engine or helper added here |
| Prior-only transform, normalized MACD scalar-series builder | NOT_IMPLEMENTED; ratio snapshot is available, rolling composition is not supplied |
| Real PIT split/action transform, freshness selector, mixed-profile join, provider/session/action provenance | Remaining V2-D/C1 gaps; prepared synthetic inputs do not prove them |
| V2 sizing/capital/fill integration; extended early-close | Missing integration; **V2-D_BLOCKER unchanged** |

The existing causal/readiness tests cover completed/delayed Daily, internal gaps,
future scalar rejection, retained warmup slots, hashes, prefix invariance,
normalization alignment/nonpositive scales and unavailable reasons. Primitive
availability is not a selected H0001 rule or proven strategy.

## Decision ownership, inventory, and next freeze

Retain **H1-DAILY-BLOCKER** as one existing executable decision. Propose nested
`state_definition {field, transform, lookback, threshold, window_convention,
readiness, equality, polarity, transform_specific_parameters}` and
`policy {action, unavailable_behavior, reentry_scope, cadence/lifecycle}`.
Track separate nested version/hash/freeze references plus the combined contract
hash. Generic parser supports nested typed contracts, but no blocker-specific
admission/frozen-hash validator exists yet. Separate provenance is feasible in
the proposed design; no current need to proliferate IDs. Only if nested tracking
proves insufficient should minimal ID separation be reconsidered.

Executable v9 remains completely unchanged, including the single unresolved
`rule_parameters.daily_exhaustion_blocker` root. Actual parser inventory remains
**78 decisions / 9 resolved / 69 unresolved IDs / 45 C1 / 17 performance /
7 optional / 96 unresolved paths**. Proposal questions do not count as new
executable unresolved paths. Canonical v9 SHA-256 remains
`6effcae1ae4e539adf0c84550821be507d86b63565b419b7877a4d08599d9c06`.

Next freeze must decide field; one canonical transform and at most one
comparator; W/m and warmup composition; upper threshold/units/equality/polarity;
current-inclusive versus prior-only and method conventions (ties/ddof or
ATR settings only if retained); independent raw-state provenance/readiness;
action and UNAVAILABLE/re-entry handling; cadence and setup/add lifecycle;
explicit tuple/trial budget, counterfactual and denominator protocol.
Full performance registration additionally needs real eligible data/coverage,
chronological discovery/confirmation, costs/capital/fills, sample unit, primary
metric/null/decision rule before results. This stage chooses none of those.

Contract tests verify preservation and proposal boundaries, including independent
state transport and shock/macro exclusion. They do **not** prove economic validity,
chart parity, real-market readiness or profitability. Final regression and
whitespace results are recorded in PROJECT_STATUS.md.
