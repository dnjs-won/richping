# H0001 Daily PRICE_REGIME / TREND_PERMISSION decision proposal

Basis: `v2-c0-extended-session-contract` at
`63b815598576c2bd8a865adb503e193ff9e9f664`, inspected on 2026-10-01.
**H0001 DRAFT; profitability NOT TESTED; chart parity UNVERIFIED.**
This proposes a small family, not a selected Daily rule or an experiment.
Machine-readable companion: [proposal YAML](../research/decision_proposals/H0001-daily-price-regime-v1.yaml).
The initial proposal preserved the hypothesis and executable v5 spec at its basis.
The subsequent [DAILY-INPUT audit](H0001_DAILY_INPUT_CONTRACT.md) adds two unresolved
input contracts in v6; the original r03 and DLP-A/B/C proposal remain unchanged.

## Research boundary and repository investigation

Daily means this asset's **price-derived LONG permission**, not MARKET_REGIME
or MACRO_REGIME. Rates, oil, dollar, sector leadership, fundamentals and options
flow are separate future states/features and interaction hypotheses. Neither
"rising rates means bearish technology" nor knowledge of the 2026 AI/semiconductor
rally enters these definitions. The proposed states cannot explain the whole
market. [Research Capture](RESEARCH_CAPTURE.md) remains authoritative for
revision, provenance and discovery/confirmation separation.

The earlier investigation incorrectly generalized a local object/history search
into a claim that `docs/RESEARCH_PHILOSOPHY.md` did not exist in repository history.
The document exists at `91eff1f2ef9943c9077f79811c651a1455803e67` and has now been
imported byte-for-byte from that Git blob, without merging or cherry-picking the
branch. [Research Philosophy](RESEARCH_PHILOSOPHY.md) is the actual contract.
The [DAILY-INPUT audit](H0001_DAILY_INPUT_CONTRACT.md) records provenance and its
compatibility audit; no original philosophy text was rewritten.

Investigation covered PROJECT_STATUS.md, RESEARCH_CAPTURE.md, H0001 r01/r02/r03,
the complete executable draft, C0 specification/inventory/admission and tests,
V2-A/B implementation notes, sessions/aggregation/replay/context contracts,
EMA/MACD/relative/volatility/confirmed-swing primitives and continuity tests.
The actual basis diff adds an independent unresolved Daily decision, scopes
H1-SESSION to intraday, checks Daily continuity independently, and adds causal
Daily tests. It selects no Daily price predicate.

### Observation audit: Daily semantics cannot be established

| Repository evidence | What it establishes | What it does not establish |
|---|---|---|
| r01/r02 `rules.regime`, `unknowns`, `required_data` | Daily rising context was discussed; mathematical definition and sessions unknown | Daily candle boundaries or close feed |
| r03 `source` | Chat on 2026-09-25; reference and issue null | Provider, chart settings, timezone, Daily price adjustment |
| r03 `timeframes.regime`, `required_data[3]` | Daily OHLCV / time-aligned Daily state required | RTH versus full extended aggregation |
| r03 `unknowns[25]`, `required_data[8]` | Session choice requires an explicit decision | Premarket observation proving extended Daily |
| r03 observations; empty `evidence_refs` and `experiment_refs` | NOK / Sep 23–25 SOXX anecdotes are discovery | Timestamped source Daily candles, chart exports or independent confirmation |
| v5 `chart_parity` | Provider/boundary/seed/history/evidence unresolved, status UNVERIFIED | Synthetic agreement proving observed-chart parity |

The tracked research/docs inventory has no original screenshot or chart export
with Daily configuration. There is no repository evidence to resolve the Daily
session. **H1-DAILY-SESSION = UNRESOLVED**, candidates **RTH_DAILY / EXTENDED_DAILY**.
The engine's ability to aggregate extended Daily and the fact that intraday
examples include premarket do not identify the observed Daily chart. No provider
or vendor default is guessed and no external source substitutes for missing
observation provenance.

## Two causal Daily series

| Semantics | RTH_DAILY | EXTENDED_DAILY |
|---|---|---|
| Profile / boundary | XNYS_RTH, official open through official close; normally 09:30–16:00 ET | US_EQUITY_EXTENDED_04_20, 04:00–20:00 ET on supported standard XNYS dates |
| Base inputs | Every expected 15m RTH interval, normally 26 | All 64 expected 15m extended intervals |
| Completion / availability | No Daily until official close **and every expected input delivered** | No Daily until 20:00 **and every expected input delivered** |
| known_at | Maximum constituent known_at, which may be later than official close | Maximum constituent known_at, which may be later than 20:00 |
| MACD/EMA close | Last constituent's RTH close at official close; no after-hours value | Last 19:45–20:00 constituent close, including after-hours |
| DST | America/New_York local anchors; normally close 21:00 UTC winter / 20:00 UTC summer | Local 04:00–20:00; close 01:00 UTC next day winter / 00:00 UTC next day summer; session label stays ET date |
| Holiday/weekend | No XNYS session/candle; next trading observation is adjacent | Same XNYS session-date calendar, no invented holiday candle |
| Early close | Official calendar close, e.g. 13:00 ET; all expected constituents required | Entire nonstandard/early-close date unsupported, including premarket; spanning dataset fails closed |
| Continuity | xnys_completed_grid_v1 | us_equity_extended_04_20_completed_grid_v1 |
| Aggregation | xnys_open_anchored_short_final_v1 | us_equity_extended_04_anchored_full_session_v1 |

