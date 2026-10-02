# V2-C0 — 1H relative setup canonical freeze (v11)

At basis `f7123b63d76501ac740f7c5369344f26325e26be`,
[1H setup contract](H0001_1H_RELATIVE_SETUP_RESEARCH.md) and
[immutable freeze](../research/decision_records/H0001-1h-relative-setup-freeze-v1.yaml)
resolve exactly six existing 1H roots. S1 **H1_RELATIVE_DOWNSIDE_MACD_P05_V1**:
MACD_LINE<0 AND current-inclusive midrank percentile320<=.05, W=m=320,
inherited MACD12/26/9/min_history130; first relative READY N449, N448 unavailable.
**LAST_EXTREME_REFRESH_WITH_FIXED_GRACE_V1**, K2 completed1H: new eligible
extreme activates, each new extreme refreshes, age0/1/2 ACTIVE, age3 EXPIRED.
Raw unavailable, Daily trend loss or exhaustion non-NORMAL cancels immediately;
no old observation reactivation or deferred execution. Raw measurement is
independent from Daily. Pure classifier/evaluator/immutable trace transport only,
no trigger/order/fill/position lifecycle or production/paper connection.
Initial family exactly S0 no-filter counterfactual vs S1, one primary comparison;
R2/R3 deferred, no sweeps/outcome lookup/backtest. All 15m/GC/add/reentry/timing/
exit/risk/global state decisions remain unresolved. Daily payloads/hashes and
original proposal/r03 preserved; extended early-close V2-D_BLOCKER unchanged.
Actual inventory: **78 decisions / 16 resolved / 62 unresolved IDs / C1 38 /
performance17 / optional7 / 89 paths**. v11 canonical SHA-256:
`63dccca8a6c00c41b1643e3710fe48261ec8736f005076d4405d231048fe139a`.
Historical v3-v10 remain readable. H0001 DRAFT/BLOCKED_ON_DECISIONS,
NOT_TESTED, chart parity UNVERIFIED. Validation is recorded in PROJECT_STATUS.md.

---

Earlier proposal/freeze sections below retain their named-basis inventories;
current 1H choices and counts are above.

# V2-C0 — 1H relative setup design proposal (v10 unchanged)

At basis `3a046021939b24068f4c95526496814c983af713`,
[1H setup research](H0001_1H_RELATIVE_SETUP_RESEARCH.md) and
[proposal YAML](../research/decision_proposals/H0001-1h-relative-setup-v1.yaml)
bound F1 MACD_LINE with R1 percentile / R2 z-score / R3 ATR ratio and separate
L0/L1/L2 lifetimes. All are PROPOSED_NOT_FROZEN, with no champion or numeric
W/cutoff/lifetime choice. Independent raw INACTIVE/DOWNSIDE_EXTREME/UNAVAILABLE
is context for a separately owned 15m trigger, never BUY or a price bottom.
Prior-only is an audited capability gap; no classifier or runtime code is added.
H1-RELATIVE-METHOD/LOOKBACK/RELATIVE-CONVENTIONS/DOWNSIDE/COMPARATOR/SETUP-LIFETIME,
H1-GC-ROLE and H1-STATE-TRANSITIONS remain UNRESOLVED. Both Daily decisions,
canonical v10 payload/hash, r03, extended early-close blocker and the inventory
78 decisions / 68 unresolved IDs / C1 44 / 95 paths remain unchanged.
H0001 remains DRAFT / BLOCKED_ON_DECISIONS, NOT_TESTED, chart parity UNVERIFIED.
No outcome lookup, performance backtest, Cartesian search or main merge.
Validation for this proposal is recorded in PROJECT_STATUS.md.

---

# V2-C0 — current H0001 Daily blocker freeze (v10)

**H1-DAILY-BLOCKER RESOLVED; H0001 DRAFT / BLOCKED_ON_DECISIONS;
profitability NOT_TESTED; chart parity UNVERIFIED.** Basis
`a25b43a59498cb3a149048dc8f206d7322cac93b` on `v2-c0-extended-session-contract`.
[Canonical blocker contract](H0001_DAILY_BLOCKER_RESEARCH.md) and
[immutable decision record](../research/decision_records/H0001-daily-blocker-freeze-v1.yaml)
supersede the selection questions in the unchanged historical proposal.

