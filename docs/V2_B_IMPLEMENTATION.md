# V2-B reusable feature services

Basis: audited V2-A `df2e34b42b954ad73cc89c039318059d058214e9`,
`atomic_known_at_batch_v1`. Implementation branch: `v2-b-reusable-features`.

## Investigation and implementation boundary

The initial root checkout was `main` at
`94cc2d292a83714aadaa4033ddfd5a5cfca39125`, with pre-existing modifications
to cli/maturity/paper/pipeline and untracked `tests/test_r1b_q_regressions.py`.
Those files remain in that checkout. The clean V2-A worktree matched the exact
audited commit. A separate `var/worktrees/v2-b` worktree starts at that commit.

Before implementation, the architecture, V2-A implementation, H0001-r03,
research capture contract, project status and V2-A contracts/data/aggregation/
clock/replay/store/tests were reviewed. There was no existing EMA/MACD contract.
Legacy `engine.features` computes the arithmetic mean of the last 14 TR values;
it is not the Wilder ATR implemented here and has not been changed.

Plan followed: immutable contracts, EMA/MACD with hand and 100-bar prefix
fixtures first, volatility and relative transforms, confirmed structure,
provenance/storage/regression verification, then documentation.

## Architecture and API

```text
V2-A atomic batch -> immutable ReplayContext (completed bars only)
                          |
          +---------------+-------------------+
          |               |                   |
       EMA/MACD         TR/ATR          confirmed swings
          |                                   |
     ScalarSeries                   same-kind classification
          |
  rolling percentile/z-score

immutable FeatureResult + positive scale FeatureResult -> normalization
```

`features/` imports only standard-library code, the existing core helpers,
V2-A value contracts and sibling feature modules. No dataset, store, loader,
aggregator, replay engine or strategy is accessible through feature inputs.
There is no registry, cache, mutable service state or new dependency. No V2-A
execution module or legacy source was edited. Existing trace/state serialization
can record `payload(result)` without a schema change or a separate writer.

Public functions and frozen specs are exported by `features/__init__.py`:

```python
raw = macd(context, "ALFA", "15m", MACDSpec(12, 26, 9, min_history=35))
series = macd_series(context, "ALFA", "15m",
                     MACDSpec(12, 26, 9, min_history=35), field="macd_line")
rank = rolling_percentile(series, PercentileSpec(window=100, min_history=50))
scale = atr(context, "ALFA", "15m", ATRSpec(period=14, min_history=14))
ratio = normalize(raw, scale, NormalizeSpec("macd_line", "atr"))
swings = confirmed_swings(context, "ALFA", "15m", FractalSpec(left=2, right=2))
geometry = classify_swings(swings)
```

These numbers demonstrate an API; they are not H0001 parameters or thresholds.
`close_series` and explicit immutable `ScalarSeries` support arbitrary causal
scalar sources, including negative values. `macd_series` is a convenience
projection, not a MACD-specific relative transform.

## Common contract and provenance

Every FeatureResult records its FeatureSpec (name, version, canonical immutable
parameters), symbol, timeframe, as_of, immutable values, status/reason,
input_end_at, input_count and input_hash. `specification_hash` hashes the full
definition; `hash` hashes the full result. Spec dataclass defaults for the one
supported convention are explicitly serialized, not omitted hidden settings.
Span/window/min_history and all supported method choices are explicit.

- EMA/MACD/ATR and swings count all selected visible bars in market-end order.
- TR counts the last one or two bars actually used.
- Rolling transforms count the last N observation slots, including unavailable
  slots. Input provenance includes these points and the supplied causal source
  input hash. The source may depend on earlier history (e.g. EMA).
- Normalization counts two operand snapshots (zero with no underlying bars),
  not the sum of overlapping bar histories. Its input hash always covers both.
- Classification retains the detector's bar input count/end and hashes its
  complete detector result as input provenance.

Transform/normalization/classification specifications recursively embed their
upstream feature definitions. The full dataset content hash, capture timestamp,
and future-dependent run ID are never feature inputs. Causal input bar vintage
labels/provenance remain included. Prefix equality fixtures use the same explicit
vintage label; different labels intentionally produce different provenance.

The unmodified `replay.code_provenance` recursively hashes all v2 Python files
and reused core. A test changes each feature file's read content in memory and
verifies engine_hash changes. Real files are not altered by that test. A fixture
also persists feature snapshots through the isolated ResearchStore and checks
rerun equality/idempotency and different run IDs for changed feature specs.
Callers must include feature definitions in their strategy specification when
using them; these fixture contracts do not freeze H0001's future specification.

## Exact math and readiness

