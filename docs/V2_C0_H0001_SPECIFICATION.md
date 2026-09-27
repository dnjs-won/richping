# V2-C0 — H0001 executable specification contract / freeze preparation

V2-C0 infrastructure: **COMPLETE** (validation results below).
H0001 executable specification: **DRAFT / BLOCKED_ON_DECISIONS**.
H0001 profitability: **NOT TESTED**. No H0001 trading plugin exists.

Draft inventory: **75 decisions** (51 C1 blockers, 17 performance blockers,
7 optional extensions); **107 unresolved parameter/transition paths**.
Canonical specification SHA-256:
`5e15b84787a42998ddeed7b183d7e2b5931b87f020840699803dceb56ad3dde3`.

## Investigation and preserved boundary

The starting default checkout was `main` at
`94cc2d292a83714aadaa4033ddfd5a5cfca39125`, with modified
`richping/cli.py`, `richping/maturity.py`, `richping/paper.py`,
`richping/pipeline.py` and untracked `tests/test_r1b_q_regressions.py`.
Those changes remain in their original worktree. The clean
`v2-b-reusable-features` worktree matched the exact audited base
`887810629a46912bd7cd4dcfca2709b1b33d7f74`.
`v2-c0-h0001-spec-contract` / `var/worktrees/v2-c0` starts at that base.
No reset, stash, deletion of others' work, or merge to main is part of C0.

Reviewed r03 in full, RESEARCH_CAPTURE, architecture, V2-A/B implementation
records, PROJECT_STATUS, V2 contracts/replay, every feature module and the
existing V2-A/B/continuity tests before implementing this layer.
V2-A/B causal, atomic-known-at, feature readiness, continuity and provenance
contracts and tests are unchanged. Production/paper and legacy code are unchanged.
The existing recursive V2 code hash naturally includes the new specification
modules; no historical evidence is rewritten and no hash contract is changed.

## Architecture and use

```text
source H0001-r03 (DRAFT, unchanged)
             |
research/strategy_specs/H0001-r03-draft.yaml
             |
H0001Specification mandatory inventory and profile validation
             |
StrategySpecification immutable parser / validation / hash
             |
existing core canonical/digest and V2 JsonObject / timeframe vocabulary

future C1 H0001 plugin -> validated frozen H0001Specification
                     -> generic V2-A replay / V2-B features
```

Generic replay/features never import the specification layer or H0001 module.
The generic specification module never imports H0001. `strategy/__init__.py`
exports only the generic value. There is no registry, on_event, Intent creation,
executor, portfolio, provider integration or optimization in this package.

Install the isolated research parser dependency with
`python -m pip install -e ".[research]"` in the intended environment. PyYAML is
an optional research dependency; generic engine/features do not import it.

```python
from richping.research_v2.strategy.h0001_spec import load_h0001

spec = load_h0001(
    "research/strategy_specs/H0001-r03-draft.yaml",
    hypothesis_path="research/hypotheses/H0001-r03.yaml",
)
spec.specification_hash
spec.unresolved_fields  # detached path -> decision_id + classification mapping
# spec.plugin_specification() raises: DRAFT cannot be handed to a plugin.
```

`StrategySpecification` validates the generic structural contract. A future
H0001 consumer **must** use `H0001Specification` / `load_h0001` and its export
gate, not the generic class to bypass the H0001 inventory. Existing replay's
trusted-plugin protocol remains unchanged; this is not an OS security sandbox
or a retrofit guard on old fixture strategies.

## Schema, canonical representation and hash

Schema `strategy_specification_v1`; H0001 profile `h0001_r03_spec_v1`.
Identity includes strategy ID, specification version, hypothesis ID/revision,
status, UTC-aware created/updated timestamps, source path and source SHA-256.
The source digest normalizes CRLF to LF only, matching the Git blob across
Windows/Linux checkouts; it does not parse or rewrite the hypothesis.

Required named sections are feature contracts, timeframe contracts, rule
parameters, state-machine parameters, execution requirements, research
requirements, optional extensions, chart parity and engine capabilities.
Decision metadata records classification, question, narrative statement,
zero-based r03 source references, available primitive, unselected candidates
and C1/profitability requirements. The unresolved inventory is **derived** from
typed values and transition conditions; an editable duplicate inventory cannot
silently drift from the actual values.

Every parameter explicitly carries `kind`, `value`, `choices`, `decision_id`.
Unknown is exactly `value: UNRESOLVED`, with a known decision ID. Omission,
null, false, zero, empty string and UNRESOLVED are different. Numbers must be
finite and non-boolean; history/lookbacks require positive integers, maximum
adds nonnegative integers. Timeframes use existing `15m`, `1H`, `Daily`
vocabulary; an optional 4H idea does not extend that engine vocabulary.
Enum choices are validated and H0001's field kinds/decision IDs/classifications
are checked against an external mandatory inventory in `h0001_spec.py`.

