# H0001 최초 LONG 15m entry trigger — bounded design proposal v1

Basis: `v2-c0-extended-session-contract@58e67178113b757a675858af1b4f31fca8508c60`.
**PROPOSED_NOT_FROZEN; H0001 DRAFT / BLOCKED_ON_DECISIONS;
profitability NOT_TESTED; chart parity UNVERIFIED.**
[Machine-readable proposal](../research/decision_proposals/H0001-15m-entry-trigger-v1.yaml).
Candidate IDs below identify design alternatives, not executable decisions.
No champion, ranking, numeric 15m W/m/threshold/K, polarity, cross definition,
reversal formula or execution price is selected. No outcome lookup, backtest,
SOXX/NOK fitting, parameter grid, production/paper/order change or main merge.

## Canonical upstream audit

Read actual [r03](../research/hypotheses/H0001-r03.yaml),
[canonical v11](../research/strategy_specs/H0001-r03-draft.yaml),
[C0 specification](V2_C0_H0001_SPECIFICATION.md), [status](../PROJECT_STATUS.md),
[1H research](H0001_1H_RELATIVE_SETUP_RESEARCH.md) and
[1H freeze](../research/decision_records/H0001-1h-relative-setup-freeze-v1.yaml).
Daily evidence: [input](H0001_DAILY_INPUT_CONTRACT.md),
[trend](H0001_DAILY_PRICE_RESEARCH.md), [blocker](H0001_DAILY_BLOCKER_RESEARCH.md)
and their immutable decision records, including trend-readiness remediation.
Earlier unresolved statements retain their historical basis; current contracts are:

| Axis | Frozen contract, preserved |
|---|---|
| Daily input | RTH_DAILY; PIT_SPLIT_ADJUSTED_OHLC; latest expected completed session required; no stale/raw fallback; maximum actual bar/action/transform known_at |
| Daily trend | BULLISH iff READY, close > EMA50 AND EMA50_t > EMA50_(t-5); EMA minimum history174, first joint READY179 |
| Daily exhaustion | EXTENDED iff READY, MACD_LINE > 0 AND current-inclusive percentile252 >= .95; otherwise READY=NORMAL, failure=UNAVAILABLE |
| 1H raw setup | READY AND MACD_LINE < 0 AND current-inclusive midrank percentile320 <= .05; W=m=320 |
| 1H lifetime | New completed extreme plus Daily BULLISH/NORMAL activates; every new extreme refreshes last_extreme; K=2 completed1H observations, age0/1/2 ACTIVE, age3 EXPIRED |

1H unavailable/Daily permission or exhaustion loss cancels immediately; recovery
alone never restores an episode. Old extreme identity cannot reactivate it.
NO_DEFERRED_EXECUTION remains. Raw 1H is Daily-independent. Neither upstream
payload nor hash changes. v11 hash remains
`63dccca8a6c00c41b1643e3710fe48261ec8736f005076d4405d231048fe139a`.

## Exact r03 source boundary

Each quotation below is from `research/hypotheses/H0001-r03.yaml`, zero-based paths.
The proposal YAML preserves the same exact text and related required_data/leakage
risk entries for machine checks against the immutable source.

| Path | Exact source statement |
|---|---|
| rules.trigger[1] | 그 setup 안에서 15분봉 MACD도 상대적으로 깊은 하방 영역에 있고 골든크로스 또는 확인된 가격 반전이 발생하면 최초 롱 진입 후보가 된다. |
| observations[0] | 0선 아래 MACD 골든크로스 뒤 단기 상승이 자주 보였다는 경험적 관찰이 있었으나 빈도와 통계적 유의성은 측정하지 않았다. |
| observations[2] | 가격 저점, MACD 최저점, MACD 골든크로스는 동일 시각일 필요가 없으며 MACD의 EMA 평활 특성 때문에 시차가 발생할 수 있다고 논의했다. |
| unknowns[6] | 1시간봉과 15분봉의 하방 extreme threshold |
| unknowns[9] | 15분봉 골든크로스만으로 trigger를 확정할지 가격 반전 조건도 필수로 할지 |

