# H0001 longer-history provider and volume audit — 2026-10-04 KST

**Audit complete; expanded-history admission BLOCKED.** No provider is selected
or migrated. The next P0 is `LONG_HISTORY_ACCESS_PATH_DECISION`
(`USER_DECISION_REQUIRED`), blocking phase exit criterion 6. Current credentials
cannot reach a longer admissible 15m feed. Buying data is not yet necessary.

## Actual access and coverage

Bootstrap used latest `main` e7082fa for PM documents and implementation
58a237c for the frozen research workstream. Evidence directory:
`research/data_evidence/h0001-long-history-20261004/`. Captures occurred on
2026-10-03 UTC / 2026-10-04 KST. This is a bounded capability audit, not an
immutable research dataset capture. A complete grid sample is not admission.

| Provider/feed | Current access / actual SOXX interval | Documented alternative, not current entitlement | Disposition |
| --- | --- | --- | --- |
| Yahoo chart 15m, existing adapter | Anonymous HTTP200, 2026-08-05 and 10-01 spot checks, 64 slots each. Existing immutable full cohort 08-05..10-01, 41 sessions. 08-04, 08-03 and 2025-03-10 HTTP422 explicitly require last60 days. 10-02 returns65 rows including invalid19:59:54 ET. | Rolling60 calendar days; requests cannot page beyond retention. No documented stable quota/SLA. | BLOCKED_ON_EXTENDED_HISTORY; volume UNKNOWN; new action/unit admission absent |
| Yahoo native60m | Anonymous HTTP200, 16 rows on 2025-03-10 only. No continuous maximum range claimed. | Longer native hourly history exists, but cannot reconstruct15m, and is not the frozen completed15m-derived04:00-anchored1H input. | BLOCKED_ON_GRID_COMPATIBILITY |
| Alpaca historical SIP | SOXX15Min raw bars and action endpoint both HTTP401. No authorized interval established. IEX is not substituted. | Stocks/ETFs since2016, Basic free; older-than15-minute SIP access described in FAQ. Basic200 requests/min; pages up to10,000 bars with next_page_token. | BLOCKED_ON_CREDENTIAL; grid/action/unit admission still UNVERIFIED |
| Massive (formerly Polygon) consolidated stocks | SOXX raw15-minute request HTTP401; no authorized interval established. | Basic lists minute aggregates and2 years/$0/5 calls/min, Starter5 years/$29 monthly, Developer10 years/$79. Account eligibility/actual aggregate entitlement untested. | BLOCKED_ON_CREDENTIAL; a paid extension would be USER_DECISION_REQUIRED |
| Databento EQUS.MINI / direct venue candidates | metadata.list_datasets HTTP401; no authorized SOXX interval or dataset license established. | MINI OHLCV blends component venues; single direct feeds are venue-specific. Dataset-specific depth/coverage must be queried; marketing-wide15+ years is not SOXX intraday evidence. Historical usage pricing; exact SOXX quote UNKNOWN. | BLOCKED_ON_CREDENTIAL; dataset/volume/cost selection requires user decision |
| Twelve Data historical US equities | SOXX15min/prepost=true/adjust=none HTTP401; no authorized interval established. | Historical04:00–20:00 for records older than1 day. Up to5,000 points/request, date-window paging. Exact SOXX extended-history start and credits UNKNOWN. | BLOCKED_ON_CREDENTIAL; exact historical intraday volume/action/units unverified |

Authorization audit found no recognized provider variables in the process,
Windows User or Machine environment; no repository `.env*`, credential or
secret configuration file was found outside excluded `.git`, `.venv`, `var`.
`config.toml` has operational settings only. No arbitrary credential vault or
other project's secrets were searched. No account was created, no secret was
generated, and no subscription purchased. Absence means unavailable to this
documented runtime/config path, not proof the user owns no account elsewhere.
Tiingo/Alpha Vantage/EODHD have no local adapter or recognized credentials and
were not authenticated/probed; no capability claim is made for them. Stooq/
issuer/Nasdaq Daily evidence is not a longer extended15m feed.

Sandbox probes first failed at transport; their records are preserved and
classified `TRANSPORT_FAILURE_CAPABILITY_UNKNOWN`. The permitted external
retry returned the HTTP results above. A transport/429/5xx failure is never
proof of missing historical capability. HTTP401 establishes authentication
failure only, not plan/depth failure. Public documentation and public metadata
responses never establish paid entitlement.

## Grid and volume

