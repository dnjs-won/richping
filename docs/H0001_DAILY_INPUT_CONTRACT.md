# H0001 DAILY-INPUT semantic freeze v1

Freeze basis: `382bd202ed394fbe5b2247af0752a4d29efaaa26` on
`v2-c0-extended-session-contract`. H0001 remains **DRAFT**, profitability
**NOT TESTED**, chart parity **UNVERIFIED**. No DLP-A/B/C rule, parameter,
ranking, champion or experiment is selected. [Input proposal YAML](../research/decision_proposals/H0001-daily-input-v1.yaml)
preserves the original unresolved proposal byte-for-byte. The new
[immutable decision record](../research/decision_records/H0001-daily-input-freeze-v1.yaml)
records the user/researcher choices, rationale and capability gaps; executable
`h0001_r03_spec_v7` carries the versioned input contracts. The earlier audit was
based on `4d5d74f716d013e89536955ebe25c2e2c81b43f5`.

| Decision | Status | Frozen choice |
|---|---|---|
| H1-DAILY-SESSION | RESOLVED | RTH_DAILY |
| H1-DAILY-PRICE-BASIS | RESOLVED | PIT_SPLIT_ADJUSTED_OHLC |
| H1-DAILY-FRESHNESS | RESOLVED | LATEST_EXPECTED_COMPLETED_SESSION_REQUIRED |

This resolves only `daily_trend_permission` input semantics. It selects no
BULLISH formula, exhaustion, price shock, macro, sector leadership, options,
fundamentals or final trade permission. No performance data, current SOXX chart,
candidate ranking, trend parameter selection or backtest informed these choices.

## Philosophy provenance correction and audit

The authoritative [RESEARCH_PHILOSOPHY.md](RESEARCH_PHILOSOPHY.md) exists at
commit **91eff1f2ef9943c9077f79811c651a1455803e67** in `dnjs-won/richping`.
That object had not been fetched in the prior local investigation. A search of
local branches/history could not establish its absence from GitHub. The prior
statement that the document did not exist in the repository/history was too
broad and is corrected in the Daily research note and PROJECT_STATUS.md.