All calculations use Python binary floating point. Bars are ordered by end_at
within the selected symbol/timeframe; EMA/ATR use all currently visible history,
without resetting at session boundaries. Missing observations are not filled.
Internal missing expected slots now fail closed under the contract below,
superseding the delivered-observation behavior of audited commit `97d847e`.
A delayed earlier bar can change a *new* as-of calculation; old returned
contexts/results never change. Readiness requires arithmetic readiness and
continuity of the calculation history, not convergence or statistical sufficiency.
No provider parity is claimed.

### Generic continuity: `xnys_completed_grid_v1`

`features/continuity.py` supplies the common slot/contiguous-prefix checks for
bars, scalar windows and causal structure. It uses the existing XNYS calendar:
15m and 1H slots are anchored to official session open, with the final short
1H bucket ending at official close; Daily is official open through close.
Adjacency crosses directly from official close to the next trading session's
first slot. Overnight, weekends, holidays, DST and early closes consume no
extra observation step. An omitted trading session or intraday slot is a gap.
Malformed bar boundaries are invalid inputs (ValueError), not missing prices.

An internal gap yields **NOT_READY / noncontiguous_history**, with empty values.
This is recoverable missing input, consistent with insufficient-history
readiness; UNDEFINED remains for arithmetic failures such as zero variance.
The gap reason takes precedence over insufficient_history when both apply.
Only the interval from the first to last selected input is checked: no history
before the first visible bar or after the last visible bar is demanded. This
is a continuity contract, not a freshness or full-dataset coverage certificate.

- EMA, MACD and ATR require the whole visible calculation history contiguous.
  They do not restart at the gap or silently discard the earlier recurrence.
- TR requires only its last two selected bars contiguous; with one visible bar
  its existing high-minus-low seed applies. An older gap outside those two bars
  does not invalidate current TR, while it still invalidates recursive ATR.
- MACD scalar projection calculates only the contiguous prefix. Every visible
  point from the first gap onward is null / NOT_READY / noncontiguous_history,
  even when a downstream rolling window starts after that gap. All three
  MACD fields follow this rule; distorted MACD cannot enter a relative sample.
- Raw close and explicit external ScalarSeries remain sparse, timestamped
  observations. An individual raw close can be READY independently of its
  neighbors. `ScalarSeries.contiguous` explicitly reports full-series continuity.
  Percentile/z-score independently check the selected window's expected grid,
  including caller-built series whose supplied points all claim READY. A window
  spanning an absent slot returns NOT_READY / noncontiguous_history rather than
  compressing time or searching for replacement observations. A later raw window
  wholly outside the gap can become READY; recursive unavailable source points
  still propagate NOT_READY / unavailable_input (or UNDEFINED for undefined
  sources), as before. No artificial numeric slots are inserted.
- Swings use the same helper on each confirmation window, preserving their
  existing window-specific readiness and immutable confirmation semantics.

Once a delayed bar becomes visible and restores continuity, a new as-of result
may be READY. Recomputed MACD scalar known_at remains the maximum arrival time
of its full prefix. Previously returned results, scalar points and contexts
remain immutable; no historical snapshot is rewritten.

EMA/MACD/TR/ATR/percentile/z-score specs explicitly serialize the continuity
version; raw-close source specs also declare sparse-grid policy. These added
parameters change specification hashes (including nested source definitions),
and the recursive engine code hash changes. Existing arithmetic version names
and formulas are retained; old stored evidence is not reinterpreted or migrated.

### EMA: `ema_first_observation_recursive_v1`

`alpha = 2/(span+1)`, `E[0] = close[0]`,
`E[t] = alpha*close[t] + (1-alpha)*E[t-1]`.
Only `seed=first_observation`, `field=close` are supported. `min_history` is a
required independent output gate; it may be smaller or larger than span. Before
that count, the whole result is NOT_READY/insufficient_history with no values.
The recurrence still starts at the first observation, not at the gate. No SMA
EMA seed, full-sample seed, hidden burn-in or chart emulation is implemented.

### MACD: `macd_first_observation_recursive_v1`

Require positive fast/slow/signal and fast < slow. Both price EMAs use the EMA
recurrence above. `macd_line = E_fast - E_slow`. The signal uses the same
first-observation recurrence with alpha=2/(signal+1), beginning at the first
MACD observation (mathematically zero, not a missing-value placeholder).
`histogram = macd_line - signal_line`. All three are withheld until the required
min_history count. Signal initialization does not wait for that output gate.
`(12,26,9)` is accepted as parameters, not embedded as an engine rule.

The scalar projection retains one slot per completed bar, including warmup
slots with value null. Each point's known_at is the maximum known_at of its
entire EMA prefix. A recomputed historical point after a late arrival therefore
cannot be misrepresented as available at its market end time.

### TR: `true_range_first_high_low_v1`