The existing calendar/session engine is reused: standard XNYS sessions require
64 completed15m slots, anchored04:00 America/New_York (22 premarket,26 RTH,
16 after-hours), end20:00. UTC anchor is09:00 in winter and08:00 in summer.
Deterministic tests exercise both sides of the March2025 DST transition.
The live Yahoo checks are summer samples; they do not demonstrate historical
DST or whole-interval completeness for another provider.

Early closes remain `UNSUPPORTED_FAIL_CLOSED` under frozen extended v1.
The 2025-11-28 live15m request was refused by retention, so its historical
feed grid is UNVERIFIED. The deterministic early-close test confirms the
existing engine returns UNSUPPORTED, with no26-slot RTH substitution or
calendar compression. New captures must retain unavailable early-close anchors
in coverage/denominator diagnostics; their adjacent lookbacks must fail closed.

The two successful Yahoo samples have0 missing/duplicate/null/incomplete rows;
each reports volume0 on **all38 extended-hours bars**. This is a numerical
provider value, not evidence of zero ETF trading. Latest10-02 has64 aligned
slots plus one extra19:59:54 point; the65-row response is UNAVAILABLE and is
not silently rounded, dropped or repaired. Captured receipt is after bar end,
but historical delivery delay or revisions remain UNKNOWN.

These states remain separate: present volume0; absent expected slot (UNKNOWN);
explicit transport/feed error; null volume (UNKNOWN); and unsupported market
session. None is filled synthetically or inferred as a no-trading bar.

Provider volume interpretation:

- Yahoo: quote-array volume preserved. Venue coverage and the reason extended
  values are zero remain UNKNOWN. Neither exchangeName nor complete timestamps
  prove consolidated volume. Existing evidence is not upgraded.
- Alpaca SIP: documented trade-size aggregation across consolidated US feeds;
  trade conditions govern price and volume independently. Extended `T` trades
  update minute bars; bars can be omitted if only price-ineligible trades occur.
  Volume is not every possible reported print. IEX is single-venue and rejected
  as an implicit full-market substitute. Actual SOXX behavior remains untested.
- Massive: qualified-trade OHLCV covering pre/RTH/post; timestamp session
  filtering, next_url pagination, max50,000 **base** aggregates. A missing
  aggregate does not prove no trades/healthy feed; quote/trade/condition or
  provider-health evidence would be needed. Actual SOXX grid remains unknown.
- Databento: MINI volume aggregates only component venues; direct-venue bars
  are venue-specific. OHLCV interval timing is based on trade receive timestamps
  per schema docs; native daily is UTC, not the frozen RTH Daily. Choosing a
  subset/blend changes research inputs and cannot happen silently.
- Twelve Data: official page distinguishes approximately5% real-time venue
  coverage from historical/end-of-day100% market volume after next-day midnight.
  The exact SOXX historical15m extended-volume realization is UNVERIFIED;
  a daily coverage claim does not certify this endpoint's every extended slot.

## Actions, units and causal admission

No existing action certificate was reused. Yahoo's fresh Daily unit spot query
2024-03-06..03-08 returns the2024-03-07 three-for-one event and snapshot price
arrays. An event effective date is not its historical knowledge timestamp.
This query is solely action/unit evidence; no return or outcome is calculated.
It is not an as-traded certificate for any longer interval. Quote OHLC bypasses
local adjustment, but that does not undo provider split restatement; AdjClose
is a separate field and must not be substituted. Dividend feature normalization
and outcome dividend accounting remain separate frozen responsibilities.

The existing interpretation record remains controlling: a fresh, complete
ex-post no-event audit plus exact unit evidence can certify an identity interval
without inventing historical absence-receipt timestamps. Where actual actions
are required, effective time and required evidence knowledge time still apply.
This audit neither strengthens that frozen rule nor supplies the missing new
interval certificate.

