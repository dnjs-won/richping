# H0003 frequency and freeze review

H0003 asks whether semiconductor leadership versus QQQ persists over a later short
horizon. This step produced causal mechanics and actual frequency evidence only.
The thesis is selected; the signal is provisional, not frozen or efficacy tested.

For each aligned completed slot, calculate both assets' raw price return from the
close 64 scheduled slots earlier, then subtract QQQ return from SOXX return.
This is one extended-session equivalent of trailing leadership, not the return of
an account and not a total-return/dividend-reinvestment feature. QQQ is a
technology/growth comparator, not the whole market. No SPY/comparator grid was run.

Four consecutive READY positive RS observations activate an episode. The first
slot in that episode whose SOXX own trailing return is >=0 emits one candidate.
Guard failure alone never rearms. READY RS<=0 ends the episode and permits another
positive run. Missing/invalid data resets numeric warmup but retains the consumed
episode lock until an observed nonpositive RS, so gaps cannot create duplicate
events. Overnight and session changes do not by themselves rearm.

| Mechanical denominator | Actual count |
|---|---:|
| Sessions in admitted discovery interval | 70 |
| Exact paired READY 15m bars | 4,480 |
| RS READY bars | 4,416 |
| Initial lookback warmup bars | 64 |
| Positive RS bars | 2,345 |
| Persistent leadership state bars | 2,188 |
| Independent mechanical leadership episodes | 37 |
| Candidates | 35 |
| Candidate sessions | 29 |
| Positive RS observations failing own direction guard | 144 |
| Data/session mismatches | 0 |

The 35 events are mechanically deduplicated, not statistically independent sample
certification. Overlapping windows, sessions and leadership clusters remain for
preregistration. Frequency is executable and nonzero: no threshold relaxation,
second window, percentile grid or outcome-based selection was necessary.
Two episodes had no candidate under the proposed guard during the observed scope.
These are retained rather than silently relaxing the LONG interpretation.
Four other episodes emitted later in the same episode when the own-direction guard
first became eligible; they did not create an extra episode or duplicate event.

QQQ's separate immutable Alpaca SIP capture admitted the exact same extended grid
as SOXX: 1,540 premarket, 1,820 RTH and 1,120 after-hours bars; missing/off-grid and
zero-volume observations 0. Repeat pagination, raw/split equality and complete
repeat corporate-action receipts passed. Only cash dividends were returned; no
share-unit-changing action was admitted. SOXX's earlier admitted vintage/hash is
unchanged. Historical availability is bar-end assumed, not observed live PIT.
Same-provider unit checks are not an independent QQQ exchange-price certificate.
No mismatch was found that requires an RTH-only contract. Complete price slots
alone do not prove equal extended/RTH liquidity or live execution quality.

Two sealed offline replays were identical. A separate chronological prefix yielded
exactly the already published subset of events. All outcome, forward-window,
efficacy/statistics, operational/research database and network callable counts in
the H0003 audit are 0. Only full chronological price inputs for causal features
were loaded; no event-conditioned future price/label queries or profitability.
The preexisting regression suite's historical efficacy tests are a separate scope,
not H0003 efficacy execution. H0001/H0002 sources and evidence were protected by
the preexecution manifest and remained unchanged during replay.

The [frequency report](../research/data_evidence/h0003-frequency-20261004/frequency-audit.json)
contains every candidate timestamp, session and segment denominator. The
[candidate snapshots](../research/data_evidence/h0003-frequency-20261004/candidate-events.json)
bind each episode, paired vintage, current feature values and causal anchor.
The [pre-frequency contract](H0003_RELATIVE_STRENGTH_RESEARCH.md) and
[decision record](../research/decision_records/H0003-hypothesis-frequency-v1.yaml)
describe semantics and independence without using efficacy.

## Owner freeze choices

| Proposed choice | Market meaning and tradeoff | Frequency evidence |
|---|---|---|
| One-session-equivalent window | Recent semiconductor leadership, quicker to change; three sessions would mean more durable leadership with longer warmup. | 64 slots tested; 192 not run. |
| Simple positive RS plus persistence | Sustained outperformance with no calibrated magnitude threshold; may include small advantages. Percentile would ask about unusually large leadership and require distribution warmup. | One definition only: 37 episodes. Percentile not run. |
| SOXX return >=0 guard | LONG continuation with own nonnegative direction; excludes relative winners that are still falling. Benchmark crash guard would add a regime threshold. | 35 candidates; 2 leadership episodes un-emitted. Other guard signals not run. |
| Full 04-20ET scope | Includes leadership outside RTH under the admitted input contract; equal slots do not establish equal trading quality. | All 4,480 pairs match; no RTH-only signal variant run. |
| One candidate, rearm only on RS<=0 | One test of each observed continuous leadership run; avoids repeated entries while guard changes. Reentry while RS remains positive would be a different hypothesis. | 35 unique episode IDs, no duplicates. |

These are reversible as a new hypothesis/signal revision before outcomes; existing
sealed trial/evidence must remain. Mechanically this definition is ready for freeze
review. Owner approval of the proposal and final freeze remain pending. No efficacy
preregistration is forced in this step. Next single P0 is
`H0003_SIGNAL_FREEZE_PREREGISTRATION / USER_DECISION_REQUIRED`; freeze first, then
register horizon, controls, uncertainty, evidence floor, untouched confirmation,
cost scope, complete/unresolved denominators and stopping before outcomes.

Test and commit verification is recorded in `verification.json` alongside the
frequency report. Final targeted **113 passed** and full regression **1,594 passed**,
failures/errors/skips 0. CLI `--help` and `git diff --check` passed.
The initial targeted run passed 35 tests with a pytest cache
permission warning; a separate writable cache is used in final verification.
Initial full regression found the old intake test's fixed H0003-next-ID assumption.
An attempted assertion update also tripped H0002's sealed test preservation checks.
That test was restored byte-for-byte. The added root `conftest.py` gives only that
historical intake case its original H0001/H0002 registry fixture; a new H0003 test
independently verifies the actual current registry now advances to H0004. No
runtime module, frozen verifier, old test or prior evidence was changed; no test
was skipped. Both initial full attempts and their failures are archived. Current
revalidation is `.venv/Scripts/python -m scripts.h0003_verify`; it verifies all
502 original protected files and unchanged original frequency/events.
