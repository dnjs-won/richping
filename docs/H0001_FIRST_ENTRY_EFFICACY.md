# H0001 fixed-stream initial-entry disposition

Latest main at `a04cf35` assigns `H0001_FIRST_ENTRY_EFFICACY`, following
composition `bb72239` and efficacy preregistration `13f719b`. The task branch
`v2-h0001-first-entry-efficacy` starts from that latest implementation.

The frozen protocol hash is
`074255189630fa625c4d40eb2f344fb7767d2c8f305f22c9e4c2a608e93e944c`.
The existing immutable SOXX candidate stream contains zero events. Its executed
disposition is **ZERO_SIGNAL**, with every numeric metric and interval null.
This neither rejects the strategy nor demonstrates an economic effect.

## Admission and execution

The evaluation manifest was sealed before disposition at evaluation as_of
`2026-10-03T12:02:15+00:00`. It pins the committed protocol, executable spec,
composer, candidate stream, fixed input IDs/hashes, implementation basis and
runner/helper source hashes. The existing protocol verifier checks all 23
frozen dependencies. Mutation or identity mismatch aborts before result emission.

The narrow runner reads only those contracts, sources and saved signal metadata.
Network, SQLite and market loaders are denied. A read-allowlist test additionally
proves that disposition opens only those metadata/source files. It does not reload
market data, construct controls, query actions/outcomes or calculate returns.
The proof records two byte-identical deterministic dispositions and zero access
attempts. Existing committed composition evidence supplies the real-data basis;
this task does not claim a new market replay.

Run:

```powershell
.venv\Scripts\python -m scripts.h0001_first_entry_efficacy
```

The one-time `--register-as-of` option seals a manifest; attempting to replace it
with a different manifest fails. Reports use the existing immutable JSON writer.
Same input produces the same report ID/hash. A changed artifact at an existing
path is a collision and is never overwritten.

This runner implements only the current fixed empty-stream branch of the protocol.
A nonempty stream fails closed until an exact frozen label/control/bootstrap
adapter is separately implemented and admitted. No full label engine is claimed.

## Denominators and scope

All 2,624 atomic-batch signal denominators are preserved unchanged. Daily READY
2,624; BULLISH 721; exhaustion READY/NORMAL 2,624; H1 raw READY 829; ACTIVE 0;
15m primitive READY 2,304; eligible armed/trigger 0; GC 92 with price confirmation
80 pass/12 fail; explicit FLAT 2,624; consumed-episode suppressions 0;
candidate count 0; unavailable 1,795; ineligible 829.

The independent completed-H1 diagnostic has 656 publications, 208 READY and
zero downside extremes. Its counting unit differs from atomic-batch occupancy.
Primitive 15m extremes are already recorded in the earlier mechanical proof;
no new primitive diagnosis or rule selection occurs here.

Each frozen horizon reports total/complete/pending/unresolved labels as zero,
with reason NO_CANDIDATE_EVENTS. Eligible control count is null, with status
NOT_EVALUATED_NO_CANDIDATES; it is not asserted to be zero. The future fixed
126-session confirmation window is NOT_STARTED_NOT_EVALUATED. Current discovery
ZERO_SIGNAL is not a disposition of that future cohort.

Signal spec stays `h0001_r03_spec_v13`, hash
`bf8134733bacee17542240e53a8ec30223c1550b5bedbaa6d3994ba1444acc19`,
with 84 unresolved paths. Daily/1H/15m/composer decisions, candidate-only FLAT,
episode consumption and global lifecycle scope remain unchanged.
Profitability is NOT_RUN; outcome lookup is NONE.

## PM consequence

The fixed-stream disposition action completes. Phase exit 5 remains complete for
the valid deterministic empty event stream. Phase exit 6 remains incomplete
because informative efficacy cannot be inferred from an empty cohort.

Promote `LONG_HISTORY_PROVIDER_AND_VOLUME_EVIDENCE` from P1 blocker candidate
to P0 for exit 6. The next action audits actual provider access, extended-session
coverage, volume semantics and action/OHLC unit admission for a longer immutable
discovery cohort. No provider migration is performed in this action. More history
does not guarantee candidates or inference. Historical expansion remains discovery;
the fixed future confirmation boundary, evidence floors and stopping rule stay
frozen. Existing interval action/unit certification must not carry forward.
