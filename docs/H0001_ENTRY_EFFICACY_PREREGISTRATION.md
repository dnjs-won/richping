# H0001 initial-entry opportunity protocol v1

The latest main PM state already marks composition complete at `bb72239`.
This action freezes only `H0001_ENTRY_EFFICACY_PREREGISTRATION`, before any
entry outcome access. It does not run efficacy or alter the candidate composer.

The authoritative record is
`research/decision_records/H0001-entry-efficacy-preregistration-v1.yaml`.
Its canonical hash (record excluding `contract_hash`) is
`074255189630fa625c4d40eb2f344fb7767d2c8f305f22c9e4c2a608e93e944c`.
The record pins 23 source/contract/signal-metadata dependencies by LF SHA256.
The verification script also pins this protocol hash: editing and rehashing
the same version fails closed.

## Frozen experiment

- Sample: immutable SOXX INITIAL_ENTRY_CANDIDATE, at most one per H1 episode.
  Gross observation marks represent entry opportunities, without fills or capital.
- Horizons: 4, 16, 64, 192, 320 expected completed extended 15m slots.
  Primary: 64 slots; secondary horizons and MFE/MAE are descriptive only.
  Expected-grid gaps are retained, never skipped to an available bar.
- Baseline: other eligible SOXX sessions at the same local completed 15m slot,
  within the same partition, omitting the H1 ACTIVE and M15 trigger filters.
  Each event excludes its own anchor session; minimum 10 distinct control sessions.
  This is a timing comparison, without a passive portfolio or filter-ablation claim.
- Primary metric: session-balanced mean of candidate return minus matched control
  return. No SPY substitution; no compatible SPY intraday vintage is admitted.
- Existing 2026-08-05..2026-10-01 intraday anchors are discovery only. Prior NOK,
  SOXX chart cases and all current indicator/count exposure remain recorded.
- Future confirmation: five-session embargo 2026-10-05..09, then 126 official
  XNYS anchor sessions 2026-10-12..2027-04-13. Unsupported early-close sessions
  remain UNAVAILABLE. No interim testing, count-driven extension or retrospective
  holdout. Later vintages require new causal action/unit admission, especially
  beyond the previously certified interval.
- Uncertainty: joint circular five-session block bootstrap, 5000 draws, seed 7,
  two-sided 95% percentile interval. Recompute controls in every draw, retain
  zero-signal sessions and original-session exclusions. Any invalid draw blocks
  inference. Minimum 30 paired events on 20 distinct candidate dates; these
  are evidence floors, not a guarantee of statistical power.
- One primary test at family alpha .05. Prior Daily/blocker/H1 ablation families
  remain separate, unexecuted. No selection among secondary metrics.
- ZERO_SIGNAL short-circuits before market/action/outcome access. Metrics are null.
  Pending or unresolved primary labels, inadequate controls or sample size yield
  PENDING/INSUFFICIENT_EVIDENCE. Only the complete untouched confirmation cohort
  can PASS or REJECT; a CI spanning zero is INCONCLUSIVE.
- Reuse existing `v3_cash_action_guard` eligibility principles: incompatible units,
  unknown action coverage or actions in a label window are unresolved. Feature
  dividend normalization does not authorize outcome dividend accounting.
- Costs are not applied to gross signal marks; after-cost profitability remains
  unresolved and no zero-real-cost claim is made.

## Verification and next execution

Run `.venv\Scripts\python -m scripts.h0001_entry_efficacy_preregister`.
It reads only contracts, source files and existing signal metadata, while network,
SQLite and market loaders are blocked. Two verification runs produce identical
immutable contract/proof/smoke artifacts. No new market replay or price read is
needed for this action.

Existing `richping.evaluation.block_ci` was audited. Its signal-date averaging
and fixed comparison rows cannot implement the joint calendar/control estimand
directly. The later execution action must use a narrow adapter preserving its
circular block sampling mechanics and this frozen protocol. No evaluator is
implemented or claimed complete here.

Executable signal spec remains `h0001_r03_spec_v13`, canonical hash
`bf8134733bacee17542240e53a8ec30223c1550b5bedbaa6d3994ba1444acc19`;
84 unresolved paths and general full-strategy research roots remain unchanged.
The independent evaluation protocol has its own version/hash. Bumping the signal
spec would change deterministic candidate identities without changing signal
semantics. The scoped decision record resolves only initial-opportunity evaluation.

Next action is `H0001_FIRST_ENTRY_EFFICACY`. With the frozen current empty stream,
that action must report ZERO_SIGNAL without accessing prices or outcomes. It cannot
produce numeric efficacy or satisfy phase exit 6 as informative market evidence.
Longer-history/provider coverage remains a P1 blocker candidate until that separately
executed disposition. No provider migration or strategy threshold change occurs here.
