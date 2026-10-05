# H0004 frequency and owner freeze review

H0004 asks whether SOXX's first upside completed-close breakout after own-volatility
compression continues upward. OHLC/time-only mechanics are executable. The
directional efficacy question remains untested; this is not signal freeze or Alpha.

Provisional compression is the current 16-bar enclosing range divided by current
completed close, ranked against the immediately previous 640 observations.
Upper-inclusive empirical rank <=20% qualifies; ties are fully counted. No extra
persistence, ATR comparator, threshold calibration or outcome fitting was run.
16 bars mean four trading hours; reference covers ten extended-session equivalents.

Freeze the compressed window's max high/min low on publication. Later completed
close strictly above that high emits once within next slots 1..16 inclusive.
Slot17 expires before evaluation; completed close strictly below low cancels.
No high-touch, equality, buffer or retest. READY noncompression after an episode
ends, then READY compression, is required to rearm. Gaps cancel and reset warmup
without rearming. Official next-session adjacency carries history and episode;
overnight/weekend count no slots. Unsupported sessions fail closed.

| Mechanical denominator | Actual count |
|---|---:|
| Admitted discovery sessions | 70 |
| Eligible completed 15m bars | 4,480 |
| Compression feature READY | 3,825 |
| Window / history warmup | 15 / 640 |
| Compressed observations | 875 |
| Continuous compressed feature runs | 86 |
| Unique published episodes / frozen ranges | 83 / 83 |
| Eligible active-range close comparisons | 544 |
| First upside candidates | 39 |
| Distinct candidate sessions | 26 |
| Expired / downside cancelled / consumed | 10 / 33 / 39 |
| Pending at input-scope end | 1 |
| Data gaps / invalid inputs | 0 / 0 |

The 86 feature runs are not 86 eligible new episodes: existing frozen ranges and
the rearm lock suppress new publications. 83=39+33+10+1 retains every episode,
including no-breakout and scope-end pending cases. The 544 attempts mean mechanical
close comparisons, not 544 intrabar touches or proposed entries. Candidate/range
identities are unique; repeated polling cannot add events. One tuple produced
these counts without tuning. No sample-independence or efficacy sufficiency claim.

| Segment | Eligible | Feature READY | Compressed | Frozen ranges | Candidates |
|---|---:|---:|---:|---:|---:|
| Premarket | 1,540 | 1,305 | 255 | 27 | 18 |
| RTH | 1,820 | 1,560 | 174 | 27 | 13 |
| After-hours | 1,120 | 960 | 446 | 29 | 8 |

Reference distribution pools segment variation, so quiet after-hours can qualify
more often than RTH. This is visible frequency evidence, not grounds to change
session scope after performance. Range and wait may cross a calendar closure.
Both meanings should be included in final owner freeze approval.

Existing immutable SIP/raw input/hash was independently checked against its
admission: exact 4,480 slots, 70 standard sessions, no gap or provider substitution.
Historical bar-end availability is assumed, not live PIT. Split-only units and
feature dividend normalization remain separate from future outcome accounting.
Same interval was already exposed in prior H0001/H0002/H0003 discovery. It remains
discovery only, not untouched confirmation. No H0004 efficacy outcome was accessed.

Four full replays (two initial, two corrected preservation audits) and two causal
half-prefix replays agreed on original event/range
hashes. Signal trials **1**, comparators **0**. Future-return queries, forward
windows, MFE/MAE, return/profitability calculations, efficacy statistics,
confirmation outcomes, forward-module imports, stores and network calls all **0**.
The runner imports no prior strategy or forward evaluator; audit blocks unloaded
forward modules and guards previously loaded evaluators during full-suite tests.
598 prior tracked research/source/test/doc files, including every H0001~3
evidence/spec/preregistration, remain unchanged. New `scripts/h0004_test_registry.py` supplies
only the sealed historical H0003 registry test its original H0001..3 registry;
both conftests and old tests remain preserved. New H0004 test verifies
the real current registry advances to H0005. Historical regression efficacy
fixtures are separate from this H0004 outcome-free research action.

Artifacts: [frequency report](../research/data_evidence/h0004-frequency-20261005/verification-v2/frequency-audit.json),
[candidate snapshots](../research/data_evidence/h0004-frequency-20261005/verification-v2/candidate-events.json),
[frozen ranges](../research/data_evidence/h0004-frequency-20261005/verification-v2/frozen-ranges.json),
[independence audit](../research/data_evidence/h0004-frequency-20261005/verification-v2/independence-audit.json),
[pre-frequency design](H0004_COMPRESSION_RESEARCH.md).
Test receipts and independent verification are in the same evidence directory.
Two pre-frequency fixture assertions were corrected: the rearm example needed
an actually lower rank under tie-inclusive ranking, and the unsupported-day
example needed an official early-close day. No implementation or tuple changed;
both initial receipts are archived. These synthetic corrections are zero extra
real signal trials. The initial H0004 fixture addition accidentally overwrote the
existing tests/conftest.py and the first manifest pinned its changed bytes rather
than comparing to Git BASE. Targeted preservation tests caught this; the initial
full run was interrupted after failures. Original bytes were restored, fixture
moved to a new plugin, and corrected seal now independently compares all 598
protected files to BASE before replay. Initial reports/manifests/runner/receipts
are preserved (their prior-source preservation claim is superseded by v2).
Only the hypothesis evidence pointer changed; signal parameters/semantics/input
did not. Both generations' events and frozen ranges are identical.
An intermediate full regression also detected that pyproject.toml was protected
by earlier preregistrations. Its bytes were restored; new pytest.ini now loads the
fixture plugin without modifying old configuration or either conftest. That
intermediate full run was interrupted and superseded by the final full run.

Owner decision: approve range-based own-history rank, **16/640/20%**, window-only
persistence, frozen boundaries, strict close without buffer/retest, one candidate
per episode/rearm lock, **16-slot inclusive expiry**, downside-close cancellation,
and extended scope with cross-session history/pooled segments. All are proposed,
not already frozen. Changes require a separate recorded revision/trial.

Next single P0: `H0004_SIGNAL_FREEZE_PREREGISTRATION / USER_DECISION_REQUIRED`.
After owner signal approval, preregister future horizon, controls, uncertainty,
costs, denominator/evidence floor, untouched confirmation and stopping **before**
any outcome. Existing H0001~3 future confirmations remain asynchronous/unchanged.

Final targeted **53 passed**, full regression **1,719 passed**; failures/errors/skips
**0**. CLI `--help` and `git diff --check` passed. Published metadata verification
checks event/range identities, episode reconciliation, original-v2 equality and
all 598 prior files without price queries. Restored pyproject and both conftests
also match Git BASE byte-for-byte. Initial failed/interrupted runs are preserved
as audit history and superseded by these complete passing receipts.