A resolved `contract` value must be a structured reference:
`{name: <identifier>, version: vN, parameters: {<name>: <typed parameter>, ...}}`.
There is no free-prose formula accepted in a contract-valued parameter.
Nested parameters are recursively checked and their unknowns remain blockers.
This names a future implementation contract; C0 does not evaluate rules or
certify that a named implementation exists. C1 must reject unknown contract
names/versions, validate method-specific required parameters and dependencies,
and verify the implementation against synthetic fixtures before using it.
Structural FROZEN alone cannot establish mathematical correctness, researcher
approval, provider support or profitability. Explicit disabled/deferred contracts
are possible decisions; C0 has selected none of them for core lifecycle rules.

YAML and JSON share validation and produce immutable canonical JSON text.
Duplicate mapping keys, aliases/merge keys, unsafe tags, non-JSON values,
unknown fields, unsupported schema/status/direction, bad timestamps, orphan
decisions and inconsistent requirement flags fail closed. YAML yes/no remain
strings; only true/false are boolean tokens. Comments and mapping order do not
affect meaning. UTC-equivalent timestamps and parsed numeric threshold values
`1` and `1.0` normalize identically, as does JSON numeric exponent notation.
Integer-kind fields deliberately reject
floating input. State names, enum choices, candidate lists, source references
and transition prerequisite lists are sets sorted for canonical serialization.
All other ordered content retains its order.

`specification_hash = core.digest(canonical_body)` uses SHA-256 and the existing
canonical JSON convention. It covers identity, timestamps, source provenance,
all feature versions, rule values, unknowns, decision metadata, chart facts and
candidate state graph. Thus changing a rule, feature version or hypothesis
revision changes identity. Even editorial metadata changes are conservatively
different specifications; logical equivalence of different formulas is not
inferred. The hash is a derived property, not embedded in its own input.
`plugin_specification()` returns a detached immutable JsonObject of that exact
body, so the unmodified replay computes the same specification hash.

## Freeze and experiment gates

- **DRAFT:** explicit unresolved values allowed. No defaulting or auto-freeze.
- **FROZEN:** no unresolved `C1_IMPLEMENTATION_BLOCKER`, including nested
  parameters and candidate transition conditions. Missing fields fail before
  this gate. H0001 blockers cannot be reclassified to evade it.
- **Profitability readiness:** separate method, not a success/performance status.
  Requires FROZEN, no unresolved C1 or performance blockers, and verified chart
  parity for H0001. Optional future decisions may remain unresolved and excluded.
  A later executor/dataset/evaluation implementation is still required.
- **Historical reproduction readiness:** requires FROZEN and verified observed
  chart conventions/evidence. It is stricter than C1 synthetic signal tests.

Immutable means an instantiated specification cannot mutate. Editing the YAML
produces a different object/hash; this is not a mutable configuration attached
to a running plugin. A future decision freeze must record user/researcher
choices, review all method-specific definitions, update specification identity
as appropriate and then evaluate RESEARCH_CAPTURE revision requirements.
No `H0001-r04.yaml` is created by C0. Source r03 remains DRAFT.

## Core candidate and lifecycle scope

Core candidate: Daily permission and separate exhaustion blocker → 1H relative
downside setup → 15m relative downside + reversal/GC → long → hold while price
structure survives → 1H exit-watch → 15m structure-break exit.

MACD fast/slow/signal **12/26/9** and Daily/1H/15m roles are explicit r03 facts.
The r03 listed execution frame is 15m; order/decision/fill timing remain separate
unknowns. Authoritative base and actual strategy session policy remain
UNRESOLVED. Current technical engine input **15m XNYS RTH** is a capability,
not proof H0001 selected an RTH-only strategy. First-observation recursive EMA
is similarly an engine fact, not a validated observed-chart strategy choice.

Add/re-entry is a narrative candidate, not silently included behavior. The
researcher must explicitly include or defer it, then settle failed reversal,
deeper extreme, counter caps and 1H GC role. Stop/trailing/max-holding/overnight
choices are C1 blockers because they can change signal/state transitions;
disabled is a possible explicit choice, never a default. Sizing/exposure/costs
are performance blockers: synthetic signal logic can use abstract position
state, while actual capital/fill evaluation requires these contracts. If a
chosen rule depends on capital availability or Daily reduction, that dependency
must be made explicit at freeze and supplied by the later executor.

## Capability mapping (availability does not imply a strategy decision)

