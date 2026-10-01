# Versioned extended-session research capability

Implemented on `v2-c0-extended-session-contract`, based on
`73b5d3d5c096c0a2612c39191e6fd4b7980d8f7a`. This is a generic research
data/replay extension, not H0001 C1. H0001 stays **DRAFT / BLOCKED_ON_DECISIONS**;
chart parity stays **UNVERIFIED**. No market data was fetched.

Session-scope correction on 2026-10-01, from
`1b3361a5f7c84765210f4f8b627ed87cbb977a7b`: the current draft is
`h0001_r03_spec_v5`. H1-SESSION applies to 15m/1H intraday only. Daily regime
session is an independent unresolved C1 decision; generic engine availability
does not authorize a strategy selection. H0001-r03 source bytes are unchanged.

## Two independent capabilities

| Contract | Preserved RTH | New extended |
|---|---|---|
| Session profile | `XNYS_RTH` | `US_EQUITY_EXTENDED_04_20` |
| C1 capability profile | `v2_ab_c1_signal_v1` | `v2_extended_c1_signal_v1` |
| Availability | `atomic_known_at_batch_v1` | `atomic_known_at_batch_v1` |
| Continuity | `xnys_completed_grid_v1` | `us_equity_extended_04_20_completed_grid_v1` |
| Aggregation (1H and Daily) | `xnys_open_anchored_short_final_v1` | `us_equity_extended_04_anchored_full_session_v1` |
| Session definition | `xnys_official_rth_v1` | `us_equity_extended_04_20_standard_days_v1` |

Availability deliberately reuses the unchanged V2-A atomic contract. No venue,
broker or provider is inferred from the extended research grid. Input remains
SYNTHETIC, 15m, explicit per-bar known_at, unadjusted prices, and
NONE_CONFIRMED corporate actions. Production, paper and legacy code are unchanged.

`sessions.py` supplies immutable profiles and local calendar boundaries.
`MarketDataset` requires `session_policy=RTH_EXTENDED` and the exact
`EXTENDED_PROFILE.metadata` in `manifest.session_contract`. Each extended bar's
provenance explicitly records `session_profile`, `session_definition`, and
`session_segment`. Segments are PREMARKET [04:00,09:30), RTH [09:30,16:00), and
AFTER_HOURS [16:00,20:00). Higher-frame bars spanning segments use MIXED.
Regular boundaries are also present in the manifest. Incorrect/mixed metadata
is rejected; omitted metadata never silently selects extended mode.

## Completed views

On a supported date, exactly 64 base intervals run from 04:00–04:15 through
19:45–20:00 **America/New_York**. Before-04:00, after-20:00, non-15m and
off-grid intervals are rejected.

Extended 1H uses sixteen buckets: 04:00–05:00, 05:00–06:00, …, 19:00–20:00.
Each needs all four completed 15m constituents. The 09:00–10:00 bucket spans
premarket and RTH; the anchor never switches to 09:30 at the regular open.
Extended Daily is the entire 04:00–20:00 local session, requiring all 64 inputs.
It is distinct from RTH Daily (official open to official close).

For both profiles, aggregate open/close are the first/last constituent values,
high/low are extrema, volume is summed, and known_at is the maximum constituent
known_at. The bucket must have ended and every expected input must have arrived.
Missing/delayed inputs never produce partial higher-frame candles. A repair
may publish an older completed bucket only at its actual arrival time.

The existing `Daily`/`1H` timeframe vocabulary is retained. Profile metadata,
aggregation version, start/end, dataset hash and feature continuity parameters
make the semantics distinct without another timeframe enum or legacy schema
migration. Detached contexts reject mixed session profiles. Features reject a
profile/continuity mismatch, even when an RTH bar happens to fit an extended
hour boundary. Extended aggregate features require the extended aggregation
provenance. Existing default constructors and RTH serialized bar fields remain.

## Continuity, DST and unsupported dates

The extended completed grid advances every 15m (or every completed 1H/Daily
observation). 09:30 and 16:00 are segment transitions, not breaks. A session
close at 20:00 followed by the next XNYS session open at 04:00 is continuous;
overnight, weekends and XNYS holidays add no missing observations. Missing
in-session slots or an omitted trading session break continuity. No price is
filled, carried, or synthesized to repair history.