First observation: `TR[0]=high[0]-low[0]` (no unknown previous close).
Subsequent observations:
`TR[t]=max(high-low, abs(high-previous_close), abs(low-previous_close))`.
Require one bar; use the previous contiguous completed bar's close thereafter.

### ATR: `atr_wilder_sma_seed_first_high_low_v1`

Period p; first p TR values use the preceding TR contract.
`ATR[p-1] = sum(TR[0:p])/p`; thereafter
`ATR[t] = ((p-1)*ATR[t-1] + TR[t])/p`.
The implementation evaluates this as a weighted sum to reduce overflow risk.
`min_history >= p` is required, and controls output release. Zero ATR is a valid
READY volatility value; it is an invalid normalization denominator.

### Percentile: `rolling_empirical_midrank_v1`

Use the last `min(window, available_count)` observation slots **including current**.
Do not search farther back to replace an unavailable slot. Require min_history
(1 <= min_history <= window) and every included value READY.
For current x among n included values:
`rank = (count(value < x) + 0.5*count(value == x))/n`.
Ties use exact scalar equality. The reported scale is [0,1]; with a finite
current-inclusive sample, attainable values are within [0.5/n, 1-0.5/n].
An all-tied window returns 0.5. There is no full-dataset percentile.

### Z-score: `rolling_zscore_ddof_v1`

Same current-inclusive window/slot/missing policy. ddof must explicitly be
0 (population) or 1 (sample), with min_history > ddof.
`mean=sum(x)/n`; `variance=sum((x-mean)^2)/(n-ddof)`;
`z=(current-mean)/sqrt(variance)`. Exact zero variance produces
UNDEFINED/zero_variance and no value. Overflow/nonfinite arithmetic produces
UNDEFINED/nonfinite_result; no arbitrary zero, clipping or epsilon is used.

### Normalization: `positive_causal_scale_v1`

Explicit numerator/denominator field names select scalar values. Require identical
symbol, timeframe, as_of and input end time; misalignment raises ValueError.
For READY operands and d>0, return n/d. A zero/negative scale yields
UNDEFINED/nonpositive_scale; a nonfinite quotient yields
UNDEFINED/nonfinite_result. Upstream UNDEFINED propagates UNDEFINED;
otherwise unavailable inputs produce NOT_READY, with reason unavailable_input.
Unknown/non-scalar fields raise ValueError. Cross-timeframe alignment or stale
scale carry-forward would need a separate explicit contract.

Statuses READY/NOT_READY/UNDEFINED belong to features, not trade/data outcomes.
Invalid specs/identities or future input raise ValueError. Unavailable results
contain `{}` rather than real-looking zeroes. Rolling windows preserve missing
slots and distinguish UNDEFINED from warmup. Scalar points use null plus an
explicit status/reason. Normal zero indicator values remain valid numeric values.

## Confirmed price structure

`SwingDetector` is a structural callable protocol. The stateless reference
`confirmed_swings(..., FractalSpec(left=L,right=R))` implements
`fractal_k_right_strict_v1`; both widths must be positive.

For each candidate, require L completed left neighbors and R completed right
neighbors on the contiguous XNYS grid. Same-session neighbors must have matching
end/start; session transitions must be to the next trading session, from official
close to official open. This works with V2-A's 15m, open-anchored 1H (including
the final short bucket), and Daily completed views. Missing grid slots prevent
confirmation; a later insertion cannot replace an already confirmed neighbor.

- High: candidate.high is strictly greater than every neighbor.high.
- Low: candidate.low is strictly less than every neighbor.low.
- Any equal neighboring extreme rejects that pivot; plateaus have no pivot.
- A wide outside candle can independently confirm both kinds.
- `pivot_at` is the candidate's market end time.
- `confirmed_at` is max(known_at) across the entire window, including left and
  right bars. Ordinarily it is the Rth right bar's completion; late arrivals
  postpone it. It is strictly after pivot_at and never after context.as_of.
- Events carry kind SWING_HIGH_CONFIRMED/SWING_LOW_CONFIRMED, pivot price,
  confirmation version and detector specification hash.

Results contain the cumulative confirmed events visible at this as_of, sorted
by (confirmed_at,pivot_at,kind), not just newly emitted events. Consumers can use
the recorded confirmation times or compare immutable prior snapshots. No event
is exposed at its pivot time before confirmation. Enough bars but no contiguous
window gives NOT_READY/insufficient_contiguous_history; an examined window with
no pivot gives READY with an empty events list.

Separate classifier `confirmed_same_kind_comparison_v1` compares each event
against the immediately previous *confirmed* event of the same kind in that
order. Higher/lower highs are HH/LH; higher/lower lows are HL/LL. Equal confirmed
prices give EQH/EQL; the first of each kind has null classification. A delayed
older pivot enters confirmation order at its actual availability, never by
inserting a fictitious past confirmation. Labels have no HOLD/EXIT meaning.