r03 does not freeze: GC necessarily below zero; GC alone means BUY; price
reversal mandatory; MACD minimum and GC same-bar; one bullish candle confirms
reversal; mandatory5m/1m confirmation. T3 is closest to the literal OR wording,
but this is semantic observation, not selection or measured evidence.
Required inputs are PIT universe/OHLCV, completed15m/1H/Daily aligned states,
MACD warmup, relative history, causal swing prices and session/timezone metadata.
Cost/fill prices belong to later performance/execution registration. Generic
OHLCV transport does not add a volume feature. r03's HH/HL/LH/LL data requirement
does not import its exit rules into initial entry.
Exposed NOK/SOXX discovery cannot be reused as independent confirmation;
future extrema/ranks, incomplete aggregates, backdated pivot confirmation,
combinatorial search and narrative fitting are leakage/selection risks.

## Four layers and independent raw vocabulary

| Layer | Responsibility |
|---|---|
| A RAW RELATIVE STATE | Is completed15m MACD sufficiently down versus the selected causal reference? Materialize ungated by Daily/1H so denominators survive |
| B REVERSAL EVIDENCE | Completed MACD CROSS_EVENT and/or confirmed price reversal; events are not orders |
| C TEMPORAL COMPOSITION | Relate extreme observation to reversal time; same-bar or bounded causal memory remains a choice |
| D ENTRY CANDIDATE | Position-flat INITIAL_ENTRY, valid1H setup ACTIVE and frozen A+B+C, with current causal upstream references |

`M15_REVERSAL_EVENT` is an ungated raw event; `H0001_INITIAL_ENTRY_CANDIDATE`
is the coupled candidate. ENTRY_CANDIDATE != ORDER != FILL. Actual decision
cadence/order time/fill price remain H1-DECISION-TIMING and execution owners.

| Raw state | Meaning |
|---|---|
| DOWNSIDE_EXTREME | All operands READY and future frozen relative predicate true; !=BUY, !=PRICE_BOTTOM, !=REVERSAL |
| INACTIVE | All operands READY, predicate false |
| UNAVAILABLE | History/continuity/feature/known_at/completed-bar/calculation failure with reason; !=INACTIVE |

An unresolved definition is a design blocker, not a measured UNAVAILABLE label.
Armed state can persist when raw becomes INACTIVE under a future C1/C2 choice;
memory never overwrites raw. No classifier is implemented here.

## Field and relative-method audit against actual primitives

Primary candidate field only **MACD_LINE=EMA12−EMA26**. Signal line is a GC
operand, not an alternative raw field. Exclude histogram, signal-line relative
rank, MACD slope, RSI, stochastic, volume, OBV, divergence and price return.
Reuse inherited MACD12/26/9, first-observation EMA seed, signal from first MACD,
min_history130, full completed causal contiguous history, no session reset.

Audited [MACD](../richping/research_v2/features/macd.py),
[relative](../richping/research_v2/features/relative.py),
[ATR](../richping/research_v2/features/volatility.py),
[contracts](../richping/research_v2/features/contracts.py) and
[continuity](../richping/research_v2/features/continuity.py):

| Audit | R1 ROLLING_PERCENTILE | R2 ROLLING_ZSCORE | R3 MACD_LINE / ATR |
|---|---|---|---|
| Units/meaning | Dimensionless own-history empirical rank | Dimensionless distance in local std units; own-history mean/std, no Gaussian tail probability | Dimensionless EMA spread in current range units; NOT own-history distribution rank |
| Primitive/version | rolling_empirical_midrank_v1 | rolling_zscore_ddof_v1 | positive_causal_scale_v1 + atr_wilder_sma_seed_first_high_low_v1 |
| Current-inclusive | Required by existing primitive; prior-only unsupported | Required by existing primitive; prior-only unsupported | Aligned current snapshots; no rank-reference inclusion convention |
| Readiness | contiguous last W slots, count>=m, every slot READY | Same plus nonzero finite variance | MACD and ATR READY, same symbol/timeframe/as_of/end; ATR>0; finite quotient |
| Ties/ddof | (less+.5*equal)/count; self included, exact equality | ddof0 or1 explicit, m>ddof; zero variance UNDEFINED; no rank ties | ATR period/min_history unselected; Wilder, SMA first-period TR seed; first TR high-low, later previous close gaps |
| Outliers | Magnitude less influential; W/occupancy/ties sensitive | Mean/std magnitude sensitive; self-inclusion can damp score | ATR shock can compress ratio; recursive denominator/history sensitive |
| Scale invariance | Strictly increasing scalar maps preserve rank apart from numeric effects | Positive affine scalar maps preserve score apart from numeric effects | Common positive OHLC unit scaling cancels numerator/ATR; no claim of affine-translation invariance with first-observation seed |
| Hash | Effective feature spec includes source projection, W/m/ties/include_current/continuity/missing policy | Effective spec includes source projection, W/m/ddof/zero variance/continuity/missing policy | Normalize effective spec nests MACD+ATR specs and alignment/positive-scale policy |