All boundaries are constructed using IANA `America/New_York` / `zoneinfo`,
then converted to aware UTC. Session labels use the **local date**. Winter
20:00 is next-day 01:00 UTC; it still belongs to the prior local session.
Spring/fall DST change UTC timestamps and elapsed overnight/weekend durations,
not the number or local anchors of supported buckets.

Only dates whose XNYS calendar has an official 09:30–16:00 local regular
session are supported by extended v1. **An early-close or other nonstandard
XNYS date is unsupported for the entire extended session**, including its
premarket. The loader rejects datasets spanning such a date even if no bars
were supplied for it. Feature continuity cannot skip it as a holiday. This is
a fail-closed limitation, not a claim that no trading occurred. Out-of-calendar
dates likewise fail; pinned exchange_calendars/tzdata versions are in replay
code provenance. RTH continues to use official early closes and a short final
1H bucket under its original contract.

Rationale: extended availability is not generically specified by the XNYS
regular-close calendar. [NYSE's holiday and hours reference](https://www.nyse.com/markets/hours-calendars)
lists different sessions across markets and special late-session closes on
early-close dates. A specific venue's 17:00 exception cannot establish a
provider-independent 20:00 research grid. A future supported exception needs
a separate reviewed, versioned availability/session contract. No such bars or
exception policy are invented here.

This conservative rule can prevent assembling 130 contiguous Daily observations
across certain date ranges. The 130-count gate is never lowered to compensate.
As in V2-B, feature continuity checks internal history: the first available
observation defines the origin, and trailing unsupplied observations are not
assumed available. Dataset gap diagnostics additionally expose missing leading
slots within the first supplied session. There is no provider coverage claim.

## Causality and features

Replay uses the manifest-selected aggregator. At every callback all bars have
`known_at <= as_of`. All symbols and delayed bars with the same known_at form
one atomic batch, including newly completed aggregates. Retained contexts and
results are immutable; future values cannot change a prefix. Profile metadata
is included in dataset/run provenance; feature continuity is in specification
hashes and extended bar provenance in causal input hashes.

EMA, MACD, scalar projections, rolling transforms, ATR and confirmed fractal
primitives accept the new continuity version explicitly. Their existing numeric
conventions remain unchanged. This adds no H0001 relative transform selection,
swing selection, threshold, regime, on_event, fill or portfolio logic.

## First H0001 decision bundle

Only these five existing decision IDs remain resolved in `h0001_r03_spec_v5`:

| Decision | Selected value |
|---|---|
| H1-SESSION | RTH_EXTENDED for 15m/1H intraday only; explicit extended engine profile |
| H1-BASE | 15m |
| H1-EMA-SEED | first_observation; first_macd_observation; close; `macd_first_observation_recursive_v1` |
| H1-MACD-HISTORY | Daily=130, 1H=130, 15m=130 |
| H1-HISTORY-ORIGIN | `available_completed_history_prefix_v1`: all available completed causal contiguous history across sessions, no per-session reset |

Premarket occurs in the observed H0001 examples, and 15m was already its
smallest authoritative timeframe. The warmup reduces first-observation seed
influence to about 0.0045% after 130 EMA26 updates. Precisely, 130 observations
have 129 recursive updates and residual `(25/27)^129`, about 0.0049%; the
selected gate is **130 observations**, not 131. MACD minimum history and a
future relative-transform lookback are independent. Full history continues
past 130; the engine does not truncate its EMA calculation to 130 bars.

New **H1-DAILY-SESSION** is a C1 implementation blocker. Its separate typed
`timeframe_contracts.daily_session_policy` has value **UNRESOLVED** and candidates
**RTH_DAILY / EXTENDED_DAILY**. RTH Daily uses official open–close; generic
Extended Daily uses 04:00–20:00 on supported dates. These differ in OHLCV,
completion/known_at, aggregation provenance, input hashes and feature continuity.
The generic extended Daily implementation is preserved; it selects no H0001 rule.

There remain **47 C1 blockers, 17 performance blockers, 7 optional decisions**:
**71 unresolved decision IDs / 98 unresolved parameter or transition paths**.
The total inventory is **76 decision IDs**. Compared with v4, total decisions
75→76, C1 blockers 46→47, unresolved decisions 70→71 and unresolved paths 97→98
are normal +1 changes from adding H1-DAILY-SESSION. Performance/optional counts,
all existing parameter values and state transitions are preserved. Only
H1-SESSION's descriptive scope is clarified; its selected value is unchanged.
`require_session_capability()` accepts extended intraday plus unresolved Daily;
`require_daily_session_capability()` requires an explicit independent Daily choice.
`require_c1_ready()` still fails because it requires FROZEN with no C1 blockers.
Even if all other C1 decisions are resolved in a test fixture, unresolved Daily
prevents freeze/admission. Historical v3/v4 remain readable but cannot gain
C1 admission by inferring Daily from intraday. Daily MACD admission uses the
Daily profile's continuity; 15m/1H admission uses the intraday profile.
A structurally frozen fixture with RTH_EXTENDED plus stale RTH capability fails;
a fully compatible extended fixture passes admission only in synthetic tests.
This contract does not implement a strategy or combine different profiles into
one replay context; existing mixed-profile rejection remains in force.

`RESEARCH_CAPTURE.md` does not require a new hypothesis revision for these
separate pre-experiment executable-spec selections. The hypothesis is not
edited and no r04 is created. r03 SHA-256 is
`35e13276056a36d6a06de04611720fd286113f0e5db1e4255af6ceeb6a0f0bc2` (Git/LF),
`abdd4f10d127ee7614a4eead734d1bfbf7dc1897ec368f8a3b70a1645e2552fc`
(unchanged local CRLF bytes). New canonical executable-spec SHA-256:
`ab0c1136d47bf1ce6b46ff7e46824b59cf715d28db93bf665b77477a8f0a50e6`.

Selected intraday strategy session: extended 04:00–20:00 ET; Daily regime
session: **UNRESOLVED**. Selected engine 1H:
04:00 anchored. Observed provider: **UNRESOLVED**. Observed exact 1H convention:
**UNVERIFIED** (its decision remains UNRESOLVED in YAML). Overall
`parity_status=UNVERIFIED`. Selection is compatible with the observed premarket
chart timing; it is not evidence of matching the user's chart provider.

## V2-D_BLOCKER: extended early-close availability

The existing extended v1 restriction is unchanged: an early-close or other
nonstandard XNYS date rejects the entire extended session, including premarket,
and a dataset spanning that date fails closed. This is an explicit
**V2-D_BLOCKER** for downstream real-data coverage/replay, independent of the
H1-DAILY-SESSION strategy decision. It can prevent 130 contiguous observations
over some date ranges. Resolving Daily to RTH_DAILY would not unblock extended
15m/1H data on those dates. A separately reviewed versioned availability/session
contract and coverage evidence are needed; this patch adds no exception,
calendar skipping, fabricated bars, or lower history gate.

## Verification

`tests/test_research_v2_extended.py` covers base bounds/segments, both first
hour buckets, whole-day OHLCV/completion, missing/late evidence, same-known-at
atomic multisymbol publication, segment prefix invariance, overnight/weekends,
both DST transitions, holidays/early closes, local dates crossing UTC midnight,
130-history readiness on all three frames, deterministic seed/no session reset,
profile mismatch, admission, and preservation of all other decisions and r03.
Existing V2-A/B/continuity test files remain byte-identical. C0 assertions were
updated for the authorized five resolutions, and RTH admission fixtures still
explicitly select the original profile. Prior v4 full suite: **723 passed in
155.86s**, including 59 extended tests, 130 unchanged RTH/V2-A/B tests and 280 C0
tests; no failures, skips or pytest warnings. `git diff --check` and CLI
`--help` pass. An additional isolated SQLite smoke check verifies extended
dataset roundtrip, versioned run metadata and identical repeated replay hashes.

The v5 regression file additionally verifies extended intraday with unresolved
Daily, the isolated Daily C1 blocker, both independent Daily choices, rejection
of implicit Daily in legacy frozen fixtures, exact count/preservation deltas,
and distinct Daily OHLCV/availability/input hashes on identical overlapping RTH
inputs. Future after-hours edits and delayed inputs preserve causal prefixes.
Current v5 full suite: **730 passed in 156.66s**, no failures, skips or pytest
warnings. All prior **723 tests** are retained; six Daily session regressions
and one additional case in the existing mandatory-field omission parametrization
account for the seven added tests. `git diff --check` passes. Source hypothesis,
session/aggregation implementation and V2-A/B/continuity tests have no diff from
the starting commit. PROJECT_STATUS.md records the current counts and verification.
