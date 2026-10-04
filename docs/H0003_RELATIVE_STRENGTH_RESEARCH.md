# H0003 causal leadership proposal

Owner thesis selection is complete: independent LONG directional research into
semiconductor leadership continuation versus QQQ. QQQ is a Nasdaq technology/growth
comparator, not the whole market. H0001 reversal and H0002 price defense contracts
and evidence remain untouched. SPY is deferred, with no benchmark ranking.

Pre-frequency proposal: `RS_t = (SOXX_close_t / SOXX_close_(t-64) - 1)
- (QQQ_close_t / QQQ_close_(t-64) - 1)`. 64 scheduled completed extended slots
are one 16-hour session equivalent, not a wall-clock day and not an H1 filter.
65 contiguous paired closes are required. Overnight/weekend closures consume no
steps; gaps do. The 192-slot alternative means multi-session rather than recent
leadership and is not implemented or ranked. One window, one definition, no grid.

Positive relative return sustained for four consecutive READY observations is the
proposed primary: it measures persistent outperformance without an arbitrary
magnitude cutoff or rolling-distribution calibration. Upper percentile instead
means unusually strong leadership and requires extra warmup; it is deferred.
Four observations are one hour of persistence on the 15m grid, not an aggregated
H1 feature. This parameter is provisional and needs owner signal freeze.

The proposed guard is current SOXX trailing return >=0 on the same 64 slots.
Relative-only could select SOXX -5% versus QQQ -8%, a defensive loser rather than
LONG continuation. Benchmark non-crash requires an additional threshold and a
market-regime thesis. Neither alternative is run as a separate signal. Guard
pass/fail counts are reported as mechanical diagnostics only.

INACTIVE positive run -> four positive observations -> ACTIVE episode. Episode
identity binds spec, paired immutable vintage identities and first positive slot.
Emit the first guard-eligible completed slot once. ACTIVE survives guard failure;
only READY RS<=0 terminates and rearms. A missing/invalid pair blocks emission,
clears numerical warmup and persistence, but retains a consumed episode lock until
an observed READY nonpositive RS. Thus data loss cannot invent a second event in
an unobservably continuous leadership episode. Sessions do not rearm episodes.
No positions, entry fills or exit hypothesis are inferred.

Both series must have exact start/end, completed 15m slot and session identity,
Alpaca SIP provider/feed, raw USD/as-traded-share price basis, unnormalized cash
dividends, compatible split-identity interval admission and the same historical
bar-end assumed availability. No forward fill, stale/future benchmark or partial
pair. Mixed units/actions/provenance fail closed. Invalid data cannot publish an
event. Revisions/duplicate timestamps require a new vintage and replay. A future
suffix cannot change an already returned immutable step or event.

QQQ admission uses the same fixed 70-session interval before signal replay,
explicit SIP/raw/asof/currency parameters, repeat pagination, raw/split equality,
complete corporate-action pagination and exact supported 04-20ET grid. Admission
is ex-post dataset certification, never a historical feature or absence receipt.
QQQ receives its own immutable capture; SOXX retains its admitted vintage.
Different prices for the two assets are normal; adjustment conventions must match.
No transformation is attempted across an unproven action/unit boundary.

Full extended scope is proposed. Segment readiness/missing counts are evidence;
no performance-driven RTH restriction. Equal slots do not prove equal liquidity,
quote quality or live latency in extended trading. Admission proves observed bar
compatibility only. Alpaca's [historical bars reference](https://docs.alpaca.markets/us/reference/stockbars)
defines explicit feed, adjustment and currency parameters; actual archived receipts
govern admission rather than advertised plan capabilities.

Frequency runner seals source/spec hashes before loading prices, prohibits outcome,
forward-window, efficacy, database and network access during replay, rereads raw
receipt chains and verifies preservation of preexisting tracked research files.
The full chronological input snapshot is read only for causal feature replay;
there are no event-conditioned future price or label queries. Test fixtures are
synthetic mechanics, never actual efficacy. Final signal freeze is a user decision;
preregistration/evaluation must follow in another action before outcomes.
