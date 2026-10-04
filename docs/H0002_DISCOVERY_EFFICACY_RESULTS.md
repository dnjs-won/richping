# H0002 discovery efficacy: exploratory only

The frozen SOXX15m70-session discovery cohort was first evaluated without changing
signal, baseline or horizons. Canonical evidence is
`research/data_evidence/h0002-first-efficacy-20261004/verification-v2/discovery-report.json`.
All original fourteen primary events and eleven nested comparator events remain.

| Family / scheduled horizon | Complete labels | Session-balanced mean raw direction | Event median | Positive events | Complete matched pairs | Session-balanced excess, resolved subset only |
|---|---:|---:|---:|---:|---:|---:|
| Price /4 |14/14|+0.071984%|+0.043293%|8/14 (57.14%)|12/14|+0.611223%|
| Price /64 |14/14|+0.309723%|-0.613150%|5/14 (35.71%)|12/14|-0.322553%|
| Price /192 |14/14|+1.286293%|-0.802459%|5/14 (35.71%)|12/14|+1.039449%|
| Volume /4 |11/11|+0.126729%|+0.035798%|6/11 (54.55%)|9/11|+0.757886%|
| Volume /64 |11/11|+0.319659%|-0.912815%|4/11 (36.36%)|9/11|-0.369640%|
| Volume /192 |11/11|+0.988259%|-0.940856%|4/11 (36.36%)|9/11|+0.993842%|

Price labels span12 sessions; matched complete price pairs span10. Volume labels
span10 sessions; complete pairs span8. May7 has zero eligible controls and May12
has two; five are required. Those events stay UNRESOLVED for paired evaluation
at every horizon and remain in the individual label stream. Full-cohort excess
is null for both families; the displayed subset excess cannot stand in for it.
There are no pending or unresolved price-direction labels on this admitted cohort.

Descriptive disposition is DISCOVERY_INSUFFICIENT_RESOLVED_LABELS because the
complete matched cohort is unavailable, despite complete absolute labels.
DISCOVERY_UNCERTAINTY_NOT_PREREGISTERED means no discovery CI or bootstrap was
executed: the fixed252-session algorithm was not adapted to70 sessions. Secondary
horizon means are positive while their medians are negative; this is mixed
descriptive evidence, not a persistence or timing-effect confirmation. Volume
results are nested descriptions, with no superiority comparison or promotion.

Each run makes222 scoped discovery label requests/forward close reads:42 event
labels plus180 matched-control labels, including permitted reused anchors. The
volume comparator reuses the already-resolved parent labels. Confirmation outcome
access and profitability calculations are zero. Duplicate requests and overlapping
windows are not claimed to be independent observations.

The initial adapter attempt falsely treated historical bar-time UNKNOWN action
knowledge as unresolved ex-post interval units. It emitted only null labels and
read zero forward closes. Its complete evidence/source is retained separately;
the corrected adapter requires the hash-verified interval-specific no-split/raw
unit certificate, preserves all raw prices/UNKNOWN flags, and uses exactly the
same control membership hash. The corrected result supersedes that implementation
defect; no frozen contract, count or membership was relaxed.

These are gross price-direction opportunity marks, not fills, account returns,
dividend reinvestment, after-cost profit or proven Alpha. Neither PASS nor REJECT
confirmation disposition was emitted. H0002 remains frozen and awaits its separate
252-session future confirmation asynchronously, terminal deadline2027-10-23 20ET.
H0001's source/evidence/126-session track remain unchanged. The next active project
P0 is independent H0003 hypothesis generation/selection; future waits do not block it.