| H0001 need | Existing V2-B primitive | Remaining strategy work |
|---|---|---|
| MACD | MACDSpec / macd / macd_series | Seed, field, origin, min_history selection and parity |
| Relative percentile | PercentileSpec / rolling_percentile | Selection, lookback, readiness, thresholds/comparison |
| Relative z-score | ZScoreSpec / rolling_zscore | Selection, lookback, ddof/readiness, thresholds |
| MACD/ATR | NormalizeSpec + ATRSpec / atr | Selection, scale period/readiness, fields, thresholds |
| Swing high/low | FractalSpec / confirmed_swings | Detector choice, widths; ATR/DC alternatives absent |
| HH/LH/HL/LL | classify_swings | Reference selection and strategy meaning |
| MACD GC / DC | Raw MACD and signal lines | NOT YET strategy predicates |
| Histogram contraction | Histogram values | NOT YET strategy predicate |
| MACD/signal slope | Line values | NOT YET strategy predicates |
| Daily regime / blocker | Completed Daily features | UNRESOLVED strategy rules |
| BOS / valid-HL / break | Completed OHLC + confirmed labels | UNRESOLVED strategy semantics |
| Execution / sizing / costs | Reserved Intent/Fill value contracts | No simulator, ledger or performance evaluation |

## Chart parity

Machine-readable `chart_parity` records:

- observed_chart_provider, observed_1h_boundary, observed_ema_seed,
  observed_history_origin, observed_min_history, parity_evidence: UNRESOLVED.
- engine_1h_boundary: XNYS open anchored, America/New_York
  09:30–10:30, 10:30–11:30, …, 15:30–16:00 on a regular session;
  official early close truncates the final bucket.
- engine_ema_seed: `first_observation_recursive_v1`;
  underlying MACD feature version `macd_first_observation_recursive_v1`.
- parity_status: **UNVERIFIED**. No “matches observed MACD” claim.

Observed-chart checks are performance/historical-reproduction blockers (B),
not obstacles to synthetic C1 state-machine fixtures **after** engine-side
feature conventions, history and all other C1 decisions have been frozen.
Synthetic tests prove behavior under chosen contracts, not chart reproduction.
UNVERIFIED or MISMATCH cannot pass historical reproduction or profitability
readiness. Recording provider/conventions without verification evidence also
cannot set VERIFIED. Evidence must be reviewed; the schema cannot authenticate
an arbitrary evidence string. No real intraday provider was selected here.

## State-machine skeleton

States: DISABLED, DAILY_LONG_ALLOWED, SETUP_1H_DOWNSIDE, ENTRY_READY,
POSITION_OPEN, ADD_READY, EXIT_WATCH_WEAK, EXIT_WATCH_STRONG, FLAT.
The YAML has named candidate transitions with prerequisite decision IDs and
`condition.value: UNRESOLVED` for **every** transition. Prerequisites are a
decision dependency inventory, not an implicit AND/OR rule or executed guard.

Candidate edges describe permission → setup → entry, position establishment,
failed-reversal add candidate → position, weak/strong watches → structural exit,
and hold/new-HH reference update. ENTRY_READY is not a fill; POSITION_OPEN/FLAT
establishment and add completion must eventually distinguish intent from fill.
These are narrative labels, not implemented position bookkeeping.

This is intentionally **not** a complete transition table. Initial state,
regime loss, setup cancellation/expiry, weak/strong switching/reset, re-entry
after flat, concurrent-condition priority, stop interactions and state memory
are all covered by the unresolved `H1-STATE-TRANSITIONS` contract (and dedicated
lifecycle decisions). No extra edge or default transition is invented. Freeze
must review/complete that table and change the versioned profile if required.
There is no on_event()/BUY/SELL or any other H0001 Intent generation in C0.

## Validation and next action

Final validation from this isolated worktree using
`C:/richping/.venv/Scripts/python -m pytest`:

| Scope | Command arguments | Result |
|---|---|---|
| New C0 | `tests/test_research_v2_specification.py -q` | **159 passed (19.11s)** |
| All V2 | `tests/test_research_v2.py tests/test_research_v2_features.py tests/test_research_v2_continuity.py tests/test_research_v2_specification.py -q` | **289 passed (39.27s)** |
| Full suite | `-q` | **543 passed (108.38s)** |
| Whitespace | `git diff --check` and staged diff check | Passed |

No failures, skips or pytest warnings in these final runs. An earlier full
run overlapped a decision-ID edit and loaded old Python/new YAML; it failed
schema consistency and was discarded. The final runs used unchanged code/spec
through completion. Existing V2-A/B tests were not altered to pass.

Tests also pin r03 source content and the unchanged
V2-A/B code/tests against the audited base. Numeric fixture choices used to test
hash/gate behavior exist only in memory; they never update the draft, run a
strategy or constitute selected thresholds.

Next: user/researcher answers the C1 decision matrix, including explicit
deferral where justified. Resolve the full versioned parameter definitions,
then review the resulting spec, source-revision implications and freeze it.
Only then may V2-C1 implement synthetic state-machine behavior. Current C1
start: **BLOCKED_ON_DECISIONS**. Performance experiment decisions, chart parity,
real data, executor and evaluation integration remain additional later gates.

## Decision matrix

