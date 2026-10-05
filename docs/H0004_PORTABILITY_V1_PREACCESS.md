# H0004 portability V1 P0

This is a separate `H0004_PORTABILITY_V1` research unit with scope
`INTRA_SECTOR_CROSS_SYMBOL_PORTABILITY`. It asks whether the frozen H0004
SOXX signal occurs on other semiconductor constituents without changed
parameters. Shared semiconductor exposure prevents independent-asset,
general-market or "10 independent replications" claims.

The branch starts exactly at discovery implementation
`9ad3546d6d0d273fa916d63da43d00a6a33131ad`. Main PM source was
`1789f7be7e3bbea298fb8984d2a9d5a072e14000`. Main and the discovery branch
are preserved; implementation is not integrated into main.

Universe and protocol are canonical JSON in `research/decision_records/`.
The complete official BlackRock investment schedule at2026-03-31 supplies
30 historical common-stock/ADR holdings. Values divided by original net
assets supply weights; unrounded values determine rank. Printed page19
is retained in the original PDF capture. The document was retrospectively
published: effective membership is historical, but contemporaneous receipt
or delivery before2026-05-05 is not claimed. Current holdings and the
unverified secondary2026-04-30 table are not used.

Universe: NVDA, AVGO, MU, AMD, AMAT, MRVL, INTC, KLAC, MPWR, TER.
Missing coverage never permits replacement. Unavailable/unresolved symbols
remain in the full10-symbol denominator. An unavailable empty stream has
unknown candidate count, not observed ZERO_SIGNAL.

The frozen signal source contains a SOXX namespace guard. The minimal
adapter maps every symbol identically into that namespace in a detached
OHLCBar. It does not change price, timestamps, feature, episode, rearm or
reference logic. Outer candidate records bind the real symbol, input hash,
causal timestamp, slot, segment and original frozen event. Native event IDs
and snapshots stay inside that binding. Parameters are loaded directly
from the original signal freeze and must match its effective hash.

Capture uses the same Alpaca SIP raw15m clock/representation with raw/split
identity and interval corporate-action evidence. No provider fallback or
adjusted prices enter the signal. Incomplete grids are UNAVAILABLE; unit
or action ambiguity is UNRESOLVED. This conservative V1 requires the same
complete4480-slot causal input grid as original discovery; it does not repair
missing slots. Raw/split equality verifies interval identity and is not a
new split transform. Cash dividends remain separate from outcome accounting.

Frequency A uses completed causal input READY observations, including
reference warmup. Frequency B uses sessions with those observations.
Feature READY observations/sessions are separately disclosed. No-signal
READY symbols are retained and their future return remains null.

Future report schema and all four universe denominators are preregistered,
not executed. Equal-symbol summary and within-symbol session balancing are
primary; event pooling is diagnostic only. Concentration has no selection
or tuning authority. Direction, t+16 prices, returns, efficacy and
profitability are outside this action.

`verify_preaccess` verifies input/stream/protocol/source seals and a clean
Git workstream. `authorize_real_outcomes` always denies in P0, including
after structural READY. Real outcome execution requires a separate action.
The existing DiscoveryPermit/control package is preserved; eventual
control-layer remediation is P2. All original research/code/doc/test files
are checked against the frozen lineage; discovery evidence is hashed without
parsing labels or result reports. SOXX48/29 is verified from frozen causal
candidate records only; no discovery regeneration or confirmation access.

Commands:

```
python -m scripts.h0004_portability_preaccess freeze
python -m scripts.h0004_portability_preaccess capture
python -m scripts.h0004_portability_preaccess generate
python -m scripts.h0004_portability_preaccess verify
```

Freeze precedes capture/signals. Generation requires a clean committed source
tree. Artifacts are write-once; a repeated write must be byte identical.
Only committed sealed streams can pass the final gate. Tests use synthetic
fixtures for arithmetic and a P0 regression plugin denies real H0004 label,
readiness and aggregation access. Unit tests have network disabled.

H0004 discovery remains FROZEN / COMPLETE with its existing disposition;
confirmation remains FROZEN / PENDING / ASYNCHRONOUS at2026-10-19..2027-10-19.
No new H0004 trial or H0005 implementation is introduced. Cross-sector
generalization needs a separate future protocol.

Current execution status is recorded in the new workstream result record;
main PM history is unchanged. Stop after preaccess verification, whether
READY_FOR_PORTABILITY_OUTCOME_ACCESS or BLOCKED_PREACCESS.
