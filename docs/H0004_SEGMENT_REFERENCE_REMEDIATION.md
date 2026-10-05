# H0004 pre-freeze segment reference correction

Owner rejected pooled session-segment reference before any H0004 outcome, based
only on trial1 mechanical compressed rates: premarket255/1305, RTH174/1560,
after-hours446/960. H0004 thesis, normalized16-bar range, lower20%, episode and
strict completed-close breakout remain unchanged. Trial1 is immutable historical
frequency research, not the final signal. Trial2 is the final authorized
pre-outcome semantic trial; no third variant or count-target tuning.

## Reference population

Assign each measurement to its **current completed bar** segment using existing
half-open segment contract: bars ending09:30ET are PREMARKET; starting09:30
are RTH; ending16:00 are RTH; starting16:00 are AFTER_HOURS. A16-bar price range
can include earlier segments or the prior session, but reference membership is
always the completed bar's own segment, never the full window's dominant segment.

Use all eligible normalized-range measurements from exactly the previous ten
**official XNYS sessions**, for that same segment. Entire current session excluded,
including causal earlier same-segment bars. No last-ten-available-date substitution,
no640-same-segment requirement and no future/current-day observation in reference.
An input session is complete only with all64 admitted scheduled15m bars04-20ET.
Each stored measure needs a valid contiguous16-bar window; it does not need an
already READY percentile. Thus first session's first15 measurements legitimately
remain unavailable; its eligible premarket population has7 values, not22. With
ten complete input sessions reference counts initially205/260/160, then normally
220/260/160 once initial warmup session rolls out. Variable eligible counts are
reported, not filled or calibrated. Current empirical upper-inclusive rank is
count(reference <= current)/reference_count; ties conservative; rank<=.20.
All-zero/empty reference is unavailable, never infinity or automatic compression.

Reference/session price history is cleared on any missing scheduled-slot gap;
active range cancels and remains disarmed until observed READY noncompression.
Initial partial input sessions are not completed reference sessions. Unsupported
official dates cannot be silently skipped as holidays or replaced with RTH;
invalid provided slots poison the stream, same as trial1. A chronological gap
across an unsupported/missing day clears warmup and references. Session closure
otherwise does not clear history or consume episode validity slots.

## Retained signal and authorization

Freeze max high/min low from16 completed scheduled bars. Publication cannot be its
own breakout. First later completed close strictly above high emits once. Valid
subsequent slots1..16 inclusive; slot17 expires before evaluation. Close strictly
below low cancels; equality at either boundary is not breakout/cancellation.
READY noncompression after retirement then READY compression rearms. No MACD,
volume, relative strength, QQQ, contextual trend, buffer or retest. Existing H0004
immutable bar/feature/range/event containers and common causal session utilities
are reused; trial1 execution code is preserved. Trial2 has separate signal hash,
candidate/range stream and evidence. Input is identical admitted SIP/raw SOXX70.

**H0004 v1 studies compression and breakout across consecutive admitted trading
slots, not continuous wall-clock hours. A range may therefore span or survive a
market closure.**

This is own-time-of-day volatility meaning, not a claim that compression rates
must equal20% or that outcome performance improves. All prior research exposure
is recorded; sealed70 remains exploratory discovery, not fresh confirmation.
Frequency runner seals definition/source/input and compares every prior protected
file to Git BASE before replay. It reads no candidate future windows and imports
no forward evaluator. Full repeat and prefix audit preserve deterministic hashes.

If causal/deterministic/nonzero/mechanically valid, owner has already approved
these final semantics. Freeze then preregister before any future-return/MFE/MAE,
efficacy, profitability or confirmation access. Primary proposed evaluation is
16-slot SOXX gross forward close **directional** return: four scheduled trading
hours for the short continuation question. No relative benchmark or fill/account
profitability meaning is introduced. Positive direction alone cannot establish
incremental timing Alpha versus market drift; protocol must state that limit.