Fetched only the source commit object and copied **only this file's exact Git
blob bytes**, without merging or cherry-picking any branch/commit and without
rewriting the document. Imported file SHA-256:
`e5a88b9d89273591a0655c116ee38b6e1ae7059ed7c39e9248408f4cf64429c8`.
Tests pin the original blob digest (allowing Git's normal Windows checkout EOL
conversion), without requiring that unrelated source commit to exist in a fresh
checkout. The imported/staged blob is also compared directly with the fetched
original; the initial copy itself is exact. Source: [pinned original](https://github.com/dnjs-won/richping/blob/91eff1f2ef9943c9077f79811c651a1455803e67/docs/RESEARCH_PHILOSOPHY.md).

| Original principle | Audit of the current Daily proposal |
|---|---|
| §§1,3: PRICE_REGIME / TREND_PERMISSION is not MARKET_REGIME or MACRO_REGIME | DLP conditions describe asset price only; no broader market/causal claim |
| §§2,7: conflicts carry information | Trend, exhaustion, price shock and future macro/leadership/options/fundamental axes are separate; no overwrite or implied hierarchy |
| §1: narrative is not causal fact | No rates→technology veto or inferred options/macro cause |
| §§4,5: historical leadership needs PIT universe/selection | No retrospective 2026 semiconductor leader selection; SOXX-specific observations cannot prove historical leadership discovery |
| §§6,9: new data requires defensible known_at and independent evidence | No current/restated fundamentals or future corporate-action vintage injected into past states |
| §9: complexity needs incremental value over a simpler price-only baseline | A is a level reference; B is its bounded slope ablation; C is a separate geometry variant. Any future layer needs preregistered incremental-value evidence, costs/turnover when applicable, and failed/inconclusive trial retention |

The original diagram describes conceptual research layers, **not automatic
causal dependencies or macro-first permission**. None of its examples authorizes
new H0001 behavior. No substantive conflict was found; provenance and the
incremental-value requirement are now explicitly linked. The earlier trend
proposal remains PROPOSED_NOT_FROZEN, including all its original parameters.

## Separate series roles

**OBSERVED_CHART_SERIES** is the actual past Daily chart used in discussion.
Its provider, session, price adjustment and initialization are unverified;
repository r01/r02/r03 contain no settings or timestamped Daily export proving
them. No external provider default fills this gap.

**RESEARCH_DAILY_SERIES** is a deliberately specified causal research series.
H1-DAILY-SESSION now selects RTH_DAILY **without proving chart parity**.
This is an explicit new versioned research choice, authorized by the user's
semantic freeze instruction. The decision record preserves source/rationale;
future actual input records must preserve data/action vintage and input/spec
hashes. It does not claim "the observed strategy was reproduced". Hypothesis
revision rules still apply when behavior/experiment contracts change.

Research series identity is `(role, symbol, session_profile, price_adjustment
convention, input_contract_version, source_vintage)`. Sharing the word Daily,
symbol or session label cannot establish equality. Session and adjustment are
independent choices. The three Daily input decisions are now **RESOLVED**.
Historical-reproduction
readiness continues to require verified chart parity; C1 readiness requires
complete declared input contracts, not a claim of observed chart matching.

## A–G audit against actual implementation

| Item | Existing contract/code | Audit result / owner |
|---|---|---|
| A session | Independent daily_session_policy / require_daily_session_capability; generic session profiles | RTH_DAILY resolved under H1-DAILY-SESSION; intraday remains RTH_EXTENDED |
| B completion/known_at | MarketBar requires end_at <= known_at; CompletedAggregator needs every expected constituent and end <= as_of; ReplayContext rejects future bars; replay batches equal known_at atomically | Already decided generic causality. Reuse it; no extra decision ID |
| C freshness | Features check internal continuity only; latest visible prefix need not include latest expected completed session; no freshness selector | Strict expected-session equality resolved; selector is V2-D/C1 capability gap. H1-DECISION-TIMING still owns callback cadence/action coordination |
| D price basis | MarketDataset admits only SYNTHETIC + synthetic_unadjusted + NONE_CONFIRMED; features reject unknown/present actions | PIT_SPLIT_ADJUSTED_OHLC resolved; real action transform/source is V2-D gap; existing synthetic restriction unchanged |
| E dates/calendar | session_date / session_bounds use America/New_York; calendar/version provenance in replay | Reuse H1-DAILY-SESSION and versioned generic profiles; no extra timezone decision |
| F missing/delayed | Missing constituents do not emit Daily; internal gaps give NOT_READY; delayed repair arrives at actual known_at | Input availability/reason remains separate from price classification; no missing→NOT_BULLISH conversion |
| G provenance | MarketBar retains session, known_at, dataset_id and provenance; FeatureResult retains symbol/timeframe/as_of/input_end/count/hash/spec | Transport can retain all requested fields, but no Daily state builder exists; explicit session/basis/known_at/series role and vintage linkage need composition, not a claimed implemented classifier |

No production/paper, price transform, replay, selector, indicator or classification
behavior changes. Only executable **specification inventory/admission validation**
adds v7 profile readability; declaration readiness is not an
implemented data adapter or policy evaluator.

## Session rationale and mixed timeframe semantics

Daily is H0001's slow PRICE_REGIME / TREND_PERMISSION axis. 1H/15m already use
RTH_EXTENDED (04:00–20:00 ET). Extended Daily could strongly reflect the same
after-hours information in both upper and lower frames. Official RTH session
close gives a simpler, reproducible Daily reference. This is a semantic choice,
with **no claim that RTH predicts better than extended**. EXTENDED_DAILY remains
a generic capability and may be researched in a separate versioned variant.

Daily uses RTH_DAILY + PIT_SPLIT_ADJUSTED_OHLC + strict expected-session freshness.
1H/15m retain their distinct extended identities. At 06:00 ET, the previous
completed RTH Daily is the upper price regime; current premarket movement
exists only in intraday layers. At/after official RTH close, the current expected
Daily is required: replace the older input when the new one is causally available;
until then the Daily axis is UNAVAILABLE. No earlier-Daily fallback is eligible.

Do not concatenate these into one candle stream. Preserve each Daily/1H/15m
identity, known_at and causal input hash separately and join only at as_of.
The Daily choice does not select a real intraday corporate-action basis.
The mixed-profile causal adapter remains **NOT_IMPLEMENTED**.

## Session/completion facts preserved

- **RTH_DAILY:** official XNYS open–close, normally 09:30–16:00 ET, 26 expected
  15m constituents. On early closes use the official close (e.g. 13:00), not a
  synthetic 16:00 candle. Close input is the last RTH constituent close.
- **EXTENDED_DAILY:** 04:00–20:00 ET on supported standard XNYS dates, all 64
  constituents; close is the final 19:45–20:00 constituent close. No partial
  Daily, and no implication about a vendor auction or execution feed.
- Daily bar known_at is `max(constituent.known_at)`, which can be later than
  candle end. A future transformed state must also include action/transform
  evidence known_at; it cannot use the original price timestamp if adjustment
  evidence arrived later. Current engine transforms no real actions.
- Anchors are local America/New_York and UTC timestamps are aware. Normal RTH
  close is 21:00 UTC winter / 20:00 summer; extended close is 01:00 UTC next day
  winter / 00:00 next day summer. session_date remains the ET trading date.
  DST does not add observation steps. Weekends/XNYS holidays have no candle.
- **V2-D_BLOCKER unchanged:** extended v1 rejects the entire early-close or
  nonstandard date and datasets spanning it. It must not be skipped as a holiday.
  Required extended intraday means RTH Daily selection does **not** remove this
  prerequisite before a multi-year H0001 replay. Out-of-calendar dates fail.
- Independent Daily/intraday selection is a spec contract; current replay
  remains single-profile and rejects mixed-profile contexts. A separately
  versioned as_of view join is still an implementation gap.

## Strict freshness contract and completion boundary

For a supported chosen profile and as_of, **expected_completed_session** is
the latest session whose scheduled profile close <= as_of. Separately retain
**available_completed_session**, the latest completely delivered Daily at as_of.
The latest causally delivered Daily's session_date must **exactly equal**
`latest_expected_completed_daily_session(as_of)` on the selected RTH_DAILY
calendar. No numeric lag/grace applies. Mismatch or absent input yields Daily
axis **UNAVAILABLE**, never NOT_BULLISH; a new H0001 decision does not satisfy
Daily permission. Keep the reason and coverage evidence separate from price state.

| Fact relation | Meaning, independent of any numeric tolerance |
|---|---|
| LATEST_EXPECTED_COMPLETED | Available and expected session match |
| BEHIND_EXPECTED_COMPLETED | Available is an earlier trading session; retain session-lag count and reason |
| NO_COMPLETED_INPUT | No delivered completed Daily exists; unavailable, not NOT_BULLISH |
| UNSUPPORTED_SESSION | Calendar/profile cannot supply a valid expected-session contract; fail closed, not a holiday |

| as_of (ET) | Expected session | Eligible input / boundary |
|---|---|---|
| 10/01 06:00 or 08:00 | 09/30 | Delivered 09/30 is FRESH; current premarket belongs to intraday |
| 10/01 15:00 or 15:59:59 | 09/30 | Delivered 09/30 is FRESH, not stale |
| 10/01 exactly 16:00 and later | 10/01 | Official scheduled completion uses close <= as_of. If delivery/required evidence is absent, UNAVAILABLE; no 09/30 fallback |
| 10/01 after actual full delivery/transform known_at | 10/01 | Causally available 10/01 becomes FRESH; no partial or future-known input |
| Weekend 10/04 | Friday 10/02 | Calendar's previous completed trading session; no calendar-day lag |
| Holiday 09/07 | Friday 09/04 | No holiday candle or stale-hours test |
| Early close 11/29/2024 at 13:00 | 11/29 | Official RTH close is the completion boundary; if undelivered, UNAVAILABLE |

Examples use calendar facts and contract fixtures, not a runtime selector.
At a delivery boundary, only actual evidence with known_at <= as_of is eligible;
reuse the existing full-constituent causal aggregation and equal-known_at batching.
H1-DECISION-TIMING still owns when callbacks evaluate this input contract and
how lifecycle actions coordinate. A selector remains **NOT_IMPLEMENTED**.
Unsupported dates fail closed; extended early-close dates cannot be skipped.

Before an overdue input arrives, its absence at as_of cannot prove it will
never arrive or that it will arrive at a future manifest timestamp. Use
UNAVAILABLE with cause unconfirmed and expected/present constituent evidence.
After actual arrival, a known_at later than end_at establishes delivery delay.
Missing and delayed are input coverage/arrival reasons, never bearish labels.
A previously available BULLISH state can remain as a dated historical record
while current input eligibility is unavailable; retaining it does not permit
using it silently as current. Final trade permission is a separate policy.

## PIT split-adjusted OHLC contract

Use all OHLC on one consistent split-adjusted basis to remove mechanical stock
split/reverse split discontinuities. This is a **tradable price regime**, not
TOTAL_RETURN_SERIES. Dividend/cash distribution ex-date gaps remain actual price
movements; no cash/reinvestment total-return adjustment is made. A future
total-return variant needs a separate hypothesis/experiment.

For every decision as_of=t, a split is eligible only when **effective_at <= t AND
required action evidence known_at <= t**. Preannounced but future-effective
splits cannot rebase today's history. Effective splits with evidence not yet
known cannot be applied. After effectiveness and evidence availability, use
only factors known by that as_of to causally rebase prior history onto its then
current split units; never rewrite earlier immutable states/snapshots. Today's
future-adjusted provider history must not be projected onto past decisions.

If required split action evidence is unavailable, Daily input/state is
**UNAVAILABLE; raw fallback is forbidden**. State input known_at is the maximum
of bar, required action and all actual transform input known_at. Late evidence
or corrections create a new actual-known_at vintage, not a backdated state.
Actual factor units, action-source coverage and transformation implementation
are V2-D data capability blockers, not new unresolved strategy decision IDs.

The previous alternatives below are preserved as proposal context; only the
PIT split-adjusted convention above is selected.

| Candidate | Causal / PIT interpretation | Required unresolved details / risk |
|---|---|---|
| Raw + action guard/accounting | Preserve raw OHLC and action evidence known by as_of; explicitly quarantine or account for discontinuities | A split or ex-dividend drop cannot silently become trend failure/shock; action discovery time, guard interval and units still needed |
| PIT split-adjusted | Transform only with splits effective/known by that as_of under a frozen factor convention and vintage | Current provider back-adjustment may include future splits; factor scale, all OHLC/volume consistency and late correction vintage must be explicit |
| PIT dividend/total-return adjusted | Define consistent OHLC transform with only then-known cash/action evidence and explicit reinvestment/reference convention | Adjusted Close alone does not define high/low/open; future dividends must not rewrite past states; economic meaning differs from raw tradable price |

Synthetic unadjusted, no-action fixtures do **not** choose raw real-market OHLC.
Current V2 rejects real, unknown/present-action input and has no split/dividend
adapter. A declared future basis may be structurally specified before that
adapter exists; C1 admission is only permission to implement a complete signal
contract, not attestation that future datasets/adjustments are already supported.
Supported dataset/primitive validation remains fail closed. Actual real-data
execution/replay needs its reviewed versioned capability.

Never use today's fully adjusted history as a historical PIT fact by default.
At each as_of preserve source/action vintage, effective time, actual known_at,
transform parameters and resulting causal input hash. Late bar/action corrections
produce a new known-at vintage; immutable old states/snapshots remain unchanged.
Feature dividend normalization is separate from outcome dividend accounting
and from execution prices. Existing top-level Richping normalization/outcome
contracts are neither imported into nor rewritten by this Daily audit.

## Required future Daily state provenance and independent axes

The sidecar enumerates symbol, ET session_date, profile/series role, input_end_at,
actual known_at/as_of, expected/available session and lag/coverage facts, causal
input hash, source vintage ID/reference, price adjustment convention and action
vintage/known-at reference, feature/specification and Daily input contract hashes.
Existing immutable JsonObject/StrategyState can transport them; a future builder
must validate that all identity/provenance agrees with the selected input.

Keep full dataset/vintage fingerprints in an evidence envelope if needed.
They may cover future data and must **not** become classifier inputs or replace
the causal hash of the actual delivered prefix. RTH/extended or raw/adjusted
records cannot be combined merely by matching date/symbol; reject mismatched
series identities rather than coerce metadata. Provenance field presence alone
does not prove PIT correctness.

Trend/exhaustion/price-shock axes remain separate from macro, sector leadership,
options flow and fundamental states. `(BULLISH, EXTENDED, ADVERSE_SHOCK)` and
`(macro HOSTILE, leadership STRONG, trend BULLISH)` retain every value. No axis
is a veto by default. Missing input does not overwrite other axes as bearish or
NORMAL. Final permission belongs to later policy/interaction research; no
current narrative or capital-dependent policy is added.

## Decisions, inventory and unchanged trend dependencies

Historical v6 audit added:

- **H1-DAILY-PRICE-BASIS**, C1: `feature_contracts.daily_price_basis=UNRESOLVED`.
  It changes every OHLC-derived feature and cannot be inferred from H1-SESSION,
  H1-DAILY-SESSION, MACD seed, chart settings or output dividend accounting.
- **H1-DAILY-FRESHNESS**, C1: `timeframe_contracts.daily_freshness=UNRESOLVED`.
  Callback timing alone does not specify which historical Daily inputs remain
  eligible. H1-DECISION-TIMING owns cadence/action coordination; this contract
  owns expected-versus-delivered session freshness, not another timer ID.

Both affect signal correctness before a performance experiment, so neither
can be downgraded to a performance blocker. Completion, dates and provenance
reuse generic contracts and existing decision owners; no IDs are created merely
to label these documentation sections. Required contract fields give **+2**:
total decisions **76→78**, unresolved IDs **71→73**, C1 **47→49**, unresolved
paths **98→100**. Performance 17 / optional 7 unchanged. Each new contract is
one unresolved root at v6; future nested unknowns are counted when declared.

Current v7 resolves three existing root fields without adding IDs or nested
unknowns: session=RTH_DAILY, basis=pit_split_adjusted_ohlc_v1 and
freshness=latest_expected_completed_session_required_v1. Inventory is computed
from the actual spec: **78 decisions unchanged; 73→70 unresolved IDs;
C1 49→46; 100→97 unresolved paths**. Performance 17 / optional 7 unchanged.
Eight decisions are resolved in total. Classifications remain historical
requirements, while blocker membership is derived from unresolved typed values.

v3/v4/v5/v6 remain readable with their original inventory; omissions cannot
pass current C1 admission. H0001 v7 remains DRAFT; FROZEN/C1_READY and
plugin/profitability export remain blocked by other C1 choices.
No state transition, DLP candidate or hypothesis r03 meaning is expanded.

| Unchanged trend proposal | Input dependency only |
|---|---|
| DLP-A | Selected Daily close/basis, consistent history and readiness/freshness |
| DLP-B | A dependencies plus same basis/origin for both EMA prefixes and trading-observation lag |
| DLP-C | Consistent adjusted/raw OHLC, action guard, actual swing confirmation known_at, full continuity and freshness |

The trend proposal file and its DLP-A/B/C blocks remain byte-identical. Source
r03 is untouched. DAILY-TREND can proceed to ex-ante family/parameter/readiness
questions only after input choices and required capability gaps are explicitly
handled; it must not pick parameters/rank candidates from current SOXX cases.

## Next decision bundles

**DAILY-INPUT semantic freeze is complete.** Observed-chart parity remains a
separate unverified evidence question. These V2-D data/runtime blockers remain:

- PIT split-adjustment/action transform, factor-unit convention and action source.
- RTH Daily + extended intraday causal as_of join (C1 integration prerequisite).
- Selected strict Daily freshness selector (C1 integration prerequisite).
- Real provider/session/calendar/action provenance.
- Existing **V2-D_BLOCKER early-close**, unchanged for required extended intraday.

They are named capability gaps in the decision record, not new strategy IDs.
Synthetic unadjusted fixtures implement none of the real split-adjusted choice.

**Then DAILY-TREND:** freeze which of the existing A/B/C family will be tested
and one ex-ante parameter/readiness tuple per retained variant (A/B shared EMA
span/history, B observation lag, C left/right confirmation widths). Declare the
simple baseline, discovery/holdout split and comparison/rejection criteria before
performance data. No champion question is answered now. Input adjustment,
continuity and freshness must be identical within each declared series comparison.

**Later DAILY-AXES-POLICY:** decide exhaustion/price-shock definitions and how
independent states interact with trade eligibility, including unavailable input.
Macro/sector/options/fundamental interactions remain separate research layers.

## Semantic freeze validation (v7)

Full `C:\richping\.venv\Scripts\python -m pytest`: **807 passed in 161.77s**,
no failures, skips or pytest warnings. All 788 prior cases remain; 19 semantic
contract/fixture cases are added. Original proposal/audit inventory assertions
use the immutable basis v6 fixture; current v7 inventory has independent exact
delta assertions. `git diff --check` passes.

Coverage includes all three resolutions, retained generic EXTENDED_DAILY,
UNVERIFIED chart parity, consistent OHLC and split-versus-total-return distinction,
effective_at/known_at conjunction, no future action use or raw fallback,
06:00/08:00/15:00 and exact official-close boundaries, unavailable versus
NOT_BULLISH, weekends/holidays/early close, independent Daily/1H/15m identity,
the exact three removed C1 roots and preserved DRAFT/unselected DLP/r03/proposals.
Calendar and immutable transport fixtures do not attest to a selector, action
transform, mixed-profile runtime adapter or classifier. All capability gaps
and the extended early-close blocker remain explicit.

## Historical audit validation (v6)

Full `.venv\Scripts\python -m pytest`: **788 passed in 158.45s**, no failures,
skips or pytest warnings. Existing 763 cases remain; 23 DAILY-INPUT contract cases
and two mandatory-field cases are added. Focused C0/Daily/extended tests: 381
passed; the new input module: 23 passed. `git diff --check` passes.

Tests cover incomplete/delayed Daily availability and actual known_at, independent
session identity and admission, expected-versus-available session fact transport,
unresolved basis/freshness C1 gates including legacy omissions, unchanged DLP/r03,
pinned philosophy content, independent/conflicting state transport, provenance
and preserved extended early-close rejection. Freshness/state transport tests
do not claim a runtime selector, numeric policy, adjustment adapter or classifier.
The imported philosophy's bytes match the fetched original exactly.