These are implemented **synthetic research grids**, not verified vendor Daily
prices, consolidated closing auctions, liquidity or corporate-action coverage.
Missing inputs never become a partial Daily; delayed repair may produce the
older Daily only when evidence arrives. At intraday time t, a usable Daily is
the latest completed **and delivered** candle subject to an explicit future
freshness policy. Yesterday's Daily is not today’s incomplete candle. A missing
whole current session cannot silently be interpreted as a holiday.

Intraday 15m/1H remains RTH_EXTENDED. Daily selection is independent in v5's
`daily_session_policy`, whose unresolved C1 blocker prevents freeze/C1_READY.
The admission fixtures can explicitly select either Daily profile while keeping
extended intraday. This is readiness to implement, not a combined data engine:
current replay uses one manifest-selected profile and ReplayContext rejects
mixed profiles. A future RTH Daily + extended intraday plugin needs separately
profiled causal views joined by as_of, explicit vintage/input hashes and same
known_at atomicity; that adapter is a documented gap, not implemented here.
Generic extended Daily remains available. Resolving Daily is distinct from
verifying observed chart semantics; a deliberate new research series may be
chosen while historical parity remains UNVERIFIED.

**V2-D_BLOCKER remains:** extended early-close availability is not specified.
It prevents some long contiguous histories and still affects extended intraday
even if Daily is RTH. No exceptions, skipped sessions or history-gate relaxation
are introduced. Out-of-calendar dates fail rather than extrapolate.

## Small candidate matrix

Notation: t indexes **completed Daily observations in the selected session**,
C_t is that candle's close, E_n,t is first-observation recursive close EMA using
the entire available contiguous history through t. n (span), h (EMA minimum
history), k (observation lag), L/R (fractal widths) are positive integers still
to be supplied. h is **not automatically MACD's 130**; 12/26/9 are MACD facts,
not a choice of price-trend spans. Inputs must also have known_at <= as_of.
All formulas below are strict-comparison **proposals**, never applied rules.

| ID / family | Causal definition | Parameters still required | Existing capability / remaining gap | What state it classifies | Leakage / overfit risk | H0001 evidence |
|---|---|---|---|---|---|---|
| DLP-A / EMA level | C_t > E_n,t | n, h; shared origin/price basis/freshness | EMASpec + ema + completed close available; comparison/classifier and C1 rule registration absent | Price above its smoothed level, including reclaim while the average is still falling | Current incomplete Daily; future-adjusted price history; seed/origin and period cherry-picking | r03 requires rising Daily context but gives no MA formula: NEW RESEARCH VARIANT |
| DLP-B / level + slope | DLP-A AND E_n,t > E_n,t-k | Same n/h as A, one positive observation lag k | ema on current and earlier detached causal prefixes; no new indicator needed; difference/conjunction/readiness classifier absent | Above the smoothed level **and** that level rose over k observations; separates falling-average reclaim from rising-average context | Future-fitted slope, calendar-day lag, changing origin between prefixes, selecting k after SOXX outcomes | No recorded Daily slope condition: NEW RESEARCH VARIANT |
| DLP-C / confirmed price geometry | Latest confirmed high has label HH AND latest confirmed low has label HL AND C_t > latest confirmed low price | L, R; common freshness/origin; strict ties and strict close break are proposed conventions | FractalSpec + confirmed_swings + classify_swings + completed close available; persistent Daily predicate/readiness and C1 registration absent | Rising latest confirmed high/low with current close still above that low; delayed geometry rather than MA position | Backdated pivots, future right bars, pivot-width search, silently skipping gaps, inferring discretionary valid-HL associations | r03 HH/HL directly concerns 15m HOLD/exit; transferring it to Daily is NEW DAILY VARIANT, not observed Daily proof |

A supplies the simplest level reference. B is one nested ablation asking whether
direction of that same average changes the classification; adding only k keeps
that question identifiable. C supplies one structurally different interpretation
of "rising" using existing causal geometry. Thus three variants across two
families; no standalone slope-only, dual-MA chain, SMA alternative, MACD
zero-line/cross, MA + swing conjunction, RSI/ADX or threshold zoo is admitted
to this initial proposal. This is a proposed research bound to freeze, not an
irrevocable rejection of other independent hypotheses. Existing code did not
select an algorithm: all three lack a strategy evaluator, and missing SMA or
alternative swing detectors is not filled before a research decision.

