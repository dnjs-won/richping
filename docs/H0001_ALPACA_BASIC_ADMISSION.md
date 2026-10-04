# H0001 Alpaca Basic actual admission — 2026-10-04

**Actual SIP access PASS; longer frozen full-prefix DISCOVERY admission BLOCKED.**
The owner selected the free Alpaca Trading API Basic route. Both named credentials
were available in the ignored `.env.local`; runtime values take precedence. No
credential value or credential hash is archived, logged or committed. No account,
subscription, order or payment was created. Workstream base is `30d1cca`; canonical
main at bootstrap is `5e6a025`.

## What actually worked

Authenticated SOXX requests explicitly specify `feed=sip`, `adjustment=raw`,
`currency=USD`, `asof=-`, ascending order and historical start/end. All intervals
are well before the recent15-minute boundary. IEX was never requested or used.
The earliest-range request starts2010-01-01 and ends2016-01-06; its first actual
15m bar is2016-01-04 08:45 ET (13:45 UTC). Recent historical requests reach
2026-10-02. This demonstrates endpoints spanning approximately10 years9 months;
it is **not** proof that a continuous10-year dataset was captured or admitted.

Small-page 2025-03-10 capture:60 bars in9 pages using limit7. A separate larger
page query returned the exact same60 OHLCV/trade-count/VWAP rows. Month/quarter
queries also returned short nonterminal pages; all next_page_token values were
followed until explicit null. Offline revalidation reconstructs every saved case
from exact archived pages and request/token links. Errors, malformed responses,
duplicate/reversed timestamps, out-of-range rows and token cycles fail closed.

## Extended observations and admission boundary

Calendar/grid admission reuses Richping's frozen04:00–20:00 ET64-slot engine.
Missing observations are retained as UNKNOWN/UNAVAILABLE, with no carry, repair,
zero filling or gap compression. Sample data:

| Fixed probe | Observed15m rows | Missing supported slots | Premarket / RTH / after-hours |
| --- | ---: | ---: | --- |
| 2016-01-04 | 29 | 35 | 2 /26 /1 |
| 2025-03-07 | 49 | 15 | 20 /26 /3 |
| 2025-03-10 | 60 | 4 | 22 /26 /12 |
| 2024-01-02..02-02 | 943 | 529 | 206 /598 /139 |
| 2026-01-02..02-02 | 1290 | 54 | 451 /546 /293 |
| 2026-07-01..07-31 | 1408 | 0 | 484 /572 /352 |
| 2026-10-01 | 64 | 0 | 22 /26 /16 |

Actual DST probes show04:00 ET at09:00 UTC on2025-03-07 and08:00 UTC on03-10.
Actual2025-11-28 early-close data contains44 bars, including premarket and
after-hours. Official RTH closes13:00 ET. It remains UNSUPPORTED under frozen
extended v1; the response is not remapped to a normal session. The source grid
engine's unsupported-session `observed_bars=0` is its eligibility diagnostic,
not a claim that the raw response contained no observations.

To avoid prematurely rejecting recent access, two further fixed, signal-blind
quarter windows were probed:2026-04-01..06-30 has3958/3968 slots, and
2026-07-01..10-02 has4216/4224. Their18 missing timestamps are archived. The
current `atomic_intraday_batches` refuses coverage other than COMPLETE_GRID;
numeric prefixes also preserve the frozen full available causal history origin
and cannot silently restart after a gap. Thus the fixed broad interval does
not pass the current composer admission. This is actual missing extended price
observations, **not** a SIP permission/depth/paywall failure. No claim is made
that every other historical interval is unusable.

Coverage metadata identifies a complete70-session run2026-05-05..08-13.
It was not chosen as a dataset, normalized, certified or replayed. Selecting that
narrower recent scope in place of the longer-history target is the smallest
alternative decision; it would still require a new Alpaca Daily/action/unit
certificate and independent immutable dataset. No candidate/outcome information
was used to compute this coverage-only alternative.

## Volume and raw/split units