For every method, retain causal input hash and source vintage separately from
specification hash. MACD ScalarPoint known_at is the running maximum of all EMA
prefix arrivals; ScalarSeries rejects future points. FeatureResult has no explicit
known_at field: composition must retain max actual bar/scalar/action dependency
arrival, never substitute candle end or as_of. R3 requires actual arrivals of both
aligned operands. Internal continuity is not latest-expected-completion freshness;
real selector/action basis/mixed-profile join are still gaps. Unsupported/missing
or nonfinite inputs cannot be dropped into a shorter usable reference.
Primitive capability does not select conventions or a method champion.

## 15m observation clock, lookback and readiness

RTH_EXTENDED04:00–20:00 ET has **64 completed15m observations per standard
session**, versus16 completed1H. W counts completed selected15m observations,
never calendar minutes/hours/days. SHORT≈3–10 sessions, MEDIUM≈10–20, LONG>20;
these overlapping qualitative bands are not runtime windows or numeric choices.
**W320 is illustrative only: 320/64≈5 sessions at15m, versus320/16≈20 at1H.**
Frequency and role differ: 1H=context/setup; 15m=entry timing/reversal trigger.
Do not inherit percentile/W320/P05/negative polarity or K2 automatically.
Same transform permits implementation reuse. No early-close solution: extended
early-close/nonstandard dates remain V2-D_BLOCKER, never skipped/padded.

For current-inclusive full-window R1/R2 with m=W, M=130:
`N_first_ready=M+W−1`, zero-based first MACD index=M−1.
`macd_series` keeps M−1 NOT_READY slots; `_transform` takes `points[-W:]` and
fails if any slot unavailable. At N=M+W−2 the slice has W−1 READY plus one
warmup; at N=M+W−1 all W are READY. This is earliest readiness for contiguous,
finite inputs; R2 constant variance still UNDEFINED. Synthetic indexing fixtures
use small W only as test values, never selected strategy parameters.
W/m unresolved; partial windows need explicit audit (the current implementation
retains unavailable slots even when m<W). No numeric final N selected.
R3's aligned earliest computational bound is max(M, ATR.min_history), not M+W−1.

## Polarity, GC and zero-line matrices

| Polarity candidate | Predicate |
|---|---|
| POL0 | relative downside only |
| POL1 | relative downside AND MACD_LINE<0 |

Extreme-observation polarity and reversal-bar polarity are separate. GC may
occur after MACD is positive. H1-M15-RELATIVE-CONVENTIONS owns raw polarity;
H1-M15-GC owns GC zero-line; conjunction owns how retained extreme evidence is
bound to them. No sign choice is selected.

GC requires completed previous/current MACD and signal values, consecutive in
the selected observation grid and READY. No crossing across missing history.

| Candidate | Previous relation | Current relation |
|---|---|---|
| G1 STRICT_CROSS | prev_macd < prev_signal | curr_macd > curr_signal |
| G2 PRIOR_EQUALITY_ALLOWED | prev_macd <= prev_signal | curr_macd > curr_signal |

Both candidates exclude current equality. Whether to admit current equality is
an explicit unresolved freeze question, not silently built into G2. In test
algebra, negative previous spread→positive current satisfies both; zero→positive
only G2; positive→positive satisfies neither; current zero satisfies neither.
GC is CROSS_EVENT, not persistent BULLISH_MACD_RELATION (`MACD>signal`). Any
event memory belongs to C-layer. 0-line/sign/same-bar conditions are separate:

| Candidate | Zero-line meaning |
|---|---|
| Z0 NO_ZERO_LINE_RESTRICTION | No GC-event zero-line gate; extreme polarity separately chosen |
| Z1 | GC event MACD_LINE<0; extreme polarity separately chosen |
| Z2 | Extreme-observation MACD<0, GC-event unrestricted; constrains consistency with POL1 |

Z0+POL1 and Z2 can describe the same event semantics. Z2 is an explicit ownership
separation, not a new independent trial if behavior is identical. Below-zero
observation[0] is not a frozen requirement. None is selected.

## Price reversal family and separate exit ownership

