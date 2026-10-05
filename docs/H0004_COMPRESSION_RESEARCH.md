# H0004 pre-frequency design

Owner selected LONG `VOLATILITY_COMPRESSION_BREAKOUT_CONTINUATION` on 2026-10-05.
Question: does an upside completed-close breakout of a recently unusually quiet
SOXX range precede short upward continuation? This action tests causal mechanical
frequency, not that future directional assertion.

## One ex-ante proposal

Primary measure is `(highest high - lowest low) / current completed close` over
16 contiguous scheduled 15m bars: four trading hours. It directly represents the
enclosing range used by the breakout. ATR/median true range instead measures
individual movement, which can be quiet even while price travels directionally;
no ATR comparator is executed. Division makes the measure price-scale invariant.

Compare current measure to the immediately **previous** 640 such observations
(ten full extended sessions). Empirical upper-inclusive rank is
`count(previous_measure <= current_measure) / 640`; rank <= 0.20 is compression.
Ties count conservatively in full. Current measurement is appended only after
classification; baseline is strictly past. All-zero history is UNAVAILABLE.
First feature READY is bar 656 (16+640). Historical windows overlap each other
and current window; this is causal, not an independent-sample certification.
All session segments share one own-history distribution. This intentionally
includes normal time-of-day variation; a segment-conditioned baseline would be
a separate semantic revision. No fixed dollar threshold or future fitting.

16 bars supply persistence without another K-bar gate. Four hours, ten-session
reference, bottom quintile and a four-hour wait are interpretable provisional
units selected before market replay. No target count or rally is used to select
them. Review considers range vs true range conceptually; **one** tuple is run.

## Range and episode

First armed READY compression publishes frozen window max high/min low and a
prefix/spec/vintage-bound identity. The publication bar cannot break its own
range. Subsequent slots 1 through 16 inclusive can emit the first completed
`close > frozen high`. Equality and intrabar high touch do not qualify. No buffer,
volume, wick, retest or confirmation condition. The event consumes the episode.
New later bars never update the range boundaries.

Completed `close < frozen low` cancels before breakout; equality does not cancel.
At slot 17 the episode expires before any breakout evaluation. Expiration bounds
the link to a recent compression rather than an indefinitely retained old level.
Ending compression alone does not cancel: expansion may be the desired breakout.
After consumption/cancellation/expiration, a READY noncompression observation
with no active range is required before another READY compressed publication.
That noncompression may be on the retirement bar. No rolling boundary refresh,
no repeated events while above the same range, and no implicit rearm by expiry.
Consecutive feature states, episodes and emitted candidates are separate counts.

## Input/session causality

Reuse the admission-certified 70-session Alpaca SIP/raw SOXX 15m vintage only,
never QQQ, a new provider or Daily/H1 inputs. Exact extended standard-day grid
04:00-20:00 America/New_York is 64 slots/session. Official calendar next-session
adjacency retains history and active episode; overnight/weekend consume no slots.
Thus a four-trading-hour window/wait can cross a closure. Missing scheduled slots
cancel an active range, clear numeric warmup and disarm; an observed READY
noncompression is still required to rearm. Unsupported early-close/session/slot,
invalid OHLC, nonfinite calculation or mixed vintage poison the stream fail-closed.
Repeated identity/correction is rejected before mutation; new vintage requires
new replay. No live correction can retract or regenerate a published candidate.

Admission is ex-post historical research, with assumed bar-end availability and
split-only unit identity, not live PIT or independent price/liquidity certification.
Existing H0001/H0002/H0003 exposures are recorded; shared input is discovery,
never fresh confirmation. Outcomes and dividend accounting require a later
separately frozen/preregistered contract.

## Authority and independence

Signal module imports only common digest/time, immutable payload, causal OHLC
continuity and session utilities. It has no prior strategy-state dependency and
accepts one detached bar, never a loader/dataset/forward accessor. Frequency runner
loads only the portable intraday vintage and admission metadata. It imports no
forward outcome module; guards block network, dataset queries, stores and known
outcome/efficacy paths through strings resolved solely for auditing. No candidate
future window lookup, MFE/MAE, return/profitability or confirmation evaluation.

Preexecution manifest binds the tuple, source and immutable input before the
first real replay and protects all previous tracked files. Real repeats and a
chronological prefix compare event hashes and causal trace. Frequency 0/sparse
or high would trigger bottleneck/duplication analysis, never automatic tuning.
Final range/percentile/window/persistence/expiry/session meaning and signal freeze
belong to the owner. Horizon/control/cost/stopping/confirmation remain unknown;
no efficacy execution is authorized. Next P0 after mechanical evidence is
`H0004_SIGNAL_FREEZE_PREREGISTRATION / USER_DECISION_REQUIRED` if executable.