The actual SIP volumes are usable as **condition-eligible bar share volume**,
with explicit aggregation limits. They are not guaranteed to count every print.
For2025-03-10,522 published1m bars sum to5,391,919 shares. Every corresponding
15m bar volume equals the sum of its published1m members, and all60 15m bars
sum to5,391,919. NativeDaily volume is5,410,827; it uses a different trade/update
domain and cannot be substituted for the intraday sum.

The missing19:45–20:00 ET15m slot actually has45 SIP trades totalling658 shares,
all with odd-lot condition `I`. No price bar is emitted for that slot. Missing
therefore cannot mean zero trading. No present bar with numerical volume0 was
observed in these probes; the offline tests independently retain the distinction
between numerical zero, absent row, null value and provider error.

Actual raw and split requests span the2024-03-07 three-for-one split. Intraday
comparison covers45 before/118 after observations; Daily covers1 before/2 after.
Before the ET effective date, split-adjusted OHLC is raw/3 (provider cent-rounding
error at mostUSD0.005) and adjusted volume is exactly raw×3. Afterwards the
units agree. The2024-03-06 19:45 ET bar is2024-03-07 00:45 UTC and correctly
belongs to the **pre-split** date. NativeDaily and intraday both demonstrate USD
as-traded share units; this spot unit test is not a full interval/RTH auction
certificate. Daily and minute trade-condition rules differ; no invented exact
OHLC/volume equivalence is claimed.

## Actions and PIT

The authenticated corporate-action endpoint succeeds and returns44 cash
dividends plus the2024-03-07 forward split. Seven small pages reproduce all
45 events from the larger-page response exactly by event identity/content.
Records contain ex/process/record/payable dates as applicable. They do not
establish historical announcement/ingest/revision `known_at`; process/ex dates
are never backdated into strategy clocks.

Actual-event transforms with unavailable causal evidence must fail closed.
The existing action/unit interpretation remains controlling: a separately
certified no-event interval can use ex-post completeness and exact unit evidence
as dataset admission metadata, without historical absence receipts. Therefore
the API provenance limit alone is **not** declared an unconditional blocker for
discovery price features. No old Yahoo identity certificate is reused for an
Alpaca interval, and no new interval is certified by these bounded spot probes.
Bar-end clocks would remain explicit historical research assumptions, not fresh
shadow/live PIT. Dividend feature normalization and outcome accounting remain
separate. No outcome/return/MFE/MAE or efficacy computation ran.

## Result and next P0

No new market dataset identity/content hash was created, because admission is
BLOCKED. Immutable raw API receipts, probe-manifest hashes, admission report and
twice-equal network-disabled reload proof are provider evidence, not a substitute
dataset or a strategy replay. Original Yahoo41-session dataset, frozen source
bytes, original ZERO_SIGNAL and126-session confirmation contract remain preserved.
Existing candidate count0 is unchanged; new-history candidate count is unknown.

`LONG_HISTORY_ACCESS_PATH_DECISION` is fulfilled. The sole next P0 is
`LONG_HISTORY_EXTENDED_COVERAGE_SCOPE_DECISION`: retain the broad multi-year
frozen full-grid target and audit an owner-approved feed with actual observations,
or authorize a narrower fixed recent discovery scope (coverage-only70-session
alternative). Neither alternative authorizes a paid plan, gap filling, changed
lookback/downside rules or outcome-driven selection. Paid Alpaca upgrades have
not been shown to repair condition-eligible historical price omissions.

Primary provider specifications: [bars](https://docs.alpaca.markets/us/reference/stockbarsingle-1),
[aggregation and SIP FAQ](https://docs.alpaca.markets/us/docs/market-data-faq),
[actions](https://docs.alpaca.markets/us/reference/corporateactions-1).
Actual evidence and test counts are in
[admission.json](../research/data_evidence/h0001-alpaca-basic-20261004/admission.json),
[offline proof](../research/data_evidence/h0001-alpaca-basic-20261004/offline-reload-proof.json)
and `test-report.json` in the same directory. Pytest is offline; live probes use
`python -m scripts.h0001_alpaca_admission`, with `--supplement`/`--depth` explicitly
invoked. No provider call is made on import or during deterministic tests.