A = C1_IMPLEMENTATION_BLOCKER; B = PERFORMANCE_EXPERIMENT_BLOCKER; C = OPTIONAL_FUTURE_EXTENSION.
Candidates are alternatives, never recommendations. Source references index the unmodified r03 YAML (zero based).
All rows currently have status **UNRESOLVED**. Required for profitability includes all C1 decisions.

| decision_id / class | question | current hypothesis statement / source | available V2 primitive | candidate choices | required for C1? | required for profitability? | current status |
|---|---|---|---|---|---|---|---|
| H1-SESSION / A | RTH만 사용할지 extended hours도 사용할지? | Session choice is unknown; US equity/ETF context. (unknowns[25], required_data[8]) | V2-A supports XNYS RTH only | RTH; RTH plus extended (requires new data/feature contracts) | yes | yes | UNRESOLVED |
| H1-BASE / A | 전략 authoritative base input은? | 15m required; technical input must not imply strategy session selection. (required_data[1]) | V2-A 15m input | 15m; finer input would require a separate capability contract | yes | yes | UNRESOLVED |
| H1-EMA-SEED / A | EMA seed·signal 시작·가격 field·feature version을 무엇으로 동결할지? | MACD(12,26,9), enough past warmup; seed and source field not specified. (required_data[4]) | MACDSpec: first_observation, first_macd_observation, close only | explicitly adopt existing engine conventions; new versioned convention after separate implementation | yes | yes | UNRESOLVED |
| H1-MACD-HISTORY / A | 각 시간축 MACD 최소 history는? | Sufficient warmup required; count unknown. (required_data[4]) | MACDSpec.min_history | researcher-specified positive counts per timeframe | yes | yes | UNRESOLVED |
| H1-HISTORY-ORIGIN / A | EMA 계산 이력 시작점·세션 간 지속 정책은? | Past-only MACD; exact history origin unspecified. (required_data[4], test.leakage_risks[3]) | V2-B full visible contiguous history, no session reset | explicit full visible history convention; other versioned history convention | yes | yes | UNRESOLVED |
| H1-DAILY-LONG / A | Daily LONG regime의 정확한 수학식은? | Allow new longs only in Daily rising regime. (rules.regime[0], rules.regime[4]) | Completed Daily MACD and generic features; no regime predicate | versioned Daily MACD rule; versioned price/structure rule; explicitly defined combination | yes | yes | UNRESOLVED |
| H1-DAILY-BLOCKER / A | Daily 과열 blocker의 threshold·차단/축소 방식은? | Upper exhaustion should block or reduce new longs; formula unknown. (rules.regime[1], rules.regime[4]) | Relative transforms; no blocker predicate | block rule with explicit threshold; reduction rule with explicit threshold and exposure dependency | yes | yes | UNRESOLVED |
| H1-RELATIVE-METHOD / A | 1H setup relative MACD 정의는? | Past-relative downside position; no final hindsight extreme. (rules.setup[1], unknowns[4]) | PercentileSpec / ZScoreSpec / NormalizeSpec + ATRSpec | rolling percentile; rolling z-score; MACD / ATR | yes | yes | UNRESOLVED |
| H1-LOOKBACK / A | 1H setup lookback 길이는? | Rolling history required; no length selected. (unknowns[5], required_data[5]) | PercentileSpec.window / ZScoreSpec.window; ATRSpec.period for scale | positive observation count; method-specific period must be explicitly specified | yes | yes | UNRESOLVED |
| H1-RELATIVE-CONVENTIONS / A | 1H setup 상대변환 field·min_history·ties/ddof/ATR 설정은? | Relative transform alternatives discussed, conventions not frozen. (rules.setup[1], required_data[5]) | Current-inclusive midrank / explicit ddof / aligned Wilder ATR | versioned full transform contract including field, readiness and selected scale parameters | yes | yes | UNRESOLVED |
| H1-DOWNSIDE / A | 1H setup 하방 threshold 값은? | Relatively deep downside, no numeric threshold. (unknowns[6]) | Relative numeric output only | numeric cutoff after method is chosen; no value proposed | yes | yes | UNRESOLVED |
| H1-COMPARATOR / A | 1H setup threshold 경계 포함 여부는? | Downside extreme; strict versus inclusive unspecified. (rules.setup[0], rules.trigger[1]) | No strategy threshold predicate | strict less-than; inclusive less-than-or-equal | yes | yes | UNRESOLVED |
| H1-M15-RELATIVE-METHOD / A | 15m entry relative MACD 정의는? | Past-relative downside position; no final hindsight extreme. (rules.setup[1], unknowns[4]) | PercentileSpec / ZScoreSpec / NormalizeSpec + ATRSpec | rolling percentile; rolling z-score; MACD / ATR | yes | yes | UNRESOLVED |
| H1-M15-LOOKBACK / A | 15m entry lookback 길이는? | Rolling history required; no length selected. (unknowns[5], required_data[5]) | PercentileSpec.window / ZScoreSpec.window; ATRSpec.period for scale | positive observation count; method-specific period must be explicitly specified | yes | yes | UNRESOLVED |
| H1-M15-RELATIVE-CONVENTIONS / A | 15m entry 상대변환 field·min_history·ties/ddof/ATR 설정은? | Relative transform alternatives discussed, conventions not frozen. (rules.setup[1], required_data[5]) | Current-inclusive midrank / explicit ddof / aligned Wilder ATR | versioned full transform contract including field, readiness and selected scale parameters | yes | yes | UNRESOLVED |
| H1-M15-DOWNSIDE / A | 15m entry 하방 threshold 값은? | Relatively deep downside, no numeric threshold. (unknowns[6]) | Relative numeric output only | numeric cutoff after method is chosen; no value proposed | yes | yes | UNRESOLVED |
| H1-M15-COMPARATOR / A | 15m entry threshold 경계 포함 여부는? | Downside extreme; strict versus inclusive unspecified. (rules.setup[0], rules.trigger[1]) | No strategy threshold predicate | strict less-than; inclusive less-than-or-equal | yes | yes | UNRESOLVED |
| H1-SETUP-LIFETIME / A | 1H setup 유지·소멸·취소 조건은? | 15m trigger occurs within the 1H setup; lifetime unspecified. (rules.trigger[0], rules.trigger[1]) | No strategy lifecycle primitive | persist while setup holds; explicit time/event expiry; explicit invalidation | yes | yes | UNRESOLVED |
| H1-M15-GC / A | GC equality·previous/current·0선 조건을 어떻게 정의할지? | 15m GC or confirmed reversal; below-zero observation is not a frozen rule. (observations[0], rules.trigger[1]) | MACD line/signal only; NOT YET strategy predicate | strict cross; cross allowing prior equality; separately decide zero-line restriction | yes | yes | UNRESOLVED |
| H1-M15-REVERSAL / A | 확인된 가격 반전이란? | Confirmed price reversal is an entry candidate. (rules.trigger[1], unknowns[9]) | Confirmed swings / classify_swings; no reversal rule | confirmed swing reversal; explicit completed-price rule; explicitly unused under chosen trigger | yes | yes | UNRESOLVED |
| H1-M15-CONJUNCTION / A | 극단·GC·가격 반전의 AND/OR·순서·동시성은? | Downside extreme with GC or reversal; timing relationship unspecified. (rules.trigger[1], observations[2]) | No strategy conjunction predicate | extreme AND GC; extreme AND reversal; extreme AND (GC OR reversal); require both with explicit temporal relation | yes | yes | UNRESOLVED |
| H1-ADD-POLICY / A | 최초 버전에 add/re-entry를 포함할지·어떻게 구분할지? | Capped add or re-entry candidate after failed first reversal. (rules.trigger[2], notes) | No position lifecycle implementation | explicitly defer both; capped add; re-entry; both with separate prerequisites | yes | yes | UNRESOLVED |
| H1-FAILED-REVERSAL / A | 첫 반전 실패를 어떻게 판정할지? | Failed first 15m reversal precedes deeper extreme and new reversal. (rules.trigger[2], unknowns[11]) | No strategy predicate | explicit price invalidation; explicit signal invalidation; explicitly disabled with add policy | yes | yes | UNRESOLVED |
| H1-DEEPER-EXTREME / A | 이전보다 깊은 극단의 reference와 비교식은? | A deeper relative downside extreme precedes a fresh reversal. (rules.trigger[2]) | Relative transforms only | compare prior trigger relative value; compare prior setup extreme; explicit reset/measurement convention | yes | yes | UNRESOLVED |
| H1-MAX-ADDS / A | 최대 add 횟수와 counter lifecycle은? | Adds and position size must be capped; cap unknown. (rules.trigger[4], unknowns[12]) | No strategy counter | explicit nonnegative cap; counter reset belongs to transition contract | yes | yes | UNRESOLVED |
| H1-SIZING / B | 최초·추가 tranche 크기는? | Tranche size is unknown. (unknowns[12]) | No V2 sizing/portfolio engine | fixed units; fixed capital fraction; explicit risk sizing; no value selected | no | yes | UNRESOLVED |
| H1-EXPOSURE / B | 총 risk·종목/계좌 exposure cap은? | Total risk and size must be limited. (rules.trigger[4], unknowns[12]) | No V2 capital accounting | explicit per-symbol cap; explicit account cap; explicit risk budget | no | yes | UNRESOLVED |
| H1-GC-ROLE / A | 1H GC는 확인용인가 추가진입 조건인가? | Not fixed as first-entry requirement; confirmation/add candidate. (rules.setup[2], rules.trigger[5]) | MACD values only | confirmation only; add prerequisite; explicitly unused | yes | yes | UNRESOLVED |
| H1-EXIT-RELATIVE / A | 1H exit relative transform은 setup과 같은가? | Upper relative extreme; method sharedness unspecified. (rules.exit[1], unknowns[7]) | PercentileSpec / ZScoreSpec / NormalizeSpec | explicit shared setup method; independent percentile/z-score/MACD-ATR choice | yes | yes | UNRESOLVED |
| H1-EXIT-LOOKBACK / A | Exit 상대변환 lookback은? | Upper relative extreme history length unspecified. (unknowns[5], unknowns[7]) | Rolling windows / ATR period | explicit positive observation count | yes | yes | UNRESOLVED |
| H1-EXIT-CONVENTIONS / A | Exit 상대변환의 전체 convention은? | No transform convention selected. (required_data[5]) | Same relative primitives as setup | explicit field/readiness/ties/ddof/ATR contract | yes | yes | UNRESOLVED |
| H1-UPPER-EXTREME / A | 1H 상방 extreme threshold는? | Upper extreme precedes strong-watch candidate. (rules.exit[2], unknowns[7]) | Relative output only | numeric cutoff after transform choice; no value proposed | yes | yes | UNRESOLVED |
| H1-UPPER-COMPARATOR / A | 상방 threshold equality는? | Upper extreme exact comparison unknown. (rules.exit[2]) | No strategy threshold predicate | strict greater-than; inclusive greater-than-or-equal | yes | yes | UNRESOLVED |
| H1-HISTOGRAM / A | Histogram 수축의 부호·기간·수식은? | Histogram contraction is an exit-watch candidate. (rules.exit[1], unknowns[8]) | MACD histogram; NOT YET strategy predicate | completed-bar difference; multi-bar contraction; explicit sign/threshold policy | yes | yes | UNRESOLVED |
| H1-MACD-SLOPE / A | MACD slope의 기간·수식·threshold는? | Falling MACD slope is an exit-watch candidate. (rules.exit[1], unknowns[8]) | MACD line; NOT YET strategy predicate | first difference; windowed slope; explicit threshold and units | yes | yes | UNRESOLVED |
| H1-SIGNAL-SLOPE / A | Signal slope의 기간·수식·threshold는? | Falling signal slope is an exit-watch candidate. (rules.exit[1]) | Signal line; NOT YET strategy predicate | first difference; windowed slope; explicit threshold and units | yes | yes | UNRESOLVED |
| H1-DEAD-CROSS / A | DC의 equality·시점 정의는? | 1H DC is watch only; small 15m DC alone does not exit. (rules.exit[0], rules.exit[1]) | MACD line/signal; NOT YET strategy predicate | strict cross; prior equality allowed; explicit timing | yes | yes | UNRESOLVED |
| H1-WEAK-WATCH / A | 중간/0선 failed-upswing과 weak-watch 조합은? | Failure before upper extreme is a weak-watch candidate. (rules.exit[3]) | No watch predicate | explicit midrange/zero-zone rule; exact deterioration conjunction | yes | yes | UNRESOLVED |
| H1-STRONG-WATCH / A | Strong-watch의 극단 이력·하락·조건 조합은? | Decline after upper extreme is a strong-watch candidate. (rules.exit[2]) | No watch predicate | explicit upper-hit memory and deterioration rule | yes | yes | UNRESOLVED |
| H1-WATCH-CONFIRMATION / A | Weak/strong의 가격 확인 강도를 다르게 할지? | Weak-watch must not exit immediately without stronger PA confirmation; exact contrast unknown. (rules.exit[3], unknowns[17]) | No strategy PA confirmation | different confirmation rules; one explicitly justified confirmation contract | yes | yes | UNRESOLVED |
| H1-SWING-DETECTOR / A | 어떤 causal swing detector를 사용할지? | ATR reversal, directional-change, k-bar pivot are candidates. (unknowns[14]) | FractalSpec only; alternatives NOT IMPLEMENTED | k-bar confirmed fractal; ATR reversal; directional-change | yes | yes | UNRESOLVED |
| H1-SWING-PARAMETERS / A | Swing width/threshold/ties와 confirmation contract는? | Pivot usable only from actual confirmation time; widths unknown. (unknowns[15], rules.invalidation[5]) | FractalSpec(left,right), strict ties, confirmed_at | explicit left/right widths; explicit ATR/directional threshold if implemented | yes | yes | UNRESOLVED |
| H1-REFERENCE-HH / A | Reference HH 초기화·갱신·실패는? | Reference HH after which pullback HL and failed rebound LH form. (observations[8], rules.exit[4]) | classify_swings labels only | explicit confirmed HH selection and failure definition | yes | yes | UNRESOLVED |
| H1-LH / A | Reference HH 아래 LH를 언제 확정할지? | Rebound ends below reference HH before HL breaks. (observations[8], rules.exit[4]) | Same-kind LH is available, strategy reference relation is not | confirmed rebound high below reference; explicit tie and sequence policy | yes | yes | UNRESOLVED |
| H1-VALID-HL / A | 어떤 HL/swing low가 유효하며 어느 LH와 연결되는가? | Break the previous valid HL/swing low related to that LH. (observations[8], rules.exit[4]) | classify_swings HL label; NOT valid-HL/BOS semantics | explicit association and confirmation order; explicit equality/initial-low handling | yes | yes | UNRESOLVED |
| H1-HL-BREAK / A | HL break는 wick·종가·연속 종가 중 무엇인가? | Wick versus completed 15m close remains unknown. (rules.exit[6], unknowns[16]) | Completed OHLC only | wick; one completed close; consecutive completed closes with explicit count | yes | yes | UNRESOLVED |
| H1-NEW-HH-RESET / A | 새 HH가 reference/watch/LH/HL 중 무엇을 reset하는가? | New HH updates reference and continues HOLD candidate. (rules.exit[5]) | Confirmed HH labels only | explicit reference update and watch/structure memory reset policy | yes | yes | UNRESOLVED |
| H1-STOP-LOSS / A | Stop loss를 병행할지·정확한 signal 규칙은? | Stop-loss unknown. (unknowns[19]) | ATR primitive only; no stop execution | explicitly disabled; fixed-price/percentage rule; ATR rule with explicit parameters | yes | yes | UNRESOLVED |
| H1-TRAILING / A | Trailing stop 여부·ATR 배수·갱신 규칙은? | Trailing and ATR multiple unknown. (unknowns[18]) | ATR primitive only | explicitly disabled; versioned ATR trail; versioned structure trail | yes | yes | UNRESOLVED |
| H1-MAX-HOLDING / A | 최대 보유시간과 만료 signal 규칙은? | Max holding unknown; timeframe mismatch noted. (unknowns[19], observations[10]) | Clock/completed bars, no lifecycle rule | explicitly disabled; elapsed-time limit; completed-bar/session limit | yes | yes | UNRESOLVED |
| H1-OVERNIGHT / A | Overnight 허용·세션 종료 처리 규칙은? | Overnight policy unknown. (unknowns[19]) | XNYS boundaries only | allow with explicit persistence; disallow with explicit flatten signal timing | yes | yes | UNRESOLVED |
| H1-DECISION-TIMING / A | 어떤 완료/known-at event에서 판단·freshness 제한을 적용할지? | Only then-known completed data; decision cadence/stale handling unspecified. (test.leakage_risks[3]) | Atomic known_at batches, READY/NOT_READY/UNDEFINED | explicit event cadence, stale higher-frame policy and unavailable-input behavior | yes | yes | UNRESOLVED |
| H1-STATE-TRANSITIONS / A | 동시 조건 우선순위·regime 소실·setup 취소·reset·initial state는? | Narrative candidate flow; complete transition table not supplied. (notes, rules.trigger, rules.exit) | Immutable StrategyState / atomic ReplayEvent | explicit deterministic transition table with state memory and reset rules | yes | yes | UNRESOLVED |
| H1-ORDER-TIMING / B | 신호 이후 주문 시점은? | Order timing unknown. (unknowns[20]) | Intent/Fill boundary reserved; executor absent | explicit next eligible event; explicit latency model | no | yes | UNRESOLVED |
| H1-FILL / B | 가격·gap·부분체결·미체결·stop 충돌 가정은? | Fill-price assumptions unknown. (unknowns[20], required_data[7]) | Fill value contract only; NO simulator | explicit causal market/limit fill contract; explicit incomplete/unavailable outcome handling | no | yes | UNRESOLVED |
| H1-COSTS / B | 수수료·슬리피지·stress 비용 규칙은? | No cost assumptions fixed. (unknowns[29], test.cost_assumption) | No V2 cost engine; legacy costs not inherited | explicit commission schedule; explicit spread/slippage model; declared stress scenarios | no | yes | UNRESOLVED |
| H1-UNIVERSE / B | SOXX 단일/반도체/다른 주식·ETF 중 적용 universe는? | Universe choice unknown; point-in-time membership required. (unknowns[24], required_data[0]) | Dataset symbol provenance; no real PIT provider selected | SOXX scope; semiconductor scope; broader explicit PIT scope | no | yes | UNRESOLVED |
| H1-DISCOVERY / B | 발견 기간과 이미 관찰한 사례를 어떻게 기록할지? | NOK and Sep 23-25 SOXX examples are discovery, not independent confirmation. (unknowns[26], test.leakage_risks[0]) | Existing experiment registration principles | explicit dates and used observations; no dates selected | no | yes | UNRESOLVED |
| H1-CONFIRMATORY / B | 독립 confirmatory 기간·purge/embargo는? | Independent confirmatory period not selected. (unknowns[26], test.confirmatory_period) | Reuse existing chronological validation principles; adapter later | untouched chronological holdout; predeclared walk-forward; future observations | no | yes | UNRESOLVED |
| H1-BASELINE / B | 무엇과 동일 시간/자본 조건으로 비교할지? | Simple MACD comparison discussed; actual baseline unknown. (thesis, unknowns[27]) | Existing evaluation principles, no V2 lifecycle adapter | declared simple MACD comparator; aligned passive comparator; explicit alternative | no | yes | UNRESOLVED |
| H1-PRIMARY-METRIC / B | Primary metric과 capital accounting 분모는? | Forward return, MAE/MFE/capture, MDD, utilization, turnover discussed; none chosen. (test.primary_metric, unknowns[28]) | Existing evaluation principles; portfolio NAV absent | one predeclared primary metric; explicitly separated secondary diagnostics | no | yes | UNRESOLVED |
| H1-DECISION-RULE / B | 귀무가설·사전 통과/기각 기준은? | Null hypothesis and decision rule unknown. (test.null_hypothesis, test.decision_rule) | Reuse existing validation engine where compatible | predeclared falsifiable null and decision thresholds; no winner chosen | no | yes | UNRESOLVED |
| H1-SAMPLE-UNIT / B | 평가 표본 단위는? | Signal event or completed trade candidates. (test.sample_unit) | No V2 trade lifecycle evaluator | signal event; completed trade | no | yes | UNRESOLVED |
| H1-MULTIPLE-TESTING / B | 후보군·trial accounting·selection 절차는? | Regime, normalization, thresholds, scale-in, swing and exit families must be preregistered. (test.multiple_testing_family, test.leakage_risks[5]) | Existing failed-trial preservation / evaluation principles | explicit candidate family and selection budget before experiment | no | yes | UNRESOLVED |
| H1-CHART-PROVIDER / B | 관찰한 chart provider·가격조정·session 설정은? | Observed screenshots/discussion do not identify these conventions. (source, observations) | No provider selected or parity evidence | record actual observed provider and settings; do not select an intraday provider here | no | yes | UNRESOLVED |
| H1-CHART-1H / B | 관찰 chart의 1H 경계·짧은 마지막 bucket은? | Observed boundary unverified. (timeframes.signal) | XNYS open anchored 09:30-10:30 ... 15:30-16:00 | verify actual chart intervals including DST and early close | no | yes | UNRESOLVED |
| H1-CHART-EMA / B | 관찰 chart EMA seed/history/warmup은? | MACD parameters explicit; chart initialization unknown. (required_data[4]) | first_observation_recursive_v1; no chart parity claim | obtain observed seed/history/warmup convention and compare | no | yes | UNRESOLVED |
| H1-CHART-VERIFICATION / B | MACD parity 검증 결과·증거는? | Reproduction and profitability have not been verified. (thesis, required_data[4]) | Hand-calculated primitive tests only | record reproducible boundary/EMA comparison evidence and limitations | no | yes | UNRESOLVED |
| H1-4H / C | 4H를 variant로 연구할지? | 4H auxiliary filter inclusion unknown; short anecdote is not core. (unknowns[2], observations[10]) | 4H NOT SUPPORTED | defer; separate filter variant | no | no | UNRESOLVED |
| H1-WEEKLY-MONTHLY / C | 주봉·월봉을 variant로 연구할지? | Higher-timeframe conflict discussed; not core. (unknowns[3]) | Weekly/monthly NOT SUPPORTED | defer; separate higher-frame variant | no | no | UNRESOLVED |
| H1-FINE-EXECUTION / C | 5m/1m refinement를 연구할지? | Finer observation candidate, not formal execution frame. (timeframes.execution, unknowns[21]) | 5m/1m NOT SUPPORTED | defer; separate refinement variant | no | no | UNRESOLVED |
| H1-VOLUME-PA / C | Volume/divergence/OBV/VWAP/volume profile/order block을 연구할지? | Observed but not mandatory core features. (observations[14], unknowns[22]) | OHLCV only; these strategy predicates NOT IMPLEMENTED | defer; separately registered feature variants | no | no | UNRESOLVED |
| H1-OPTIONS / C | Options/0DTE/GEX/Max Pain을 연구할지? | Alternative explanation only; causality not established. (observations[15], unknowns[23]) | NOT IMPLEMENTED | defer; separate PIT data/variant contract | no | no | UNRESOLVED |
| H1-SHORT / C | Short를 별도 가설로 연구할지? | Short excluded from current long-only core. (rules.regime[3]) | No short strategy | defer; separate bearish-regime hypothesis | no | no | UNRESOLVED |
| H1-LAG-STUDY / C | 가격저점/MACD저점/GC 시차를 별도 연구할지? | Timing distributions unknown; do not use hindsight low as signal. (observations[2], unknowns[10]) | No empirical lag study | defer; separate descriptive study with discovery labels | no | no | UNRESOLVED |
