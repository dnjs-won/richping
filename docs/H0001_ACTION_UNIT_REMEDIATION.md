# H0001 action availability and OHLC unit interpretation remediation

The frozen `PIT_SPLIT_ADJUSTED_OHLC` decision requires causal evidence for
actual applied events. It does not freeze a separate historical absence
receipt for every as_of. The prepared-prefix comment introduced in `8ad1297`
and the enforced coverage gate added in `ce6497c` made dataset completeness
an additional causal input. This audit corrects that interpretation for one
fully certified no-event interval. All frozen strategy records and v12 remain
unchanged. Trend N179, exhaustion N381, 1H and 15m rules remain unchanged.

The [interpretation record](../research/decision_records/H0001-action-unit-interpretation-audit-v1.yaml)
retains the canonical clauses, implementation origins and frozen-file hashes.
The previous provider audit and failed v1 readiness reports remain historical
evidence; their old blocker interpretation is superseded by this record.
The frozen classifier source files, including the historical caller comment,
are byte-preserved. The data admission capability supplies the corrected
scope; no classifier code or immutability test is relaxed.

## Two evidence responsibilities

Actual event transforms still require event identity, share ratio, effective
time and audited event evidence known_at. Only effective<=as_of and
known_at<=as_of events may rebase history. Effective events with unknown
evidence remain UNAVAILABLE. Future-effective events do not enter prices,
even if already announced. The existing forward/reverse split engine and
revision handling are retained.

Ex-post completeness and unit audits determine whether a fixed historical
dataset is admissible. Their 2026 capture timestamps are dataset metadata,
not historical strategy known_at, absence receipts, or numeric features.
In a certified interval containing no events, the causal transform inputs
are the price bars alone and the explicit identity transform. Nothing is
backdated. Uncertified empty tables still fail closed.

## Actual SOXX evidence

Selected interval: 2024-10-04 through 2026-10-02, 500 sessions.

- Official iShares Form8937 reports the 3:1 split approved 2023-12-21,
  record2024-03-04, payable after close2024-03-06. Yahoo's actual full-history
  query and Twelve Data's independent event table agree on trading2024-03-07.
  This boundary is before the selected origin.
- iShares' SEC supplement dated2026-08-21 explicitly reports 3:1,
  record2026-11-03, effectuated after close2026-11-04 and split-adjusted
  trading2026-11-05. The current official issuer notice agrees. This is
  after the selected end and contributes no applied factor.
- Neither current provider event history contains an effective event inside
  the interval. They do not promise historical revision/receipt timestamps
  or enumerate announced future events. The issuer supplies those future
  boundary terms. Source coverage and limitations remain in
  [action-history-audit.json](../research/data_evidence/h0001-action-unit-20261003/action-history-audit.json).

Nasdaq's captured historical API returned all500 session OHLC rows. Each
matches the original Yahoo `indicators.quote[0]` within absolute USD0.02.
Maximum differences are O0.005022/H0.005015/L0.005018/C0.000030 dollars.
The cent tolerance accommodates source precision and float32 rounding; it
cannot accept an early 3:1 rebase.

The official issuer download also supplies NAV for all500 dates. The NAV
sanity tolerance is relative2%, because market prices and NAV measure
different things. Actual maximum close/NAV deviation is0.274%. This is
corroboration only: direct Nasdaq market OHLC, not NAV, certifies the four
price fields. Official issuer market close2026-10-01 is576.33 and Yahoo
quote close576.330017. The primary comparison includes2026-09-30 and10-01
plus every other session.

The archived original response contains distinct quote and adjclose arrays.
The installed yfinance parser reproduces each separately;486 rows have
different Close/Adj Close. The adapter uses quote OHLC directly. Yahoo's
overall history is never relabelled raw/as-traded. The
[unit audit](../research/data_evidence/h0001-action-unit-20261003/ohlc-unit-crosscheck.json)
binds the exact raw capture and preserves per-session reference values,
URLs, source hashes, comparison meaning, future-preadjustment detection,
parser version and limitations. The future split is not preapplied.

## Narrow admission capability

`PIT_SPLIT_ADJUSTED_IDENTITY_INTERVAL_V1` requires:

1. Origin after the prior effective split, end before the next split.
2. Official/provider/independent ex-post completeness certification with
   no inside event, bound to the exact symbol and interval.