| Candidate | Boundary | Parameters/delay/capability |
|---|---|---|
| PR0 UNUSED | Initial study uses GC branch only | No price branch; not false evidence fabricated from unavailable data |
| PR1 COMPLETED_PRICE_RECLAIM | Explicit reclaim using completed15m prices only | Reclaim reference/level/comparator unknown; prior-bar high/local reference high are illustrations requiring audit; H0001 predicate missing |
| PR2 CAUSAL_CONFIRMED_SWING_REVERSAL | Reuse existing causal confirmed-swing primitive | left/right widths needed; structural confirmation adds right-bar and actual delivery delay; H0001 mapping from confirmed swing to reversal missing |

[FractalSpec/confirmed_swings](../richping/research_v2/features/structure.py)
supports strict ties, positive left/right, extended continuity. confirmed_at is
max known_at of the full confirmation window; pivot_at cannot authorize a past
entry. A confirmed low alone has no frozen H0001 reversal mapping. No formula,
candle pattern or width is chosen. Entry reversal and exit HH/HL/LH/valid-HL
break have separate owners, even if they reuse the same primitive.

## Conjunction and temporal families

Notation D=relative downside evidence under selected temporal relation,
G=GC event, P=price reversal. Expressions name logical families; they do not
impose that the raw extreme still holds at the reversal bar.

| Candidate | Composition |
|---|---|
| T1 | D AND G |
| T2 | D AND P |
| T3 | D AND (G OR P) |
| T4 | D AND G AND P |

T3 is literal semantic fidelity only, not champion. PR0 fits T1; other pairings
need meaningful branch definitions. T4 must next freeze whether G and P are
same-bar or separately remembered, their ordering, evidence expiry and identity.
The C family does not silently decide G-versus-P coincidence.

| Temporal candidate | Extreme→reversal relation | Still unresolved |
|---|---|---|
| C0 CONTEMPORANEOUS | At reversal bar raw downside predicate still true | Equality/operand admission; no grace K |
| C1 EXTREME_ARMED_THEN_REVERSAL | Extreme creates short arming state; later reversal may qualify | expiry K, age anchor, same-observation admission, refresh/consumption/reset policy |
| C2 LAST_EXTREME_REFRESH_GRACE | Each new extreme refreshes last_extreme; allow reversal through K completed15m observations after extreme release | K, age boundary/inclusion, activation/refresh/reset/consumption/unavailable handling |

C1/C2 wording is intentionally bounded but not executable. Clarify whether C2
age counts from last extreme or first non-extreme at freeze; last-extreme refresh
is preserved as its candidate meaning. No numeric K or automatic1H K2 inheritance.
Same-bar requirement cannot be inferred from AND or r03; C0 is a candidate,
not the default. GC follows recovery toward signal, so rank can leave lower
tail before cross. C0 may exclude the observed extreme→recovery sequence;
long C1/C2 memory may approve stale extremes. This is a semantic tradeoff, with
no case-based latency fit or measured advantage.

## Causal timing, upstream coupling and initial-entry scope

Incomplete15m is forbidden for both GC and price reversal; previous/current
completed bars only. Future bars/ranks/pivots are forbidden. Delayed data creates
a current-known-at vintage, never a backdated opportunity. Past events rejected
while setup inactive cannot be queued or recycled on a later activation.

At the last15m constituent of an hour, that bar and new1H aggregate can share
one atomic known_at batch. [Replay](../richping/research_v2/replay.py) publishes
all batch members and aggregates before a single callback. This availability
contract does **not** select H0001 decision eligibility:

| Unresolved H1-DECISION-TIMING option | Meaning |
|---|---|
| A SAME_ATOMIC_BATCH | Newly ACTIVE1H episode and same-batch15m event may form a candidate after complete publication |
| B NEXT_15M_OBSERVATION | Newly ACTIVE1H is eligible only from the next new completed15m observation; same-batch event is rejected, never deferred |

Neither is selected. B means next completed observation identity, not next poll
or batch containing a vintage correction. Freeze/timing bundle must choose and
define delayed multi-observation batching/cadence explicitly; lexical order
inside a batch cannot supply priority. No change to frozen1H activation_at.

An actionable candidate needs setup ACTIVE **at decision as_of**, valid episode
ref/hash and current causal Daily refs. EXPIRED/CANCELLED/INACTIVE cannot approve
it. Daily BULLISH/NORMAL loss must first be propagated to the existing lifetime
evaluator, including between hour completions. Use one authoritative frozen
Daily snapshot per as_of join; retain its refs/hash rather than recompute a second
Daily formula. If refs/eligibility disagree or unavailable, suppress and trace.
This is a composer requirement, not an implemented new upstream classifier.
Whether extreme armed outside a setup can qualify inside a later active episode,
or setup activation resets arming, needs nested-conjunction freeze; old rejected
**reversal events** can never be reused. Avoid backdating or episode mixing.