**DAILY_BLOCKER_MACD_LINE_P95_V1** selects B1 Daily MACD line (12/26/9,
first-observation seed, signal from first MACD, min_history=130, full causal
history, no reset) + current-inclusive `rolling_empirical_midrank_v1`,
W=252/m=252 completed RTH Daily observations. EXTENDED iff all inputs READY,
MACD line >0 and percentile >=0.95; otherwise READY is NORMAL, failed input
is UNAVAILABLE. N=380 has 251 READY reference points, unavailable; N=381 has
252 READY reference points, READY. Readiness is derived from M+W-1 and actual
primitive statuses/indexing, not a hardcoded total-history gate.

P2 **DAILY_EXHAUSTION_BLOCK_NEW_EXPOSURE_V1** blocks INITIAL_ENTRY/ADD/REENTRY
for EXTENDED and fail-closes UNAVAILABLE with separate reasons. No forced exit,
sizing or blocked-signal queue. Later NORMAL requires a new valid downstream
signal/trigger. Existing 1H EXIT-WATCH + 15m structure exit ownership stays intact.
Pure research classifier/evaluator in `strategy/daily_exhaustion.py` reuse the
V2-B primitives and prepared Daily input contract. State/policy have separate
versions/hashes and combined contract provenance; no plugin/order/paper connection.
Counterfactual trace schema is frozen for immutable transport; candidate logger,
forward trade evaluator and label writer remain unimplemented.

Initial blocker family only **E0/B0 NO_BLOCKER vs E1/B1 frozen P2**,
**1 primary blocker-effect comparison**. B0 may record raw B1 without a veto.
B2 histogram is DEFERRED_SEPARATE_RESEARCH_VARIANT. No z-score/ATR/prior-only,
other threshold/window, P1/P3 or added indicators/sweeps. New changes require a
new revision and new preregistered family. Full performance protocol remains
unregistered; outcomes and backtests NOT_RUN. Win rate alone cannot justify adoption.

Actual inventory: **78 decisions / 10 resolved / 68 unresolved IDs /
44 C1 / 17 performance / 7 optional / 95 unresolved paths**.
Exactly one removed root: `rule_parameters.daily_exhaustion_blocker`.
Current profile **h0001_r03_spec_v10**, canonical SHA-256:
`b9a2c69ce9ea27010b7846339bf052401b3c836dc39c0538ab3e411cb59dd7f4`.
v10 validates the frozen blocker payload and requires the unchanged resolved
Daily trend payload. Historical v3–v9 remain readable with their original meaning.

H1-DAILY-LONG v9 semantics unchanged: close>EMA50 AND EMA50_t>EMA50_(t-5),
minimum_history=174, DLP-B first READY=179; trend hash
`61bb9108c33f1fcd131a384bcf63202e9c52c5dc0e34815a26f840a7e89f1025`.
RTH_DAILY / PIT_SPLIT_ADJUSTED_OHLC / strict latest expected completed session
unchanged; 1H/15m RTH_EXTENDED unchanged. Independent exhaustion does not consume
trend/shock/macro/sector/options/fundamentals/volume or override exit ownership.
Real PIT transform/freshness selector/mixed-profile join/provenance and extended
early-close **V2-D_BLOCKER** remain. H1-DECISION-TIMING remains unresolved.

Current validation: 962 passed (223.44s), existing 880 + 82 new; no failures/skips/pytest warnings. CLI --help and git diff --check pass; 60 local documentation links valid..

---

The earlier C0/v9 audit, proposal inventories and test totals below are historical
records at their named bases; current v10 selections and counts are above.


# V2-C0 — H0001 executable specification contract / freeze preparation

V2-C0 infrastructure: **COMPLETE** (validation results below).
H0001 executable specification: **DRAFT / BLOCKED_ON_DECISIONS**.
H0001 profitability: **NOT TESTED**. No H0001 trading plugin exists.

Daily blocker design at basis `819e6ffebb11e9cb0b5f08bc7d98e4523c98249a`:
[bounded exhaustion proposal](H0001_DAILY_BLOCKER_RESEARCH.md) and
[proposal YAML](../research/decision_proposals/H0001-daily-blocker-v1.yaml).
B0/B1/B2 and separate raw-state/P0–P3 policy contracts are design candidates only.
No field/transform/lookback/threshold/action champion or performance experiment.
H1-DAILY-BLOCKER remains UNRESOLVED; canonical v9 and its inventory/hash are unchanged.
Price shock and macro/sector/options/fundamentals remain independent; forced EXIT
is excluded and P3 sizing is deferred. Proposal questions do not enter executable
unresolved counts. This does not change the frozen Daily trend or DLP-C deferral.

