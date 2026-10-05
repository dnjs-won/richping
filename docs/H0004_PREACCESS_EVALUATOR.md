# H0004 pre-access directional evaluator

This action implements and seals the registered calculation before opening any
real H0004 forward prices. H0004 discovery remains NOT_RUN; confirmation remains
PENDING / ASYNCHRONOUS. Frozen signal, protocol, trial1/trial2 and prior hypothesis
evidence are preserved. No signal variant, horizon change or performance estimate.

## Calculation and readiness

The detached input binds candidate and episode ids, signal snapshot hash,
completed candidate end, anchor close content identity, dataset id/content hash,
admission file hash, scope and calendar/semantics hashes. The adapter shares the
already frozen timestamp-only scheduled window utility. The signal never imports
the evaluator. There is no provider, database or automatic runner in the evaluator.

Primary label: `SOXX_close(exact scheduled t+16)/SOXX_close(t)-1`.
Readiness checks anchor and every nominal scheduled slot t+1..t+16. Overnight,
weekends and official holidays consume no slots. Unsupported nominal dates are
retained; RTH and the next available observation never substitute. Current action
does not probe the real candidates' endpoint scope/readiness, even without values.

READY_TO_EVALUATE is metadata-only. Before endpoint maturity or slot availability:
PENDING. Mature missing supported slot, unsupported followup, out-of-scope path,
share-unit change/unknown action/incompatible raw-unit segment: UNRESOLVED. Clock,
hash, duplicate, feed, adjusted-price or anchor identity defect: INVALID_FAIL_CLOSED.
Discovery scope is the immutable70 sessions2026-05-05..08-13; endpoint outside this
scope remains UNRESOLVED and receives no supplementary capture. Every price
lookup matches its content identity. No adjusted fallback or new transform.

Equal-weight event returns within each anchor session, then equal-weight occupied
session means. Full emitted denominator is preserved as total/complete/pending/
unresolved/invalid. Any noncomplete event blocks the full-cohort mean; no
complete-case estimate. Discovery is descriptive with no CI/PASS/REJECT.
Cash dividends are disclosed separately, with no total-return correction.
Profitability NOT_ESTIMATED; no MFE/MAE, controls, benchmarks or execution model.

## Scope and activation

Typed DISCOVERY_EXPLORATORY cannot admit confirmation anchors or extend discovery
source scope. CONFIRMATION_TERMINAL cannot expose label values or aggregate before
the fixed deadline2027-10-21T20:00ET, including equality. Readiness may expose state
only. Real confirmation additionally requires a separate future interval admission
and terminal seal; this infrastructure does not activate it or calculate terminal CI.

Real discovery source loading and every label call require independently verified
pre-access manifest and PASS receipt plus canonical action
H0004_DISCOVERY_EFFICACY_EXECUTION. The dormant source adapter reuses immutable
dataset/admission validation, validates action/unit audit identities, and supplies
only exact close identities. It never executes in this action. New execution
requires explicit separate-action invocation; merely importing these modules or
updating PM routing does not open outcomes.

## Evidence and verification

Manifest binds all evaluator/source/verifier/fixture/test/design bytes, frozen
signal/protocol/candidate file identities, dataset/admission file hashes,
calendar/session semantics, exact formula, weighting, units and scope. Protected
BASE is the published final freeze branch commit292dd67. Hashing existing input
bytes is identity verification, not parsing or querying forward observations.

Targeted and full regression receipts are required for independent PASS. A
separate verifier checks source direction and formula/weighting against rational
artificial references, completeness, fixed weekend mapping and confirmation guard,
twice with identical output hashes. Only SYNTHETIC: dataset identities may perform
test arithmetic. Shared metadata/no-outcome guards additionally reject real
source loading, label reads, aggregation and real candidate endpoint probes.

Real audit counters remain0: forward-price queries, discovery/confirmation label
reads, return arithmetic, efficacy aggregations and profitability calculations.
Synthetic counters are recorded separately and do not describe market efficacy.
All48 real candidates and29 sessions stay in the frozen stream unchanged. Trial
count remains2. Next P0 is separate bounded discovery exploratory execution;
no outcome is disclosed as part of implementing, verifying or sealing this adapter.
