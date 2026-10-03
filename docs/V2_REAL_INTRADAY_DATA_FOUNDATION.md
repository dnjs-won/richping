# V2 real 15m data foundation — 2026-10-03

Status: **IMPLEMENTED / EXECUTED_ON_REAL_DATA / EVIDENCE_PRODUCED** on
`v2-real-intraday-data-foundation`, from extended workstream head `7197fe3`.
Integration into main is pending. H0001 profitability, chart parity, executable
entry composition and frozen Daily input admission are **not** established.

## Provider decision

Use **Yahoo chart via installed yfinance 1.7.0**, adapter
`yahoo_chart_15m_v1`, for this first single-symbol historical research capture.
The decision is limited to reproducible intraday price research on the measured
range; this is not a selection of a production feed, volume source, Daily PIT
action source, or live/shadow data source.

[yfinance PriceHistory documentation](https://ranaroussi.github.io/yfinance/reference/yfinance.price_history.html)
specifies 15m and pre/post support but only the most recent 60 calendar days of
intraday history. Start is inclusive, end exclusive. Neither pagination nor
chunking can retrieve history outside that rolling window. US equities/ETFs
are supported; SOXX coverage was measured directly below. No guaranteed numeric
rate limit or SLA is documented: 429/non-200 fails without retries or fallback.
One chart response contains the requested range, with no pagination token in
the observed response; array lengths and the entire requested grid are checked
rather than assuming an HTTP success is complete.

`Ticker.history(prepost=True, auto_adjust=False, back_adjust=False, repair=False,
actions=True, keepna=True)` was first probed. Its 2,624 returned rows hid a
2,625th raw quote. [PriceHistory source](https://github.com/ranaroussi/yfinance/blob/main/yfinance/scrapers/history.py)
also explicitly deduplicates rows. The adapter therefore reuses yfinance's
Yahoo cookie/HTTP transport (`YfData.get`) but normalizes the original chart
arrays itself. This private transport dependency is recorded with the library
version; changes need review. There is no DataFrame sorting, deduplication,
null-volume substitution, interval resampling, price repair or adjustment.

The chart identifies America/New_York, ETF, USD, 15m, and pre/post availability.
Epoch seconds label interval starts, normalized to aware UTC; sessions retain
the NY local date. Fixed 15m intervals and the 04:00–20:00 ET calendar grid are
validated, including segment boundaries and DST via existing session helpers.

Prices are named `yahoo_chart_snapshot_ohlc_no_local_adjustment`. This does **not**
mean raw-as-traded PIT prices. Yahoo prices can be restated for splits, and
`auto_adjust=False` does not undo provider-side splits. The maintainer confirms
that [unadjusted-for-split prices require reversing adjustments](https://github.com/ranaroussi/yfinance/discussions/1682).
Snapshot action metadata is retained, not treated as complete historical
knowledge. The actual capture includes a $0.325 dividend dated 2026-09-15 and
no split event in the requested response. Prices were not dividend normalized;
no outcome dividend accounting was implemented. Corporate action state stays
**UNKNOWN**, including on derived bars.

All 1,558 extended-hours bars have provider volume zero. They remain exactly
zero; this is not evidence of zero trades or valid tape volume. The current
price-based 15m path can be inspected, but volume-dependent research requires
another measured source. No volume strategy or provider parity was added.

Alternatives reviewed from primary sources:

| Candidate | Relevant contract | Decision |
|---|---|---|
| [Alpaca historical bars](https://docs.alpaca.markets/us/reference/stockbars), [plans](https://docs.alpaca.markets/us/docs/about-market-data-api), [FAQ](https://docs.alpaca.markets/us/docs/market-data-faq) | US stocks/ETFs since 2016; 15Min; UTC start timestamps; explicit raw/split/dividend adjustments; page tokens up to 10,000 rows/page; historical SIP available without paid realtime access when end is >15m old; Basic 200 calls/min | Most realistic next long-history candidate: explicitly SIP, never implicit IEX fallback. Requires account credentials, none present among APCA/ALPACA environment variable names. SOXX/full-grid/early-close/action semantics still need actual capture validation; no Alpaca implementation or smoke claim. |
| [Massive custom bars](https://massive.com/docs/rest/stocks/aggregates/custom-bars) | US stocks, pre/RTH/post; 15 minute multiplier; Unix-ms start; split-adjusted toggle; next_url; qualifying-trade omissions; plan-dependent multi-year history | Credible alternative when access is available; no credentials or entitlement smoke. |
| [Twelve Data extended hours](https://support.twelvedata.com/en/articles/5195429-pre-post-market-data), [history](https://support.twelvedata.com/en/articles/5656039-how-to-get-historical-prices) | Historical 04:00–20:00 for records older than one day; 15m; history depth varies by instrument | Candidate only, not selected without SOXX depth and adjustment/entitlement evidence. Realtime 07:00 start must not be confused with historical 04:00. |

Yahoo meets the first measured intraday dataset/session goal. Its 60-day
lookback does **not** supply a multi-year efficacy corpus or the frozen Daily
179-observation trend readiness. A separate reviewed RTH Daily/PIT action
input remains necessary; 41 extended Daily aggregates cannot substitute for it.

## Historical availability and admission

`quality=REAL_HISTORICAL_RESEARCH` is distinct from the unchanged SYNTHETIC
contract. Required manifest/per-bar provenance includes provider/library/adapter
versions, capture time, timezone, session profile, price/action basis, raw
capture hash, symbol, and requested range. Every SQLite reload reconstructs
and validates the contract before comparing the full content hash.

`historical_snapshot_bar_end_assumed_v1` sets `known_at=end_at` as an **explicit
research assumption**. Actual knowledge of this snapshot begins at
`captured_at`. Market-time replay protects prefix ordering under that assumption;
it does not prove historical receipt, publication latency, revision availability
or live/shadow PIT causality. Run metadata and results say real historical
snapshot research, never SYNTHETIC or PIT evidence.

The existing aggregator/features may process UNKNOWN actions only with this
explicit real snapshot policy. Derived bars retain UNKNOWN and provenance.
Synthetic UNKNOWN/PRESENT inputs still fail as before. The frozen Daily PIT
strategy contract, its typed input requirements and strategy code are unchanged;
this generic price-research admission does not fulfill that contract.

Malformed OHLCV, duplicates, backward timestamps, partial arrays/results,
unexpected symbol/timezone/timeframe/currency, session violations, off-grid
bars, mixed provenance and identity collisions are rejected. Missing leading,
internal, trailing and wholly absent requested sessions are reported without
fill. A structurally valid but incomplete capture may be persisted only as
`coverage_status=UNAVAILABLE` diagnostic input; replay and offline iteration
refuse it before strategy callbacks. An absent slot is UNKNOWN/UNAVAILABLE,
because the response cannot establish no trades versus provider/collection
failure. A complete grid is structural coverage, not independent verification
of price correctness or liquidity.

Extended v1's early-close rule is unchanged: a range spanning a nonstandard
session cannot be materialized. A rejection artifact names the unsupported
day and its observed row count, and raw capture survives. The first actual
range contains no such session. Early-close generalization remains backlog.

## Persistence and vintage algorithm

Original decoded response and request are archived as canonical, content-addressed
JSON at `var/research/v2-real/raw/<capture_hash>.json`. This is a decoded-source
hash, not a claim of byte-identical HTTP wire capture. No crumb/cookie/credential
is included. Existing `v2_datasets`/`v2_bars`, schema version and SQLite immutable
triggers are reused. Raw data and local DB remain outside Git under ignored
`var/`; small coverage/offline/smoke evidence is versioned in
`research/data_evidence/v2-real-20261003/`.

Default update overlap is **7 calendar days** before the parent's exclusive
end, bounded by its original start. A new labelled vintage combines unchanged
earlier bars (retaining original capture hashes/times) with the whole explicitly
re-requested interval. Overlap OHLCV changes, removed rows and added rows are
listed in the child manifest. Removed rows become gaps in the new vintage;
old rows never mask an incomplete refresh. Old dataset IDs/rows are never
updated. Same identity with different manifest/bars fails. Even a no-revision
refresh has a new capture vintage. Overlap detects only overlap revisions;
arbitrary earlier restatements are not disproved. A split event or library/basis
change requires full recapture, rather than merging potentially incompatible
split vintages. If the Yahoo rolling window no longer reaches the overlap,
update fails; it cannot reconstruct lost history.

## Actual collection and offline evidence

Canonical local DB: `C:/richping/var/research/v2-real/market.sqlite`.
Raw responses and local coverage are also retained under that directory,
independent of worktree cleanup. The ingestion worktree additionally retains
its original `var/research/v2-real/market.sqlite` and source captures.

| Field | v1 evidence |
|---|---|
| dataset_id | `soxx-yahoo-15m-20261003-v1` |
| captured_at | `2026-10-03T03:25:13.015023+00:00` |
| request | SOXX, 2026-08-05 inclusive → 2026-10-02 exclusive |
| actual sessions | 2026-08-05 → 2026-10-01, 41 trading days |
| UTC coverage | 2026-08-05 08:00 → 2026-10-02 00:00 |
| expected / observed | 2,624 / 2,624 |
| pre / RTH / post | 902 / 1,066 / 656 |
| missing / gaps / duplicates / unsupported | 0 / 0 / 0 / 0 |
| content hash | `bb7ac246e4005d49d861301c4acc8261043bcd71818c3bcdbef5f73aa98c59b9` |
| raw capture hash | `b648e187501e5d7fa145c4177c53b86102d38283bf2f1f9638aba1065db1715a` |

The earlier request through 2026-10-02 returned a final **19:59:54** point
after the 19:45 bar. It was rejected as an invalid 15m interval, not silently
dropped/rounded/merged. The successful capture ends the day before that latest
provider session. The current-day boundary is a provider limitation to revisit,
not an authorization to relax the 15m grid.

Actual overlap refresh captured at `2026-10-03T03:29:48.606866+00:00`, covering
2026-09-25 inclusive → 2026-10-02 exclusive. Child
`soxx-yahoo-15m-20261003-v2` has hash
`70cb7069e3d9a941471a2b9774a70e78997aa66f07e27e7c8397cea7caa33d69`.
Revised/deleted/added overlap slots: 0/0/0. Parent reload still has its original
hash. The deliberately changed/retracted provider responses are mock tests,
not claims that an actual provider revision occurred.

`scripts/verify_v2_real_offline.py` runs in a fresh process: socket creation and
connection raise, yfinance is never imported, the DB is opened read-only twice,
both content identities are revalidated, and the file SHA256 is unchanged.
Existing `CompletedAggregator` + `ReplayEvent` stream iteration yields **2,624
events, 656 1H and 41 extended Daily aggregates**, no incomplete buckets, and
identical repeated event hashes. These Daily aggregates are generic extended
views, not the frozen RTH/PIT Daily inputs. No strategy, signals, returns,
performance or parameter search was run. Mock fixtures additionally exercise
the full existing replay engine with identical roundtrip results.

## Commands

Run from `C:/richping/var/worktrees/v2-real`, using the root virtualenv. V2 uses
`--store` rather than legacy `--db`; no operational DB/config is touched.
Use the canonical DB's absolute path to inspect the durable saved vintage.

```powershell
C:/richping/.venv/Scripts/python -m richping research-v2-data sync --symbol SOXX --start 2026-08-05 --end 2026-10-02 --dataset-id fresh-vintage
C:/richping/.venv/Scripts/python -m richping research-v2-data sync --parent soxx-yahoo-15m-20261003-v1 --end 2026-10-02 --overlap-days 7 --dataset-id another-vintage
C:/richping/.venv/Scripts/python -m richping research-v2-data --store C:/richping/var/research/v2-real/market.sqlite list
C:/richping/.venv/Scripts/python -m richping research-v2-data --store C:/richping/var/research/v2-real/market.sqlite inspect soxx-yahoo-15m-20261003-v1
C:/richping/.venv/Scripts/python -m richping research-v2-data --store C:/richping/var/research/v2-real/market.sqlite proof soxx-yahoo-15m-20261003-v1
C:/richping/.venv/Scripts/python -m scripts.verify_v2_real_offline --store C:/richping/var/research/v2-real/market.sqlite --dataset-id soxx-yahoo-15m-20261003-v1 --output C:/richping/var/research/v2-real/offline-proof-v1.json
```

For offline reconstruction from the captured source:

```powershell
C:/richping/.venv/Scripts/python -m richping research-v2-data --store var/research/v2-real/reimport.sqlite import var/research/v2-real/raw/b648e187501e5d7fa145c4177c53b86102d38283bf2f1f9638aba1065db1715a.json --dataset-id soxx-yahoo-15m-20261003-v1
```

Only `sync` imports/calls the provider. Import/list/inspect/proof, features and
replay use fixed local inputs. Save returns coverage JSON and writes JSON plus
Markdown. Exit 0 means structural complete grid, 2 means persisted but unavailable
coverage, and 1 means failure/rejection. Choosing a new label prevents accidental
reuse of an earlier identity. Dates in examples are evidence dates, not a promise
that Yahoo will still serve this range outside its retention window.

## Acceptance and remaining work

All eight `PROJECT_CONTROL.yaml` **data-foundation** acceptance criteria have
evidence: reviewed provider contract; real immutable bars; incremental vintages;
fail-closed validation; measured full-session SOXX; identical offline identity;
JSON coverage; persistence/failure tests. The phase itself remains incomplete:
only its first three exit criteria are established. The next action is
`H0001_MINIMAL_15M_ENTRY_FREEZE`; efficacy and mixed-profile/PIT Daily prerequisites
must not be claimed from this dataset.

The existing synthetic behavioral tests are retained. Historical freeze-only
source-byte assertions now compare the immutable freeze-era implementation
head, while current strategy/frozen decision preservation remains checked.
This permits the authorized data-only CLI/store/replay extension without
rewriting historical claims. Session/feature numeric formulas, frozen strategy
files and V2 SQLite schema were not redesigned.

Main's newer R1 paper change `c48851d` was reviewed but not merged into this
workstream. Main keeps it; the V2 task branch keeps the existing V2 history.
Deliberate integration is still P1, with no force push or broad merge/conflict
refactor in this data task. Main carries only the PM state update.

## Verification results

- New provider/provenance/persistence/failure/offline/incremental tests:
  **41 passed** (4.74s), entirely fixture/mocked HTTP input.
- Full workstream suite: **1,140 passed** (250.58s), no skips or warnings.
  Existing synthetic behavioral/causal tests remain present and pass.
- `git diff --check` and CLI `--help` pass.
- Real API smoke: initial historical capture and explicit overlap refresh
  succeeded. The malformed latest-session response was rejected and archived.
- Actual offline reimport into a separate DB reproduces v1's full content hash.
- Both real vintages have repeated network-disabled reload/aggregation proof.
- These are data/mechanics results; no synthetic or real strategy performance
  is reported.