Current Daily trend readiness remediation (basis `8ad1297a4dcd2e9787d62a78fa2866884dbbc41a`):
[Daily research contract](H0001_DAILY_PRICE_RESEARCH.md) and
[readiness remediation record](../research/decision_records/H0001-daily-trend-readiness-remediation-v1.yaml)
resolve **H1-DAILY-LONG** as DLP-B / `DAILY_TREND_EMA_LEVEL_SLOPE_V1`.
`close > EMA50 AND EMA50_t > EMA50_(t-5)`, strict comparisons, completed trading
observations; first-observation seed, minimum_history=174, separate readiness
for current and lag prefixes: `actual_first_seed_residual_lte_0_001`.
Alpha=2/51; seed coefficient `(49/51)^(N-1)`. At N=173 it is
0.0010272011006169637 (UNAVAILABLE); at N=174 it is 0.0009869187045143375 (READY).
DLP-B N=178/lag=173 is UNAVAILABLE; N=179/lag=174 is READY. Equality yields NOT_BULLISH only when every operand is READY;
missing evidence yields UNAVAILABLE, with no SHORT permission.

Input freeze remains **RTH_DAILY / PIT_SPLIT_ADJUSTED_OHLC /
LATEST_EXPECTED_COMPLETED_SESSION_REQUIRED**. Intraday 1H/15m remains
RTH_EXTENDED. Chart parity remains UNVERIFIED. H1-DAILY-BLOCKER stays unresolved.
The original r03, Daily input freeze, philosophy, proposal and
[v1 trend freeze](../research/decision_records/H0001-daily-trend-freeze-v1.yaml) are
preserved. The v1 173-count/v8 contract remains historical and readable;
v9 corrects only the N-1 off-by-one. Classification is
MATHEMATICAL_CONTRACT_REMEDIATION; performance information NONE; neither
PARAMETER_OPTIMIZATION nor PERFORMANCE_TUNING. No actual performance evidence
was generated under the 173-count H0001 contract.

Draft inventory: **78 decisions**, nine resolved;
**45 C1 blockers, 17 performance blockers, 7 optional extensions**;
**96 unresolved parameter/transition paths**, **69 unresolved IDs**.
v7→v8 resolves exactly `rule_parameters.daily_long_permission`, retaining all
IDs, classifications and every other contract. v8→v9 changes no inventory count.
Current v9 canonical specification SHA-256:
`6effcae1ae4e539adf0c84550821be507d86b63565b419b7877a4d08599d9c06`.
Trend rule SHA-256:
`61bb9108c33f1fcd131a384bcf63202e9c52c5dc0e34815a26f840a7e89f1025`.
EMA feature SHA-256: `df12721b668034c411291792a9497f93c831a8bf02518a463ea5115e03b071d6`.

`strategy/daily_trend.py` implements a pure detached research classifier using
V2-B `EMASpec`/`ema`; prepared causal eligible inputs supply freshness/action
facts. No real transform, selector or mixed-profile join is implemented, and no
production/paper/order/plugin integration is added. No historical performance
backtest or sweep. Extended early-close restrictions remain **V2-D_BLOCKER**.

The preregistered Daily subfamily is only **T0 DLP-A level ablation / T1 DLP-B**.
Both use identical operand readiness, inputs, downstream rules, sample and costs;
only the slope predicate differs. C is DEFERRED_SEPARATE_RESEARCH_VARIANT.
Standalone A first becomes READY at N=174; matched T0/T1 both first become
READY at N=179, requiring current and t-5 prefixes independently READY.
Chronological discovery/confirmation separation, contaminated NOK/SOXX exclusions,
failed/null/inconclusive retention and new-revision requirements are frozen.
Actual dataset/date splits and full performance protocol remain undecided until
eligible data coverage is established, before outcomes are inspected.

Current v9 validation: **852 passed in 178.61s**, no failures/skips/pytest warnings
(843 existing regression cases + 9 additional remediation cases). Focused Daily
classifier suite: **45 passed in 15.62s**. CLI `--help` and `git diff --check` pass.
Historical v8 validation: **843 passed in 166.87s**, no failures/skips/pytest warnings
(807 prior cases + 36 new cases). Daily classifier focused suite: 36 passed.
CLI `--help` and `git diff --check` pass. Historical v7 validation:
807 passed in 161.77s. Current v9 validation is recorded in PROJECT_STATUS.md.

The earlier C0 implementation/audit records below describe their original
75-decision/107-path state. Current selections and validation are recorded in
[the extended-session note](V2_EXTENDED_SESSION_IMPLEMENTATION.md) and PROJECT_STATUS.md.

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

