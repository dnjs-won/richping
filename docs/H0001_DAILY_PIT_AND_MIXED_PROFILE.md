# H0001 Daily PIT prerequisites: implementation with real-evidence blocker

**BLOCKED for historical PIT admission. Implemented ingestion, immutable Daily
vintages, causal split transform, official Daily freshness and separate-profile
join. Executed real Daily/15m offline mechanics; no composed entry or efficacy.**

The frozen input/trend/exhaustion/1H/15m records and v12 specification are
unchanged. The precise remaining P0 is historical action availability,
no-action coverage and raw share-unit evidence, blocking phase exits 4/5/6.

## Actual captures and the simplest route

Yahoo chart 1d RTH captured 500 contiguous XNYS sessions, 2024-10-04 through
2026-10-02. The origin is selected by the calendar's completed-session count,
not a fixed calendar-day warmup. The saved dataset is
`soxx-yahoo-rth-daily-20261003-v1`, hash
`0312ed5c2ffef702e9ee1d185ff789b05221a4aa07f7f49ca5b56215b695371d`.
Its original provider arrays and immutable normalized vintage are archived.
The current 41-session 15m overlap is fully contained in this range.

The actual full-history Yahoo query (2001-07-10 through 2026-10-02) returned
one split, 3 new shares per 1 old share, effective 2024-03-07. The selected
Daily origin is after that event. [BlackRock's dated release](https://www.ishares.com/us/literature/press-release/stock-split-press-release-2023.pdf)
cross-checks the event. The [current issuer page](https://www.ishares.com/us/products/239705/ishares-phlx-semiconductor-etf)
also reports a filed 2026-08-21 forward split, trading on a new basis from
2026-11-05. That event is future-effective for this overlap and is not applied;
no ratio or historical receipt timestamp is invented from the notice.

The split-free anchored interval has sufficient numeric warmup. It cannot yet
satisfy the frozen PIT contract: `PreparedDailyPrefix.transform_known_at`
explicitly includes evidence of *no relevant action*. A current empty Yahoo
split table has only actual capture receipt time, not per-historical-as_of
complete action coverage. Backdating that receipt to the origin, an ex-date,
an announcement's date or a bar-end would manufacture causal knowledge.
Identity transformation requires the same causal evidence checks as a split.

Yahoo chart OHLC is labelled
`YAHOO_CURRENT_SPLIT_NORMALIZED_OHLC_NOT_CERTIFIED_AS_TRADED`, not raw/as-traded
OHLC. Its split-free capture is consistent with an identity basis, but current
provider history alone cannot certify historical unit consistency and future
restatement absence. `raw_unit_status=UNVERIFIED` is preserved. No `Adj Close`
or dividend/reinvestment adjustment is used.

## V1 and provider audit

`richping/data.py:yahoo_dataset` already disables auto/back adjustment and repair,
records capture-time actions, and preserves old vintages during revisions. Its
Daily bars use close plus a 30-minute buffer and V1 universe/accounting metadata.
Neither those bar clocks nor capture-time split tables satisfy V2 historical
action knowledge. They are not imported as frozen V2 Daily evidence. We reuse
the original-array Yahoo transport, canonical hashes, XNYS calendar and immutable
archive/collision pattern from V2, plus the existing frozen classifiers,
features and completed aggregator. We do not aggregate long Daily from 15m.

[Alpaca's current data API](https://docs.alpaca.markets/us/reference/corporateactions-1)
supports forward/reverse splits, symbol and ID filters, process-date sorted
inclusive start/end, 1–1000 total results, `next_page_token`/`page_token`, and
complete/all data-quality filters. It explicitly does not guarantee creation
time and describes receipt/processing/API availability delays. Its
[official SDK models](https://raw.githubusercontent.com/alpacahq/alpaca-py/master/alpaca/data/models/corporate_actions.py)
expose ID, symbol/CUSIP, old/new rates, process/ex/record/payable dates. These
date fields do not by themselves certify the availability of each revision.
Factor direction and exact effective time still need actual payload validation.

The [legacy Announcements launch description](https://alpaca.markets/blog/introducing-corporate-actions-api-announcements/)
reports coverage since April 2020 and typical ingestion following declaration.
That is a different endpoint and a typical schedule, not a delivery guarantee
or historical revision log for the current data endpoint. Its coverage cannot
be silently inherited by the current endpoint. Historical coverage and correction
semantics remain unverified for the actual SOXX payload.

No Alpaca credential variables were present in the task environment. The actual
unauthenticated SOXX corporate-actions request returned HTTP 401; the response
is saved in `corporate-actions.json`. No authenticated event payload, processing
timestamp guarantee, completeness watermark or revision history was verified.
Consequently `process_date` is **not** converted to known_at. Even a conservative
end-of-process-day timestamp requires evidence that the exact payload revision
was available by then; a current corrected record with an old process date is
insufficient. The importer accepts actual capture receipt or explicitly audited
historical source availability, never implicit date backdating.

## Runtime semantics

Daily raw bars and action evidence remain immutable. Action updates/corrections
require a new dataset identity; old inputs and returned state snapshots survive.
The narrow JSON vintage store uses exclusive creation and exact collision
checks. It leaves the existing SQLite intraday schema untouched.

`prepare_daily` selects the latest official XNYS close at or before as_of.
Before close it requires the previous completed session; at close it requires
today. Missing or undelivered expected Daily fails closed, with no prior-state
fallback. Holidays/weekends select the prior trading session. Official early
close (including 2024-11-29 13:00 ET) uses the exchange calendar; unsupported
dates fail closed. Extended early-close architecture is unchanged.

The versioned transform needs audited raw units and complete causal action
coverage from the origin through as_of, including a coverage known_at no later
than as_of. A future interval's action absence cannot be certified in advance.
For each event, only the latest revision known at as_of may be used, and only
when effective_at <= as_of. An effective event whose required evidence is not
known makes the input unavailable. A future revision cannot rewrite an old
snapshot. For N-for-1, each pre-split OHLC field is multiplied by 1/N; a 1-for-N
reverse split multiplies each by N. Volume and dividends are not adjusted.
Inside-session unit changes fail closed. No applied event yields the explicit
`NO_APPLIED_SPLIT_IN_CAUSAL_PREFIX` identity result with transform version,
evidence refs, source vintage, factors, as_of and causal prefix hash.

Historical price bars use
`HISTORICAL_RESEARCH_BAR_END_AVAILABILITY_ASSUMPTION_V1`, separately from action
knowledge. This is the same type of labelled research assumption as the current
intraday capture, not actual provider delivery, live/shadow PIT or measured
latency. It never supplies missing action evidence.

The join independently selects Daily, completed extended 1H and completed
extended 15m. It preserves role, symbol, timeframe, profile, price basis, source
vintage, end_at, known_at, causal input hash and state contract/hash. The two
profiles never enter a concatenated candle stream or mixed ReplayContext.
At 06:00 ET, previous RTH Daily plus today's premarket intraday is normal.
Polling the same completed identity yields the same constituent state hashes;
the join emits no trigger, candidate or callback on polling. All equal-known_at
base members publish via the existing aggregator before a detached join is made.
Partial/modified source publication and mixed intraday vintages are rejected.

## Evidence and remaining acceptance

See [coverage](../research/data_evidence/h0001-daily-pit-20261003/daily-coverage.json),
[readiness](../research/data_evidence/h0001-daily-pit-20261003/daily-readiness.json),
[transform](../research/data_evidence/h0001-daily-pit-20261003/pit-transform-proof.json),
[join](../research/data_evidence/h0001-daily-pit-20261003/mixed-profile-join-proof.json)
and [smoke](../research/data_evidence/h0001-daily-pit-20261003/smoke.json).

The current intraday vintage produces2624 atomic joined evaluations. Two complete network-disabled runs are identical, join stream hash `98bc674c9da861073363d32a77ad7b07085381c4b3b3e010bf41dd466fcbb506`. H1 raw READY829/UNAVAILABLE1795;15m primitive READY2304/UNAVAILABLE320; joint READY evaluations0 because both Daily axes remain unavailable. Portable provider reimport preserves both dataset hashes, and uncached06:00/16:00 sample joins reproduce the memoized proof exactly. See `portable-offline-verification.json`.

Actual historical eligible Daily observations = 0, trend/exhaustion READY = 0,
UNAVAILABLE = 500 each, joint READY = 0. This is not a strategy failure or a
warmup shortage. The missing causal evidence prevents admission.
Separately labelled price-only arithmetic reaches trend N179 on 2025-06-24
and exhaustion N381 on 2026-04-14, with 120 numeric joint-warmup sessions.
These are not eligible READY states or performance results. Actual READY
session dates remain null. Fixtures prove the frozen N178/N179 and N380/N381
boundaries only after legitimate fixture input admission.

The smallest next action is to obtain and audit source availability/revisions
and no-action coverage for the selected interval, plus exact raw price-unit
evidence. Import those into a new vintage and rerun these same proofs. An API
key alone is not acceptance: the actual payload/availability semantics must
also pass. No longer-history intraday migration is required for this blocker.
If no supplier can provide this evidence, only an explicit registered research
variant/user contract decision could change the requirement; this task does
not reopen or weaken the frozen choice. Composition remains queued.

New contract tests: 58. Full workstream suite: 1260 passed, no failures/skips (434.61 seconds). The generic replay/strategy import boundary is preserved. The offline driver memoizes the exact existing pure calendar functions only; it never replaces boundaries, input data, state calculations or strategy parameters.

## Commands

Run from this branch using the project's Python environment:

```text
python -m richping research-v2-data --output-dir var/research/v2-daily-pit daily-sync --end 2026-10-03 --sessions 500 --dataset-id soxx-yahoo-rth-daily-20261003-v1
python -m richping research-v2-data --output-dir var/research/v2-daily-pit daily-inspect soxx-yahoo-rth-daily-20261003-v1
python -m richping research-v2-data --output-dir var/research/v2-daily-pit daily-proof soxx-yahoo-rth-daily-20261003-v1
python -m richping research-v2-data --output-dir var/research/v2-daily-pit daily-action-import soxx-yahoo-rth-daily-20261003-v1 evidence.json --new-dataset-id soxx-daily-v2 --unit-audit unit-audit.json
python -m richping research-v2-data --store C:/richping/var/research/v2-real/market.sqlite --output-dir C:/richping/var/research/v2-daily-pit mixed-proof soxx-yahoo-rth-daily-20261003-v1 --intraday-id soxx-yahoo-15m-20261003-v1
python -m scripts.h0001_daily_offline_proof C:/richping/var/research/v2-daily-pit C:/richping/var/research/v2-real/market.sqlite research/data_evidence/h0001-daily-pit-20261003
```

`daily-import` can reload the archived original provider capture. `daily-vintage.json`
is a portable exact vintage; `intraday-provider-capture.json` reconstructs the
existing intraday content hash. Inspect/proof never import network clients.
No outcome query, forward return, MFE/MAE, H0001 entry composer, execution,
orders, parameter change or main code integration is included.
