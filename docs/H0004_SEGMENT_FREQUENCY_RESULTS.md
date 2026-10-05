# H0004 trial2: same-segment compression, final freeze and preregistration

The owner corrected pooled time-of-day volatility reference before outcomes.
Trial1 (`TRIAL_1_POOLED_SEGMENT_REFERENCE`) remains immutable:39 candidates across26
sessions. Trial2 (`TRIAL_2_SEGMENT_CONDITIONED_REFERENCE`) compares each current
normalized16-bar range only with that endpoint segment's eligible measurements
from exactly the previous ten completed official sessions. Entire current session
is excluded. Same SIP/raw70-session input is reused, without efficacy exposure.

| Segment | Trial1 compressed / READY | Trial1 rate | Trial2 reference/feature READY | Trial2 compressed | Trial2 rate | Trial2 candidates |
|---|---:|---:|---:|---:|---:|---:|
| PREMARKET | 255 / 1,305 | 19.54% | 1,320 | 325 | 24.62% | 19 |
| RTH | 174 / 1,560 | 11.15% | 1,560 | 381 | 24.42% | 20 |
| AFTER_HOURS | 446 / 960 | 46.46% | 960 | 219 | 22.81% | 9 |

The large pooled segment difference is mechanically reduced on this vintage.
Rates need not equal20%: causal rolling distributions, ties, price regimes and
overlapping windows remain. No threshold, window or candidate-count tuning.
This is frequency sanity, not evidence that future continuation/returns improved.
No third signal variant was created. Total parameter/semantic trials **2**.

| Denominator | Count |
|---|---:|
| Eligible bars / admitted sessions | 4,480 / 70 |
| Compression feature READY / compressed | 3,840 / 925 |
| Continuous feature runs | 108 |
| Unique episodes / frozen ranges | 101 / 101 |
| Valid active-range close comparisons | 625 |
| Candidates / distinct anchor sessions | 48 / 29 |
| Consumed / downside cancelled / expired | 48 / 38 / 14 |
| Pending at input-scope end | 1 |
| Gaps / invalid input / gap-cancelled | 0 / 0 / 0 |
| Window / reference-session warmup unavailable | 15 / 625 |

All101 episodes reconcile:48+38+14+1. No repeated range refresh or duplicate
breakout. Reference normally has220/260/160 observations for PREMARKET/RTH/AH.
The first ten-session reference has205 premarket values because the initial
session's first15 price windows were unavailable; these are disclosed, not filled.
Missing official sessions never get replaced by older available sessions.

Two complete chronological replays and one half-prefix match on published events,
ranges and hashes. All prior protected646 files match Git BASE: prior H0001~3
sources/evidence/preregistrations and all H0004 trial1 sources/evidence preserved.
Signal module uses only SOXX OHLC/time, common session/calendar utilities and
H0004 immutable containers; no prior hypothesis strategy state. Frequency and
freeze/preregistration audits show future-return/window access, MFE/MAE,
efficacy/profitability/confirmation calculations and network calls **0**.
Freeze/preregistration additionally prohibit price loading, signal replay and DB
access. Historical regression fixtures are separate from H0004 research action;
deliberate guard-rejection tests do not execute outcomes.

## Final owner-approved H0004 signal v1

16-bar normalized enclosing range; prior10 official completed sessions of the
same current-bar segment; empirical lower20%, ties fully counted; no extra
persistence. Frozen max high/min low. First later completed close>high, no buffer
or retest, once per episode. Subsequent slots1..16 inclusive; slot17 expires first;
close<low cancels. READY noncompression after retirement then new compression
rearms; gap cancels, clears numeric/session references and disarms. Full04-20ET.

**H0004 v1 studies compression and breakout across consecutive admitted trading
slots, not continuous wall-clock hours. A range may therefore span or survive a
market closure.** Session segments follow the existing half-open bar contract.
The owner explicitly pre-authorized freeze if trial2 causal/deterministic/nonzero
and executable; all conditions passed. Final signal is now FROZEN, not awaiting
another semantic approval. Original hypothesis DRAFT/trial1 proposals are historical
and not rewritten; new freeze decision is authoritative for v1 signal meaning.

## Outcome-free preregistration

Primary is **16 subsequent scheduled15m slots**, four observed trading hours.
Estimator is session-balanced SOXX gross close-to-close price direction: equal
events within session, then equal occupied sessions. Null expected mean<=0;
no benchmark, matched-control search, secondary horizon, MFE/MAE or costs modeled.
Price direction may reflect market drift; this contract cannot establish
incremental timing Alpha, executable profit or account performance.

Fixed252-session confirmation2026-10-19..2027-10-19 after ten-session embargo;
one followup session2027-10-20 and strict terminal receipt deadline
2027-10-21T20:00ET. Confirmation is asynchronous/PENDING, no interim outcomes or
count-driven extension. New interval-specific SIP unit/action/coverage admission
required; unsupported/gap dates retained, never compressed or replaced by RTH.
Every primary label must resolve, else full-cohort inference UNRESOLVED.

Ex-ante breadth floors40 complete events,20 sessions,8 occupied fixed10-session
bins. Terminal uncertainty: existing calendar-block bootstrap architecture with
20-session circular blocks (longer than10-session signal reference),10,000
replicates, H0004 seed202610054, two-sided95% percentile interval. No statistics
computed now; no powered-sample or coverage guarantee. PASS/REJECT require strict
positive lower/negative upper bound and every completeness/floor gate. PASS
permits further research only. Future label/statistics adapter is unimplemented.

Initial metadata sealing caught a YAML `null` key parsed as None; quoting the
key fixed serialization without changing protocol meaning. Its draft is archived.
No extra signal trial or outcome access resulted.

Artifacts: [trial2 frequency](../research/data_evidence/h0004-segment-frequency-20261005/frequency-audit.json),
[trial ledger](../research/data_evidence/h0004-segment-frequency-20261005/trial-ledger.json),
[freeze record](../research/decision_records/H0004-signal-freeze-v1.json),
[preregistration](../research/decision_records/H0004-efficacy-preregistration-v1.yaml),
[metadata verification](../research/data_evidence/h0004-freeze-preregistration-20261005/verification.json).

Next single P0 **H0004_FIRST_EFFICACY**: implement/test/seal the directional
adapter before a later bounded exploratory discovery action. No outcomes were
read in remediation/freeze/preregistration; prior confirmation tracks unchanged.

Validation: targeted **80 passed**; full regression **1,767 passed**.
Immutable JUnit receipts and the reconciled frequency verification are stored
with trial2 evidence. CLI help and Git whitespace checks passed.