Position-flat INITIAL_ENTRY only. Repeated GC before entry may produce separately
identified raw events; candidate duplicate/consumption policy remains to freeze
with timing/conjunction/global state owners. After a position exists a second GC
does not become add/reentry. Candidate creation does not prove a fill or position.
H1-ADD-POLICY/FAILED-REVERSAL/DEEPER-EXTREME/MAX-ADDS/H1-GC-ROLE remain unresolved.
No failed reversal, add, scale-in, re-entry,1H GC
confirmation/add role, risk or exit rule is designed here.

## Conceptual trigger matrix — no ranking

| Arm | r03 fidelity | Additional parameters | Expected delay (qualitative only) | Causal observability | Implementation capability | Multiple-testing cost |
|---|---|---|---|---|---|---|
| E0 NO_15M_TRIGGER_FILTER | Omits trigger; denominator/counterfactual only | No trigger parameters; matched downstream controls still needed | No trigger wait | Completed eligible opportunity, upstream availability retained | Counts possible; H0001 counterfactual composer missing | At most one optional comparator; counts in budget |
| E1 D+GC / T1 | Preserves GC branch, omits price branch | Relative/W/m/cutoff/sign, G/Z, C/K | Cross recovery plus selected memory | Two completed READY MACD/signal observations | Primitives available; predicate/composer missing | One branch; all choices preregistered |
| E2 D+price / T2 | Preserves price branch, omits GC | Relative tuple, PR reference/widths, C/K | Reclaim or swing confirmation | Completed reclaim or actual swing confirmed_at | Swing primitive available, H0001 rule missing | Adds reversal-definition dimensions |
| E3 D+(GC OR price) / T3 | Closest literal OR, unselected | Both branches plus temporal identities | First qualifying branch, conditional on memory | Both causal branches and statuses traced | Predicates/composer missing | More hypotheses and availability paths |
| E4 D+GC+price / T4 | Stronger than literal OR, unselected | Both branches plus G/P coincidence/order/memory | Wait for conjunction; no guaranteed ordering across arms | Requires explicit event timing and readiness | Branch memory/conjunction missing | Most composition dimensions within this family |

Delays are structural possibilities, never latency/return measurements or ranking.
E0 does not fabricate READY/extreme/reversal or imply a live strategy.

## Search guard, denominators and trace requirements

Do not test method×W×threshold×polarity×G×Z×PR×T×C/K Cartesian product.
Next freeze fixes one small initial tuple, optionally one comparator (E0 counts).
Relative-method and trigger-composition questions remain separate. Do not also
cross Daily/1H families in that initial comparison. Changed/added variants after
viewed results require new revision/preregistration and independent confirmation.

| Denominator group | Required future counts/diagnostics |
|---|---|
| Raw15m | total eligible completed15m; MACD READY; relative READY; UNAVAILABLE; DOWNSIDE_EXTREME; INACTIVE |
| 1H overlap | setup ACTIVE observations; extreme inside/outside active setup |
| Reversal | GC; price reversal; both same-bar; GC-only; reversal-only; neither; operand-unavailable separately |
| Temporal | activation; refresh; armed duration; latency from last extreme in completed observations; expiry |
| Candidate | initial candidates; 1H-inactive rejection; changed Daily rejection; unavailable suppression; duplicate/retrigger suppression |
| Later, not queried now | completed entries; no-entry episodes; MAE/MFE/forward returns; sample and availability suppression; PENDING/UNRESOLVED/missing labels+reasons |

Use stable opportunity identity and same prefilter denominator, data/universe/
Daily/1H/downstream/cost controls. Sample suppression=READY-filter rejection;
availability suppression=missing/unavailable operands, reported separately.
Keep source vintage as evidence; revisiting a completed source identity does not
advance the observation clock. Freeze explicit event/candidate dedup policy so
polling or corrected vintages cannot inflate the denominator or repeat an entry.
Zero denominator=null. Reversal partition applies only to joint READY event
operands; PR0 is UNUSED, not false/unavailable. Both same-bar is a diagnostic,
not a T4 rule. Preserve rejection reason sets and their union to avoid duplicate
totals. Common-availability comparison and coverage diagnostics require separate
preregistration. Recommendation return/cohort drawdown is not account performance.