## Validation

Commands use `C:/richping/.venv/Scripts/python -m pytest` from the isolated
worktree, reusing the existing environment rather than copying its packages.

Continuity audit remediation on `97d847ef2ecfb97199f6ca8637d4c0bb8076ef82`:

- Full V2: **130 passed (20.08s)**, including all 47 V2-A tests and 33 new
  calendar continuity regressions.
- Full pytest: **384 passed (91.74s)**; no failures, skips or pytest warnings.
- `git diff --check`: passed.
- Regressions cover missing/delayed internal 15m, 1H and Daily inputs, restored
  readiness, immutable prior result/series payloads, delayed scalar known_at,
  unavailable MACD line/signal/histogram propagation, raw/external scalar windows,
  first-visible history, TR's two-bar scope, overnight/weekend/holiday/DST,
  early-close short buckets and missing slots on both sides of a session boundary.
- Existing prefix-invariance, atomic-known-at and swing tests remain passing.
  The original delayed-leading-bar test is retained: that absent bar is before
  the first visible observation, so it is correctly not an internal gap.

Initial V2-B implementation results (historical, before continuity remediation):

- V2-B: 50 passed (5.00s).
- V2-A plus V2-B: 97 passed (5.52s), including unchanged 47 V2-A tests.
- Full regression: 351 passed (77.60s), no failures/skips/warnings.
- `git diff --check`: passed. Results are also recorded in PROJECT_STATUS.md.

Hand fixtures include EMA [2,4,8,6] -> [2,3,5.5,5.75]; MACD(1,3,3) on [2,4,8]
-> line [0,1,2.5], signal [0,.5,1.5], histogram [0,.5,1]; TR [2,3,4,5] ->
Wilder ATR(3) [3,11/3]; tied percentile .5; sample z=1; population z=sqrt(3/2);
MACD/ATR=1.25; confirmed high and low sequences yielding HH/LH/HL/LL and equality.
No third-party indicator output is used as the oracle.

Two full 100-bar datasets share bars 1..50; all later OHLC in one are extreme.
Every result through bar 50 is equal for EMA, MACD, ATR, MACD percentile/z-score,
swings and classification. Already confirmed events also survive the altered
future. Other fixtures cover incomplete 1H/Daily, delayed bars/known-at stamps,
missing confirmation neighbors, input tie permutations, ticker relabeling,
atomic first visibility, immutable values and source/spec/code provenance.
Unmodified V2-A tests retain hidden-future, atomic batch, isolated store and
bytewise legacy/paper DB preservation checks.

## Limits, non-goals and V2-C prerequisites

- H0001-r03 remains byte-for-byte unchanged and DRAFT. No executable strategy,
  regime, thresholds, crosses-as-actions, scaling, re-entry, exit/watch, stop,
  sizing, simulator, ledger, provider, historical backtest, optimization or
  walk-forward performance test was implemented. Production/paper code is
  unchanged. Profitability has not been measured; synthetic math fixtures are
  neither alpha nor fresh/OOS/paper/live evidence.
- This is a trusted Python API boundary, not an OS sandbox. Explicit externally
  constructed scalar series must truthfully declare source and availability;
  the API validates timestamps/values and transforms check the selected grid,
  but it cannot certify arbitrary caller math or undeclared upstream dependencies.
- Full visible histories are recomputed without caching; cumulative swing output
  and provenance serialization target small fixtures. No throughput claim.
- Missing bars are not repaired. Numeric features and scalar transforms fail
  closed on internal gaps in their calculation history; structure requires
  contiguous confirmation windows. Feature READY does not override V2-A coverage
  diagnostics, certify trailing freshness, or certify real-data quality.
- Only synthetic corporate-action-free V2-A data is supported. Provider/dataset
  ingestion, dividend normalization and outcome accounting remain later scope.
- Only first-observation EMA and SMA-seeded Wilder ATR are implemented. **Before
  V2-C, confirm H0001's EMA seed, history origin, warmup and relative conventions.**
- **Before V2-C, verify the observed chart/provider's 1H candle boundaries against
  unchanged `xnys_open_anchored_short_final_v1`: 09:30–10:30, 10:30–11:30, ...,
  15:30–16:00.** No claim of matching that chart's MACD is justified yet.
- **Before V2-C, choose H0001's actual swing detector/spec.** This reference
  fractal is not a confirmed H0001 algorithm. ATR/directional-change detectors
  remain unimplemented. Freeze the remaining DRAFT execution-critical unknowns
  before writing a strategy plugin or testing profitability.
- Existing legacy daily availability assumptions, Store same-ID behavior,
  top-level legacy code hash, and V2-A automatic checkpoint restart limitations
  were observed/preserved; no unrelated repair is bundled here.