### Readiness, ordering and falsifiability

- A requires the whole visible calculation history contiguous and >=h completed
  inputs. B requires both EMA prefixes ready (>=h+k inputs for the later prefix),
  with one fixed origin/convention and k counted in observation steps. No
  full-future fit or centered regression is used. Operand known_at and actual
  input hashes must be retained; current result cannot be stamped onto t-k.
- C uses only events confirmed_at <= as_of, ordered by
  `(confirmed_at,pivot_at,kind)`. Compare latest events of each kind to their
  previous same-kind event, without silently imposing alternation or a
  discretionary reference-HH/valid-HL association. At least two highs and two
  lows must exist to classify both; a first null classification is UNAVAILABLE.
  EQH/EQL does not satisfy HH/HL. Equality at the close/low is not permission
  under this strict proposal. Both kinds may confirm together on an outside
  candle; neither overwrites the other.
- Fractal READY can mean a tested window with **no** pivot; local contiguous
  windows can coexist with gaps elsewhere. C therefore additionally requires
  full calculation-history continuity and enough classified events; primitive
  READY alone does not certify a bullish state or complete coverage. This
  composition check is a future classifier gap. Unconfirmed future pivots
  cannot be substituted for missing events.
- Any not-ready/undefined operand yields an unavailable axis with its reason,
  not false/NOT_BULLISH or NORMAL by default. The three formulas classify
  price context; they do not estimate probability, promise return or place
  orders. Once n/h/k/L/R and data protocol are frozen, each state is reproducible
  from a causal prefix and each candidate can be falsified under a separately
  predeclared metric/null; those experiment choices remain unknown.

### MACD redundancy and comparison control

EMA and MACD share closes and smoothing, so selecting a trend subset changes
the conditional distribution of 1H/15m relative-MACD setups. Dual fast/slow EMA
ordering with the same spans is algebraically MACD-line >0; it would add a
duplicate gate, not independent evidence. No Daily MACD rule is added here.
C's geometry also shares price inputs and is not statistically independent.
Future diagnostics must distinguish state occupancy, availability, eligible
setup denominator, signal count and conditional outcomes; do not report an
apparent improvement produced only by suppressing observations. Keep excluded,
unavailable and no-signal denominators, not only successful trades.

Before any experiment, freeze a canonical proposal snapshot/hash plus an
approved subset of IDs, exactly one manually justified parameter tuple per
retained family (A/B share n/h), session treatment, baseline, discovery/holdout,
costs, sample unit, primary metric/null/decision rule and trial budget. This
proposal has **no numeric sweep bounds or selected tuple**. If both sessions
and all three candidates are compared, that is up to six structural variants
before blocker/policy variants; each additional tuple or action is another
trial, including failed/inconclusive trials. Do not silently search their
Cartesian product. Freeze which comparisons are included and which are deferred;
adding a family or tuning after results requires new provenance/revision under
RESEARCH_CAPTURE. Family freeze is distinct from executable FROZEN/C1_READY.

NOK and already observed SOXX Sep 23–25 and Sep/Oct 2026 cases, plus contemporary
AI/semiconductor narrative knowledge, are discovery/exposure, never untouched
confirmatory evidence. No chart inspection, performance scan, backtest or data
download was performed to choose these candidates.

## Independent state proposal, with policy kept separate

| Axis | Proposed vocabulary (not selected) | Meaning / definition owner |
|---|---|---|
| daily_trend_permission | BULLISH / NOT_BULLISH / UNAVAILABLE | Raw price-context classification, H1-DAILY-LONG; NOT_BULLISH is not a short permission |
| daily_exhaustion_state | NORMAL / EXTENDED / UNAVAILABLE | Relative upper extension state, H1-DAILY-BLOCKER; no threshold, method or action selected |
| daily_price_shock_state | NORMAL / ADVERSE_SHOCK / UNAVAILABLE | Optional price-only adverse discontinuity/drawdown state; new research inclusion/definition unresolved |

Store a product of axes, not one enum or priority overwrite. Proposed per-axis
record fields are `state, status, reason, input_end_at, known_at, input_hash,
feature_specification_hash, session_profile`; the snapshot also records symbol,
as_of, Daily series identity and proposed schema/version. The existing immutable
StrategyState/JsonObject transports this without a new schema implementation.
The vocabulary and fields are **a proposal only**, not a validated H0001 runtime
payload or calculated classifier. Generic transport tests cannot approve a
threshold or establish that a state is economically meaningful.