Proposed trace schema `h0001_initial_entry_trigger_trace_proposal_v1` (not logger):
symbol, as_of, source_15m_end/known_at, macd_line, signal_line (plus previous
values/identity), relative_value, relative_method/version/hash, threshold/
comparator, raw_downside_state/status/reason, GC event state/definition version/
hash, price reversal state/definition version/hash, temporal armed state,
last_extreme_at, reversal_at, latency_observations, conjunction_result,
1H setup episode ref/hash, Daily permission refs/hashes, candidate_type=INITIAL_ENTRY,
trigger contract version/hash, causal input hash, source vintage. Also retain
extreme source-end versus actual-known-at identities, batch/ref timing choice,
position-flat evidence/ref, rejection/duplicate reason and candidate identity.
Historical trace/snapshots immutable; later outcomes separate. Order/fill records
have distinct owners and are not fields inferred from this proposal.

## Implementation capability and decision-ID ownership

| AVAILABLE actual code | MISSING / H0001-specific |
|---|---|
| Completed15m/grid/continuity/ReplayContext; MACD12/26/9 line/signal/histogram | 15m relative classifier; GC predicate; price reversal predicate |
| Percentile/z-score/ATR/normalize/readiness/spec+input hashes | Temporal arming evaluator; conjunction evaluator; event/candidate logger |
| Atomic known_at replay; causal confirmed swings; immutable StrategyState/DecisionTrace | 1H+15m composer; mixed-profile Daily join/freshness/action selectors; entry order/fill logic |

Primitives are synthetic research capabilities, not a real-market H0001 plugin.
No trading implementation/schema migration is added; only proposal/docs/tests.

| Existing ID | Proposed semantic ownership |
|---|---|
| H1-M15-RELATIVE-METHOD | R1/R2/R3 transform |
| H1-M15-LOOKBACK | W observation window |
| H1-M15-RELATIVE-CONVENTIONS | MACD_LINE field, m/reference/ties/ddof/ATR settings/readiness/continuity/raw polarity |
| H1-M15-DOWNSIDE | Numeric cutoff and transform units |
| H1-M15-COMPARATOR | LT versus LE threshold equality |
| H1-M15-GC | G1/G2, current equality, event identity, event zero-line restrictions; no persistent relation |
| H1-M15-REVERSAL | PR0/PR1/PR2 and exact causal price rule/reference/widths/confirmation |
| H1-M15-CONJUNCTION | T1–T4 plus nested C0–C2, K/unit/age/expiry/refresh/unavailable/episode binding, G/P event ordering/coincidence/consumption |

Nested typed contract parameters can track these semantics with the existing
contract root; no new executable ID/path is needed in this proposal.
H1-DECISION-TIMING remains global atomic-batch eligibility/entry cadence owner;
H1-STATE-TRANSITIONS owns global position transitions; add/reentry and exit/risk
owners stay separate. No invented standalone temporal decision. Contract
freeze must encode nested values explicitly rather than bury them in prose.

Actual parser at basis/after: **78 decisions,16 resolved,62 unresolved IDs,
C1 38, performance17, optional7,89 unresolved paths**. All eight target IDs,
timing/1H GC/add/reentry/state transitions remain UNRESOLVED. Canonical v11
selected values/hash and r03 remain unchanged; comments only add proposal refs.

## Bounded next-freeze alternatives and checklist

Structural alternatives to consider, **not selected or ranked**:
A: MACD_LINE percentile + negative extreme polarity + GC branch + short
temporal grace. B: same relative concept + GC OR price-reversal branch + short
temporal grace. These are reduction guidance, not champions excluding R2/R3
or selecting POL1/C1/C2. Exact W/m/cutoff/K/G/Z/PR definitions remain unknown.

Next freeze must choose method; W/m/reference/ties/ddof or ATR period/history;
cutoff/comparator; extreme and event polarity; G/current-equality/Z; PR and exact
completed reference or swing widths/mapping; T plus G/P coincidence; C/K age
anchor/expiry boundary/refresh/unavailable/recovery/consumption/episode binding;
position-flat evidence/duplicate policy; immutable trace and denominator/trial
budget. Timing bundle must choose same-batch vs next-observation and delayed
batch handling without changing1H freeze. Execution price/order/fill, add/reentry,
exit/risk and full data/universe/splits/costs/capital/metrics/null/pass-reject/
purge/embargo registration remain separate prerequisites for performance work.
Contract tests verify preservation and causal design boundaries only; they do
not demonstrate profitability or economic validity.