3. Direct market OHLC comparisons and issuer unit sanity for every captured
   session, bound to the exact Yahoo raw capture hash.
4. A new immutable child vintage, preserving the parent, original price
   basis, price clocks and unmodified current action receipts.

The result is transform IDENTITY, applied_actions=[], factor1.0, never raw
fallback. Loading revalidates embedded evidence and rejects contradictory
inside events, missing comparison rows, changed quotes, changed source units,
wrong scope/bounds, hashes or future-preadjustment. Any interval extension or
new snapshot needs new certification. An actual split interval needs the
existing event engine and legitimately available event evidence.

New vintage: `soxx-yahoo-rth-daily-pit-20261003-v2`, parent
`soxx-yahoo-rth-daily-20261003-v1`. Parent identity/hash remains intact.
Admission audits are embedded in the child manifest and separately archived.
`raw_unit_status=VERIFIED_IDENTITY_INTERVAL` is distinct from
`VERIFIED_AS_TRADED`; the original Yahoo basis label remains unchanged.

Daily bar known_at remains
`HISTORICAL_RESEARCH_BAR_END_AVAILABILITY_ASSUMPTION_V1`.
This is historical causal research admission, without a claim to actual
2025 delivery latency, measured historical action API receipts,
live/shadow PIT or production market data.

## Reproduction and acceptance

The saved immutable [Daily readiness](../research/data_evidence/h0001-action-unit-20261003/daily-readiness.json)
is recomputed from the admitted vintage, independently of price-only
diagnostics: eligible500, trend READY322/UNAVAILABLE178, exhaustion
READY120/UNAVAILABLE380. First actual READY dates are2025-06-24 atN179
and2026-04-14 atN381. The offline mixed proof exercises all2624 current
intraday batches twice, records each role's denominator and requires joint
READY>0. It also compares uncached06:00/16:00 joins with the full proof.
Both runs match stream hash
`6de4730cb3abfaaf701d9fda0a212d5df0ad5f16dcc0e0cf4714f844d0cac57a`.
Daily trend and exhaustion are READY in all2624 overlap batches. H1 is
READY829/UNAVAILABLE1795;15m READY2304/UNAVAILABLE320; joint READY829.
This is upstream readiness, without a composed entry or economic result.

Final full-suite coverage:1291 passed,0 failures/errors/skips, including31
new tests. The suite ran in two disjoint partitions:1290 tests, then the
single real-proof-artifact test after the repeated proof completed. Earlier
comment-only edits failed three frozen source byte checks; the comments were
restored and the full suite rerun. No preservation test was relaxed.

The driver blocks network/provider calls, opens the intraday database
read-only and permits reads only from v2_datasets/v2_bars. No outcome lookup,
entry composer, return, MFE/MAE or profitability run is performed.

```text
python -m scripts.h0001_action_unit_audit
python -m richping research-v2-data --output-dir var/research/v2-daily-pit daily-identity-import soxx-yahoo-rth-daily-20261003-v1 research/data_evidence/h0001-action-unit-20261003/action-history-audit.json research/data_evidence/h0001-action-unit-20261003/ohlc-unit-crosscheck.json --new-dataset-id soxx-yahoo-rth-daily-pit-20261003-v2
python -m scripts.h0001_action_unit_offline_proof
python -m pytest
```

Captured source binaries are byte-preserved with `.gitattributes`. Audits and
proofs use exclusive creation/collision checks. Network capture is separate
from offline audit/admission/proof; reruns never silently overwrite evidence.
The old Daily/15m provider captures and old Daily vintage remain archived on
this branch for portable reconstruction without APIs.

Regression fixtures cover announced-but-future2026 split exclusion at
2026-10-02 and before2026-11-04 close, plus application from the new trading
unit boundary2026-11-05 when required fixture evidence is known. The
2024-03-07 crossing fixture retains all-field1/3 direction, post-unit identity,
unchanged volume and unknown-effective-event rejection. Fixture clocks are
explicitly simulated; they are not reconstructed real receipts.

Alpaca authentication/revision evidence is a future P1 provenance candidate,
not a prerequisite to this sufficient interval certification. Entry execution
and composition is the next PM task after readiness/join/tests pass. The full
first-efficacy phase remains open. No implementation is integrated into main.
