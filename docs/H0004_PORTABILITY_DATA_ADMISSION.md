# H0004_PORTABILITY_V1 data admission remediation

This is an outcome-blind admission revision on top of immutable preaccess commit
`f3090a23123279cf0f9a506a526224cce7909e61`. It changes neither strategy nor universe.
H0004 discovery and asynchronous confirmation remain separate frozen research.
No outcome permit is issued by this action; its runner always denies outcome authorization.

The remediation policy is canonically serialized and frozen before the one permitted
same-provider retry. The original capture implementation is reused verbatim with only
its destination and the preregistered non-READY subset adapted. Alpaca SIP, raw USD/share,
15-minute extended-session grid, interval, pagination, publication clocks and action
compatibility are unchanged. Split-adjusted rows are diagnostics only.

Every missing slot is listed in `before/<symbol>/audit.json`, including completed clock,
session, slot index, segment and contiguous run. Original HTTP pages are reconstructed
and compared exactly to parsed captures. A missing provider bar does not establish a
halt, zero trading, or absence of eligible trades. These endpoints supply neither halt
history nor historical action announcement clocks. Those causes are explicitly unknown.
Calendar slots remain valid and are never deleted to improve coverage.

KLAC has a provider-reported 10:1 split effective on 2026-06-12, with record date
2026-06-04. Raw/split rows differ before that effective date. The provider action
capture supplies ex/payment/process/record dates but no historical `known_at`.
The current receipt clock is not an announcement clock. The existing generic
no-share-unit-action contract cannot admit this boundary without a new interpretation;
no symbol exception or normalization is introduced. Cash dividends are disclosed;
their feature treatment and outcome accounting are not changed or evaluated.

Only exact newly returned observations may be admitted. Loss or revision of a
previously present raw/split bar, changed action metadata, or an incomplete retry
fails closed as UNRESOLVED and leaves predecessor inputs in place. Missing provider
observations remain UNAVAILABLE. Unchanged inputs reuse the old candidate stream
and its hash; all ten symbols stay in the universe denominator. Non-admitted symbols
have null candidate counts, never fabricated zero returns or ZERO_SIGNAL classifications.

The revision 2 admission manifest binds policy, predecessor aggregate, original
universe/config/protocol, committed sources, captures/raw pages, exact audits and all
candidate streams. A separate aggregate seal rejects mutation. Repeated offline
builds and independent processes must produce identical canonical hashes.

Final state: `PORTABILITY_DATA_ADMISSION_FINALIZED` after successful verification.
Next action: `H0004_PORTABILITY_V1_OUTCOME_EVALUATION`, requiring a separate owner action.
No outcome phase is started here. Main research integration and control architecture
remediation remain outside this workstream.

Provider documentation supporting the limited interpretation of missing bars:
[Alpaca market-data FAQ](https://docs.alpaca.markets/us/docs/market-data-faq) and
[corporate actions API](https://docs.alpaca.markets/us/v1.1/reference/corporateactions-1).