For example, `(BULLISH, EXTENDED, NORMAL)`, `(BULLISH, NORMAL, ADVERSE_SHOCK)`
and `(BULLISH, EXTENDED, ADVERSE_SHOCK)` are all representable. Updating shock
must not delete trend/exhaustion. Unavailable exhaustion or shock likewise
cannot erase a ready bullish classification or pretend NORMAL. Missing input
and a deliberately deferred classifier are separately explained by reason;
an unknown definition is UNRESOLVED before calculation, not measured NORMAL.

A separate policy would map this vector to final new-LONG permission and
signal-lifecycle actions. **All action/priority/freshness/reset choices remain
unresolved.** No OR/AND policy or automatic block/reduction is chosen. Reducing
exposure depends on the separate execution/capital layer; current C1 cannot
silently import unresolved sizing. No threshold-triggered state or action is
implemented in this step.

Exhaustion evidence exists only as r03's direction to consider a separate upper
relative MACD blocker, not a measured crash forecast. Price shock could later
measure an adverse close return, gap or drawdown from **previously known** price,
with scale/readiness/window/direction fixed before testing. These are gap notes,
not additional active indicator candidates. No price shock formula, numeric
cutoff, horizon or inclusion is selected. Proposed NORMAL would mean only that
a chosen predicate was not met, not zero future crash risk. A macro announcement, oil/rate shock
or options narrative belongs in separate state layers, never this price axis.
If shock changes H0001 behavior, first capture it as an explicit research variant
and review the hypothesis/spec revision and mandatory decision inventory.

## Decision inventory and three next bundles

**Original trend proposal only: new executable decision IDs 0 / unresolved paths 0.**
At this proposal's basis, executable inventory was 76 decisions, 71 unresolved IDs (47 C1 / 17
performance / 7 optional), 98 unresolved paths and v5 hash
`ab0c1136d47bf1ce6b46ff7e46824b59cf715d28db93bf665b77477a8f0a50e6`.
Current v6 inventory is 78 decisions / 73 unresolved IDs (49 C1, 17 performance,
7 optional) / 100 paths, solely from the two DAILY-INPUT blockers; see the audit.
The sidecar's UNRESOLVED paths are proposal questions, not executable blockers;
its bundle lists enumerate them explicitly. No resolved contract is weakened.
H1-DAILY-SESSION, H1-DAILY-LONG and H1-DAILY-BLOCKER remain unresolved.

1. **DAILY-INPUT:** choose RTH_DAILY or EXTENDED_DAILY deliberately for research
   (or preserve unresolved pending source evidence); record origin/price basis
   and freshness policy. To claim reproduction, supply observed provider/settings,
   timestamped Daily candles and initialization/adjustment evidence. Existing IDs:
   H1-DAILY-SESSION, H1-CHART-PROVIDER/EMA/VERIFICATION, H1-DECISION-TIMING.
2. **DAILY-TREND:** approve the bounded comparison subset among A/B/C, or select
   one ex ante with rationale; provide n/h and k if needed or L/R for C, agree
   strict/equality/readiness semantics, freeze the shared parameters and protocol
   before outcomes. Existing H1-DAILY-LONG and experiment-design IDs own these
   choices. No question asks for the best fit to today's SOXX chart.
3. **DAILY-AXES-POLICY:** define exhaustion separately and explicitly defer or
   specify a price-shock variant; confirm the product representation, unavailable
   behavior, final entry action and signal lifecycle. Existing H1-DAILY-BLOCKER,
   H1-DECISION-TIMING and H1-STATE-TRANSITIONS own the current core. Shock effect
   would require a future explicit decision/revision rather than being hidden
   in Daily LONG. Sizing/exposure remains a separate later bundle.

The next researcher can fill these bounded questions without adding indicators
or reconstructing the design. An approved proposal freeze still is not a
completed C1 plugin, historical parity, paper performance or evidence of alpha.

## Verification boundary

Existing tests already cover independent sessions, unresolved Daily C1 failure,
distinct causal Daily input hashes, delayed/incomplete Daily availability,
extended 15m/1H, DST, holidays/early closes and immutable causal prefixes.
New proposal-level tests use the existing state transport to preserve all
trend/exhaustion/shock combinations, independent updates and unavailable reasons,
and verify no executable-spec/hypothesis decision has changed. Additional Daily
availability tests include missing and delayed RTH/extended last constituents.
No candidate evaluator, new primitive or production/paper behavior is added.

Full suite: **763 passed in 154.02s**, no failures, skips or pytest warnings.
The prior 730 tests are unchanged. Added 33 cases: 27 product-state combinations,
four missing/delayed Daily cases and two proposal/inventory checks. Focused
proposal + prior Daily-session suite: 39 passed. `git diff --check` passes.
No diff in runtime, hypotheses, executable spec or the prior V2-A/B/C0/extended
test files; the default main worktree's pre-existing changes are preserved.