future C1 H0001 plugin -> H0001Specification.require_c1_ready()
                     -> generic V2-A replay / V2-B features
```

Generic replay/features never import the specification layer or H0001 module.
The generic specification module never imports H0001. `strategy/__init__.py`
exports only the generic value. There is no registry, on_event, Intent creation,
executor, portfolio, provider integration or optimization in this package.

Install the isolated research parser dependency with
`python -m pip install -e ".[research]"` in the intended environment. PyYAML is
an optional research dependency; generic engine/features do not import it.
All specification APIs, including JSON and in-memory construction, require
`[research]` because the module imports PyYAML at runtime. The base installation
does not promise these research APIs. Packaging tests simulate missing PyYAML
and verify that the production CLI and generic engine/features still import.

```python
from richping.research_v2.strategy.h0001_spec import load_h0001

spec = load_h0001(
    "research/strategy_specs/H0001-r03-draft.yaml",
    hypothesis_path="research/hypotheses/H0001-r03.yaml",
)
spec.specification_hash
spec.unresolved_fields  # detached path -> decision_id + classification mapping
# spec.plugin_specification() raises: DRAFT cannot be handed to a plugin.
# spec.require_c1_ready() also rejects unsupported FROZEN contracts.
```

`StrategySpecification` validates the generic structural contract. A future
H0001 consumer **must** use `H0001Specification` / `load_h0001` and its export
gate, not the generic class to bypass the H0001 inventory. Existing replay's
trusted-plugin protocol remains unchanged; this is not an OS security sandbox
or a retrofit guard on old fixture strategies.

## Schema, canonical representation and hash

Schema `strategy_specification_v1`; current H0001 profile `h0001_r03_spec_v9`.
Profile v4 records the authorized first five decisions and explicit extended capability.
Profile v5 limits H1-SESSION to intraday and adds the independent unresolved
H1-DAILY-SESSION C1 decision without selecting either Daily candidate.
Profile v6 requires independent Daily price-basis and freshness contracts.
Profile v7 records the three user-authorized semantic choices as versioned
contracts; their source/rationale is the new decision record, with the original
input and DLP proposals preserved byte-for-byte at the freeze basis.
Profile v8 freezes the versioned Daily trend contract; mutations require a new revision.
Profile v9 corrects readiness to 174 actual first-seeded observations while retaining
the rule selection, span 50, lag 5 and residual limit 0.001. v8 is validated by
its original immutable contract digest, so it remains readable with its original hash.
Legacy v3/v4/v5/v6/v7/v8 profiles remain readable, but omitted Daily input contracts cannot
pass C1_READY. C1 admission validates declarations; it does not implement a real
adjustment adapter, freshness evaluator or H0001 classifier.
The r03 hypothesis bytes remain unchanged; no r04 is required for this pre-experiment
executable specification resolution.
Profile v2 introduced signal-state ownership and capability admission; v3 closes
the signal lifecycle. The hypothesis revision remains r03. Old profiles v1/v2
are not silently reinterpreted.
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
For engine features, C0 admission checks supported names/versions and explicit
parameters using the existing V2-B spec validators. Strategy rule contracts
remain declarations to implement in C1: C0 does not evaluate rules or certify
their mathematical behavior. C1 must reject unsupported rule names/versions,
validate their method-specific parameters and verify synthetic fixtures before
using them. Admission is readiness to implement the plugin, not plugin completion.
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
  this gate. H0001 blockers cannot be reclassified to evade it. This is structural
  strategy-contract freeze; a valid future-capability choice may remain FROZEN.
- **C1_READY:** derived admission via `require_c1_ready()`, not a stored status.
  Requires FROZEN, no C1 unknowns, only C1 transition dependencies, and current
  engine compatibility. `plugin_specification()` requires this gate. Unknown
  capability/convention/version or an unimplemented primitive fails closed.
- **Profitability readiness:** separate method, not a success/performance status.
  First requires C1 readiness, then no unresolved performance blockers and verified chart
  parity for H0001. Optional future decisions may remain unresolved and excluded.
  A later executor/dataset/evaluation implementation is still required.
- **Historical reproduction readiness:** requires C1 readiness and verified observed
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
unknowns. The authorized first bundle selects **15m / RTH_EXTENDED for 15m/1H
intraday only**. Daily regime independently selects **RTH_DAILY**, removing
`H1-DAILY-SESSION` from the unresolved C1 inventory. The first bundle also selected the
existing first-observation MACD seed, first-MACD signal start, close field and
`macd_first_observation_recursive_v1`. Minimum completed history is 130 on each
of Daily/1H/15m, using full available causal history across sessions without
EMA reset. Relative-transform lookbacks remain unresolved. Engine convention
selection does not validate observed-chart parity.

Add/re-entry is a narrative candidate, not silently included behavior. The
researcher must explicitly include or defer it, then settle failed reversal,
deeper extreme, counter caps and 1H GC role. Stop/trailing/max-holding/overnight
choices are C1 blockers because they can change signal/state transitions;
disabled is a possible explicit choice, never a default. Sizing/exposure/costs
are performance blockers. C1 owns causal signal state and Intent emission;
the future execution/portfolio layer owns orders, fills, actual positions,
sizing, exposure and cash. C1 can emit an Intent with `requested_quantity=None`,
as allowed by V2-A. A signal transition cannot wait for execution confirmation
or read unresolved execution decisions. Fill-based stops, fill-based holding
clocks or capital-dependent rules require a future execution-aware profile;
they cannot be hidden inside the current signal contract. Signal rule choices,
clock origins, counters and resets remain C1 decisions, not defaults.

## Capability mapping (availability does not imply a strategy decision)

`strategy/capabilities.py` exposes `v2_ab_c1_signal_v1`: 15m authoritative base,
XNYS_RTH, atomic-known-at, completed-grid continuity, open-anchored short-final
aggregation, and the existing V2-B feature versions. It compares the complete
machine-readable `engine_capabilities` record, independently of narrative
`available_v2_primitive` text. Exported V2-A/B version constants/classes are
reused; the adapter pins conventions with no exported constant. A separate
`v2_extended_c1_signal_v1` selects `US_EQUITY_EXTENDED_04_20` with its own session,
continuity and aggregation definitions. Availability remains atomic-known-at.
RTH_EXTENDED passes the intraday session portion only with that explicit compatible
profile; a stale RTH claim fails. 1H/Daily base and ATR_REVERSAL/DIRECTIONAL_CHANGE
still require future implementation and cannot pass C1 admission. Full admission
remains blocked by DRAFT status and 45 C1 decisions. `require_daily_session_capability()`
validates the independent Daily choice; MACD Daily continuity follows that choice
rather than the intraday profile. The existing generic extended Daily capability
is retained for a future versioned variant. Historical v3/v4 specifications remain
readable but cannot pass C1 admission without explicit Daily session semantics.

Selected feature contract encoding (all parameters use the existing typed
parameter envelope; the first five and three Daily input decisions are selected):

- `pit_split_adjusted_ohlc_v1`: all OHLC consistently split-adjusted; only splits
  effective by as_of with required evidence known_at <= as_of. Causal history
  rebase after effectiveness is allowed using then-known factors; past states
  are immutable. Missing required action evidence means UNAVAILABLE, no raw
  fallback. Preserve actual cash ex-date price gaps; no total-return adjustment.
- `latest_expected_completed_session_required_v1`: the latest causally delivered
  Daily session_date must equal the latest calendar RTH session with official
  close <= as_of. No numeric lag/grace or previous-Daily fallback. Absent/mismatched
  input means UNAVAILABLE, not NOT_BULLISH. Weekend/holiday use trading sessions;
  early-close official RTH close is the Daily completion boundary.
- These are declarations, not implemented data transforms/selectors. V2-D gaps:
  PIT split/action transform and source; RTH Daily + extended intraday as_of join;
  selected freshness selector; real provider/session/action provenance.
  Preserve each series identity/known_at/hash and join only by as_of, never
  concatenate Daily and intraday candle streams. Existing early-close blocker remains.

- Empty-parameter convention IDs: `first_observation_recursive_v1`,
  `first_macd_observation_v1`, `close_v1`, `macd_first_observation_recursive_v1`,
  `available_completed_history_prefix_v1` (the full available completed-bar
  prefix supplied by the replay context, with no hidden truncation/restart).
- Primitive IDs split their actual V2-B `version` at the final `_vN` into
  `{name, version}`. All dataclass parameters, including convention defaults,
  must be explicit. Missing/extra parameters and unsupported conventions fail.
- Percentile/z-score contracts additionally require a MACD projection `field`;
  `window` must equal that rule's declared lookback. Both available methods
  are supported without selecting one for H0001.
- `macd_atr_normalization_v1` contains typed nested `atr` and `normalization`
  contracts for ATRSpec and NormalizeSpec. The ATR period equals the declared
  lookback; denominator is `atr` and numerator is an available MACD field.
- FRACTAL parameters use `fractal_k_right_strict_v1`, including explicit
  left/right widths, strict ties and completed-grid continuity.

Daily EMA50/minimum_history=174/lag=5 and the earlier MACD conventions are
selected. Other widths, periods, fields and strategy thresholds remain
researcher decisions. The admission gate introduces no performance winner.

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
| Daily trend / blocker | EMA50 level + 5-observation slope research classifier | Trend resolved in v8; separate blocker UNRESOLVED |
| BOS / valid-HL / break | Completed OHLC + confirmed labels | UNRESOLVED strategy semantics |
| Execution / sizing / costs | Reserved Intent/Fill value contracts | No simulator, ledger or performance evaluation |

## Chart parity

Machine-readable `chart_parity` records:

- observed_chart_provider, observed_1h_boundary, observed_ema_seed,
  observed_history_origin, observed_min_history, parity_evidence: UNRESOLVED.
- Selected intraday strategy session: America/New_York 04:00–20:00 extended.
  Selected research Daily session: official RTH close, with separate identity.
- engine_1h_boundary: 04:00–05:00, 05:00–06:00, …, 19:00–20:00.
  Generic Extended Daily covers the full 04:00–20:00 session. Early-close/nonstandard
  days fail closed, as specified in the dedicated implementation note.
- Preserved RTH profile: 09:30 anchored, short final hour and official-close Daily.
- Observed exact 1H convention remains UNVERIFIED; its decision remains UNRESOLVED.
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
ACTIVE_SIGNAL, ADD_READY, EXIT_WATCH_WEAK, EXIT_WATCH_STRONG, INACTIVE_SIGNAL.
The YAML has named candidate transitions with prerequisite decision IDs.
The original 11 conditions remain `UNRESOLVED`; the two lifecycle return edges
reference the existing unresolved transition contract. Prerequisites are a
decision dependency inventory, not an implicit AND/OR rule or executed guard.

Candidate edges describe permission → setup → entry intent → ACTIVE_SIGNAL,
failed-reversal add candidate → add intent → ACTIVE_SIGNAL, weak/strong watches
→ exit intent → INACTIVE_SIGNAL, and hold/new-HH reference update.
`enter_intent_emitted` and `add_intent_emitted` depend on decision timing and
signal transitions, never fill/order timing/sizing/exposure. Exit candidates
also no longer depend on H1-FILL. ACTIVE_SIGNAL records a signal episode;
INACTIVE_SIGNAL means **no current active long signal**, even if an executor has
not filled an exit. It is nonterminal and permits evaluation of a later causal setup.
Neither state asserts a position quantity, a successful fill, or account flatness.
All prerequisite decisions
are C1-classified and must be resolved at admission; nested lower-stage
dependencies are rejected. The 75-decision/107-path inventory is unchanged.

Lifecycle return edges are explicit:

| Transition | From | To | Existing contracts |
|---|---|---|---|
| inactive_daily_permission | INACTIVE_SIGNAL | DAILY_LONG_ALLOWED | H1-DAILY-LONG, H1-DAILY-BLOCKER, H1-STATE-TRANSITIONS |
| inactive_daily_disabled | INACTIVE_SIGNAL | DISABLED | H1-DAILY-LONG, H1-DAILY-BLOCKER, H1-STATE-TRANSITIONS |

At a subsequent causal evaluation, permission to begin a new long cycle is
re-evaluated using H1-DAILY-LONG and H1-DAILY-BLOCKER. If permitted, the return is
to DAILY_LONG_ALLOWED; if permission is absent/blocked, the return is to DISABLED.
The exact split (including the block/reduce alternative), simultaneous-condition
priority, evaluation timing and episode-memory reset remain owned by
H1-STATE-TRANSITIONS with those Daily contracts. No threshold, cooldown, fresh
Daily bar requirement, or same-event transition policy is selected here.

The two `existing_contract_reference/v1` condition envelopes are structural
references to `state_machine_parameters.transition_priority_and_resets`, not
resolved guards. H0001 validation pins the reference path and prerequisite IDs;
the target remains an existing UNRESOLVED path and blocks FROZEN/C1 admission.
Each return therefore reuses an existing unknown instead of duplicating it or
silently resolving it. All prior 107 unresolved paths and 75 decisions remain
identical. This profile change is versioned as `h0001_r03_spec_v3`.

After either exit, a later causal Daily permission/setup must be able to reach
ENTRY_READY and then ACTIVE_SIGNAL through the existing downside_setup,
entry_candidate and enter_intent_emitted conditions again. Prior entry/setup
satisfaction cannot authorize the new episode. Direct INACTIVE_SIGNAL →
ACTIVE_SIGNAL and indirect setup/entry bypasses are forbidden. Exit fill,
position flatness, capital, sizing and performance evidence never gate this
signal lifecycle; they remain execution/portfolio responsibilities.

Graph validation checks all nine states as nonterminal: outgoing progress,
reachability from the DISABLED graph anchor, and a path from every state to both
INACTIVE_SIGNAL and ENTRY_READY. Removing any required permission/setup/entry
edge must disconnect inactive states from ACTIVE_SIGNAL. DISABLED is only a
graph anchor, not a selection of the runtime initial state. These are structural
liveness checks under future satisfying causal inputs, not a guarantee that
market conditions will generate a signal or an implementation of guard timing.

The lifecycle graph is complete for another episode; executable transition
predicates are still unresolved. Initial state, regime loss, setup cancellation/
expiry, weak/strong switching/reset, priority, stops and state memory remain in
H1-STATE-TRANSITIONS and dedicated lifecycle decisions. Freeze must review and
resolve those contracts; no default trading rule was added.
There is no on_event()/BUY/SELL or any other H0001 Intent generation in C0.

## Validation and next action

September 29 lifecycle re-audit remediation, starting at
`03438243b0ce35a456bf350adcdbdf6da5416c26`:

- Full suite: `C:/richping/.venv/Scripts/python -m pytest -q` → **664 passed
  (136.16s)**, no failures/skips/pytest warnings. Includes **280 C0 cases**
  (229 existing + **51 new regressions**) and unchanged V2-A/B tests.
- Graph tests cover both exit branches and permission/no-permission returns,
  all nine nonterminal states, dead-ends/self-loop traps, unreachable/closed
  components, direct/indirect activation bypasses, reference integrity and
  C1 admission while execution/performance blockers remain unresolved.
- Original 75 decisions and all 107 unresolved paths compare identically to
  the audit HEAD. Source r03 worktree bytes compare directly to that HEAD using
  Git's checkout filters; raw SHA-256 remains
  `abdd4f10d127ee7614a4eead734d1bfbf7dc1897ec368f8a3b70a1645e2552fc`.
- CLI `--help` and `git diff --check`: passed. Hypotheses and V2-A/B source/tests
  have zero diff. No strategy value, threshold, execution dependency or
  performance blocker was introduced into C1 transitions. H0001 remains DRAFT;
  this closes graph liveness, not executable predicates or profitability.

Earlier September 29 audit remediation, starting at
`e2bce5b0dd0bd49a7b132f3aced2a3fcaadbfb0f`, closes only the two freeze-semantics
findings: current-engine admission and signal/execution state ownership.

- Full suite: `C:/richping/.venv/Scripts/python -m pytest -q` → **613 passed
  (118.15s)**, no failures/skips/pytest warnings. This includes all **229 C0
  specification cases** (159 existing + **70 new regressions**) and unchanged
  V2-A/B tests. An intermediate targeted C0 run passed 225 cases before the
  last four regressions were added; the full run covers the final code.
- `python -m richping --help` and `git diff --check`: passed.
- Raw local r03 SHA-256 before/after:
  `abdd4f10d127ee7614a4eead734d1bfbf7dc1897ec368f8a3b70a1645e2552fc`.
  The normalized Git-blob source digest remains `35e13276...0f0bc2` as above.
  All hypothesis files and V2-A/B source/tests have zero diff from the starting
  HEAD; the existing preservation test also checks the audited V2-B base.
- No decision metadata, selected strategy values or classifications changed:
  51 C1 + 17 performance + 7 optional = **75 decisions / 107 unresolved paths**.
  The new resolved capability-profile ID adds no decision or unknown. Renamed
  signal transitions retain every unresolved condition and all execution
  decisions remain performance blockers in their own section.
- PyYAML remains in `[research]`/`[dev]`; no production dependency was added.
  No r04, strategy handler, backtest, provider, execution or portfolio was built.

Original C0 validation before the September 29 audit remediation, from this
isolated worktree using
`C:/richping/.venv/Scripts/python -m pytest`:

| Scope | Command arguments | Result |
|---|---|---|
| New C0 | `tests/test_research_v2_specification.py -q` | **159 passed (19.11s)** |
| All V2 | `tests/test_research_v2.py tests/test_research_v2_features.py tests/test_research_v2_continuity.py tests/test_research_v2_specification.py -q` | **289 passed (39.27s)** |
| Full suite | `-q` | **543 passed (108.38s)** |
| Whitespace | `git diff --check` and staged diff check | Passed |

No failures, skips or pytest warnings in those original final runs. An earlier full
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
Only after `require_c1_ready()` succeeds may V2-C1 implement synthetic
state-machine behavior. Current C1
start: **BLOCKED_ON_DECISIONS**. Performance experiment decisions, chart parity,
real data, executor and evaluation integration remain additional later gates.

## Decision matrix

A = C1_IMPLEMENTATION_BLOCKER; B = PERFORMANCE_EXPERIMENT_BLOCKER; C = OPTIONAL_FUTURE_EXTENSION.
Candidates are alternatives, never recommendations. Source references index the unmodified r03 YAML (zero based).
The five original selections and three Daily input rows are resolved.
All other rows remain **UNRESOLVED**. Availability of a primitive is separate
from semantic resolution and does not attest to a runtime data adapter.
Required for profitability includes all C1 decisions. The source statements
and candidate lists preserve the historical capture; the last column records
the selected executable-spec values.

| decision_id / class | question | current hypothesis statement / source | available V2 primitive | candidate choices | required for C1? | required for profitability? | current status |
|---|---|---|---|---|---|---|---|
| H1-SESSION / A | Intraday 15m/1H에서 RTH만 사용할지 extended hours도 사용할지? | Intraday session choice was unknown in r03; observed examples include premarket. Daily session is separate. (unknowns[25], required_data[8]) | Preserved XNYS_RTH plus separate US_EQUITY_EXTENDED_04_20 intraday | RTH; RTH plus extended | yes | yes | RTH_EXTENDED (04:00–20:00 ET), 15m/1H only |
| H1-DAILY-SESSION / A | Daily regime의 session semantics는? | New research choice, independent of unknown observed chart and extended intraday. (unknowns[25], required_data[8]) | Separate causal RTH Daily and generic extended Daily capabilities; mixed-profile join gap | RTH_DAILY; EXTENDED_DAILY | yes | yes | RESOLVED: RTH_DAILY |
| H1-BASE / A | 전략 authoritative base input은? | 15m required; technical input must not imply strategy session selection. (required_data[1]) | V2-A 15m input | 15m; finer input would require a separate capability contract | yes | yes | 15m |
| H1-DAILY-PRICE-BASIS / A | Daily price-derived states의 PIT OHLC basis는? | All OHLC split-adjusted only with effective and known action evidence; cash ex-date gap retained. (required_data[0], required_data[3]) | Synthetic unadjusted/action-free only; real adjustment adapter gap | raw plus action guard/accounting; PIT split-adjusted; PIT dividend/total-return adjusted | yes | yes | RESOLVED: PIT_SPLIT_ADJUSTED_OHLC |
| H1-DAILY-FRESHNESS / A | latest usable Daily와 stale/missing input의 eligibility는? | Calendar expected completed session must equal latest delivered session; no previous fallback. (required_data[3], test.leakage_risks[3]) | Complete/delivery gate and internal continuity; no latest-expected-session evaluator | latest expected strict; explicit versioned grace | yes | yes | RESOLVED: LATEST_EXPECTED_COMPLETED_SESSION_REQUIRED |
| H1-EMA-SEED / A | EMA seed·signal 시작·가격 field·feature version을 무엇으로 동결할지? | MACD(12,26,9), enough past warmup; seed and source field not specified. (required_data[4]) | MACDSpec: first_observation, first_macd_observation, close only | explicitly adopt existing engine conventions; new versioned convention after separate implementation | yes | yes | first_observation / first_macd_observation / close / macd_first_observation_recursive_v1 |
| H1-MACD-HISTORY / A | 각 시간축 MACD 최소 history는? | Sufficient warmup required; count unknown. (required_data[4]) | MACDSpec.min_history | researcher-specified positive counts per timeframe | yes | yes | 130 / 130 / 130 (Daily / 1H / 15m) |
| H1-HISTORY-ORIGIN / A | EMA 계산 이력 시작점·세션 간 지속 정책은? | Past-only MACD; exact history origin unspecified. (required_data[4], test.leakage_risks[3]) | V2-B full visible contiguous history, no session reset | explicit full visible history convention; other versioned history convention | yes | yes | Full available completed causal history across sessions; no EMA reset |
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