| Candidate | Raw/adjustment evidence | Action/knowledge evidence | Daily/intraday compatibility / admission |
| --- | --- | --- | --- |
| Yahoo | Current split-normalized snapshot; no general raw/PIT assertion. | Current split event exists; historical publication/revision availability UNKNOWN. | Fresh full interval unit/cross-source evidence absent. BLOCKED_ON_ACTION_PROVENANCE and BLOCKED_ON_UNIT_COMPATIBILITY for expansion. |
| Alpaca | Docs: adjustment=raw; split also adjusts volume, dividend adjusts price, all adds spin-offs. | Events API exists but explicitly has no creation-time guarantee. Endpoints401. Effective dates cannot stand in for historical receipt. | Raw Daily must still satisfy official RTH/auction semantics; provider daily price/volume trade-condition rules differ from minute rules. Requires interval-specific price/action join and knowledge audit. No PASS from credential alone. |
| Massive | Explicit adjusted=false yields raw split-unadjusted bars; default split-adjusted, not dividend-adjusted. | Split execution overnight, including premarket on effective date; current historical factors normalize to today's units and must not be used causally. No demonstrated historical record receipt/revision archive. | Raw Daily/intraday units potentially interpretable, but RTH Daily contract and new interval/action timing cross-check unverified. Admission BLOCKED. |
| Databento | Trade-derived venue prices; scaled integer units documented; dataset schema and bar clock require explicit comparison. | Corporate-action docs include effective/ex dates, ts_record (last change), ts_created (record addition). Those fields must be verified on actual SOXX records, not backdated to event_date. | UTC daily cannot substitute for official RTH. Selected venue/blend, action archive, and RTH bridge absent. Admission BLOCKED. |
| Twelve Data | Probe requested adjust=none but401 returned no OHLC. Adjustment/raw/volume behavior cannot be confirmed from this probe. | Existing public split table is current history, not knowledge provenance for a new interval. Actual API actions unavailable. | Exact Daily/intraday units, raw settings and knowledge timestamps UNKNOWN; BLOCKED_ON_ACTION_PROVENANCE/UNIT_COMPATIBILITY/volume verification pending. |

Expanded data is **DISCOVERY only**. Historical bar-end availability, when
admitted by the existing contract, is a research assumption, never reconstructed
live/shadow PIT. Later price revisions cannot be certified away by raw=true,
and current action lists alone do not prove historical knowledge. A candidate
must obtain its own causal transform/identity evidence before any signal replay.

No new strategy replay, candidate search, outcome/performance lookup or tuning
was performed. Current candidate stream0, ZERO_SIGNAL and profitability NOT_RUN
remain preserved. Frozen thresholds, MACD, Daily/1H/15m/composer,126-session
confirmation2026-10-12..2027-04-13, stopping rule and evaluation protocol remain
unchanged; phase exit6 is INCOMPLETE.

## Smallest next P0 and reversible choices

`LONG_HISTORY_ACCESS_PATH_DECISION` asks only whether to make an existing
read-only historical account available for a **small admission audit**, or
which account/data access route the owner wants to authorize. It does not
authorize provider migration or mass capture. A credential unblocks probing;
it does not guarantee admissibility. No evidence supports requiring a paid
plan at this point.

Realistic options are free Alpaca historical SIP account access (documented
since2016), free Massive Basic access (documented2 years/minute aggregates),
or existing Twelve Data access (exact SOXX extended depth/volume unverified).
Databento is an alternative if actual raw/record-time evidence proves necessary;
its component venue mix and usage price must first be made concrete. Paid
Massive5/10-year plans are optional extensions, not prerequisites inferred
from missing credentials. Cost alone does not rank or select these feeds.

Choosing which account to probe is reversible and isolated. Frozen semantics,
existing vintages and the confirmation window survive a rejected probe. A paid
subscription can be cancelled under its provider terms, but money already
spent is not assumed refundable. Data from different feeds cannot be pooled
or treated as equivalent without unit/volume/session/action admission.

After a selected route passes the actual admission audit, the next action
becomes `LONGER_IMMUTABLE_DISCOVERY_CAPTURE`: minimal raw-response archival,
fixed request/pages, exact range and hash, expected-grid/unsupported-session
diagnostics, interval-specific action/unit evidence and offline identity proof.
No capture is routed now. New evidence cannot guarantee an informative cohort.

## Verification and provenance

`network-probes-*.json`, `boundary-*.json` and raw SHA256-addressed responses
record request parameters, actual capture time, authorization, provider error
and diagnostic counts. Public primary sources are indexed in
`documentation-*.json`; some Databento HTTP pages are JS shells and the
content-bearing official web extracts are separately identified in
`source-notes.json`. Documentation is never actual-access evidence.

Pure tests in `tests/test_h0001_long_history_audit.py` cover zero/missing/null,
DST, early close, invalid latest rows, incomplete bars, malformed/error results,
credential non-disclosure and immutable collisions. No test calls a provider.
Targeted13 passed. Final whole-regression results and unchanged preexisting
source/evidence hashes are recorded in `test-report.json` and
`preservation.json`. The network audit is separate from deterministic tests.
