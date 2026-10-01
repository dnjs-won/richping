# Richping Research Philosophy — Epistemic Boundaries and Market-State Layers

Status: research/architecture principle. This document does **not** authorize production trading behavior, alter H0001, select a champion, or establish profitability.

## 1. Core epistemic rule

Richping must distinguish **what is observed** from **what is inferred or explained**.

A rising moving-average structure, HH/HL sequence, positive momentum, or similar price-derived condition does not mean that Richping has "understood the market." It means only that a defined price condition is observable from information available at that time.

Accordingly:

- `PRICE_REGIME` / `TREND_PERMISSION` is preferred for strategy-local price state.
- `MARKET_REGIME` must not be used as a synonym for a price trend unless the contract explicitly defines the broader information set being measured.
- Strategy output must not imply causal knowledge that its inputs cannot support.
- A narrative explanation such as "AI boom is overpowering rates" is research context until represented by point-in-time data and tested.

## 2. Separate state layers

Richping should preserve the following conceptual layers rather than collapse them into one regime flag:

```
MACRO STATE
rates / real rates / yield curve / USD / oil / liquidity / inflation / growth ...
        |
        v
CROSS-ASSET / SECTOR LEADERSHIP
which assets/sectors are demonstrating relative strength now?
        |
        v
ASSET PRICE REGIME
what is the causal price state of the selected asset?
        |
        v
STRATEGY FAMILY
H0001 pullback / H0002 breakout / other independently tested hypotheses
        |
        v
ENTRY / EXIT / RISK
```

These layers may disagree. Disagreement is information and must not be silently resolved by narrative.

Example valid state:

```
macro_state        = HOSTILE_OR_TIGHTENING
sector_leadership  = SEMICONDUCTORS_STRONG
asset_price_regime = BULLISH
```

The architecture should preserve such combinations for conditional evaluation.

## 3. H0001 terminology and boundary

H0001's Daily bullish condition is a **price-derived long permission**, not proof of a favorable macro environment.

Do not change H0001 merely because a current macro narrative appears inconsistent with its Daily price state. If macro information is later introduced, compare explicit alternatives through versioned experiments, for example:

- price-only permission;
- macro risk modifier;
- macro veto;
- interaction model between macro state and price/leadership state.

No alternative is assumed superior before evidence.

## 4. Avoid asset-selection hindsight

A strategy tested on SOXX because semiconductors are known *today* to be a leading 2026 theme risks asset-selection hindsight when interpreted as a general historical strategy.

A historical test that claims to discover leadership must reproduce the selection using only information available at each historical decision time.

Invalid generalization:

```
know in 2026 that semiconductors are strong
-> choose SOXX
-> backtest SOXX historically
-> claim the system could historically identify the winning sector
```

Valid research requires a point-in-time eligible universe and a causal selection rule.

SOXX-specific research may still be performed, but its conclusion must remain SOXX-specific unless broader selection/generalization is separately tested.

## 5. Causal sector / asset leadership discovery

Before requiring complete fundamental coverage, Richping may research price-derived cross-sectional leadership over a predeclared point-in-time universe.

Candidate inputs include, without being adopted as rules:

- relative return over multiple predeclared horizons;
- volatility-adjusted momentum;
- distance from / persistence above causal moving averages;
- breadth and new-high participation;
- relative drawdown / recovery strength;
- cross-sectional rank stability.

The important property is not a particular indicator. It is that the same predeclared algorithm can select different leaders at different historical dates without knowledge of future winners.

Selection, strategy signal, and performance evaluation must remain separate contracts so that selection bias can be measured.

## 6. Fundamentals are a future evidence layer, not assumed knowledge

A stronger explanatory layer may eventually use point-in-time fundamentals such as:

- revenue / earnings / margin growth;
- earnings surprise;
- estimate revisions;
- valuation;
- capex and sector-specific operating metrics.

However, fundamental data are only admissible when their historical availability/known-at semantics are defensible. Current or restated fundamentals must not be projected backward as if known earlier.

Analyst-estimate history and revisions require particular care because present-day snapshots do not reconstruct historical expectations.

Until such data contracts exist, Richping must not claim that it identified *why* a sector is strong.

## 7. Macro: state, shock, and interaction

Macro research should distinguish at least:

- **level/state**: e.g. yield level;
- **change/shock**: e.g. rate move over a defined causal horizon;
- **market response**: how the asset/sector behaves while that macro condition occurs.

A hostile macro variable does not automatically imply a short signal. A strong price response despite an adverse macro state may itself become an interaction feature candidate.

Examples to test rather than assume:

```
macro adverse + leadership weak   -> ?
macro adverse + leadership strong -> ?
macro benign  + leadership strong -> ?
macro benign  + leadership weak   -> ?
```

Any thresholds, horizons, state definitions, and actions remain unresolved until specified and tested.

## 8. Research objective

Richping's objective is not to claim complete market understanding.

The operational objective is:

> Discover reproducible, causally observable market states and strategy opportunities; measure their conditional after-cost outcomes; preserve uncertainty and conflicts; and expand the information set only when point-in-time data and independent evidence justify it.

The system should progressively expand from price-pattern research toward cross-sectional leadership, macro interactions, and fundamentals without retroactively upgrading old evidence.

## 9. Evidence and promotion requirements

For every new state layer or feature family:

1. define point-in-time / `known_at` semantics;
2. define eligible universe and survivorship treatment;
3. separate discovery data from confirmatory data;
4. predeclare the tested variants / multiple-testing family;
5. measure incremental value relative to the simpler price-only baseline;
6. include costs and turnover where the feature changes trading;
7. preserve null, contradictory, and unavailable states rather than forcing a classification;
8. reject or leave inconclusive features that do not add robust evidence.

Complexity is not evidence. A macro/fundamental model must demonstrate incremental value rather than being added because its narrative is plausible.

## 10. Current limitation statement

As of this document, Richping should be described conservatively as a developing causal **price/strategy research system** with reusable replay/feature infrastructure, not as a complete market-understanding engine.

Future cross-sectional, macro, options, and fundamental layers are research directions. Their existence in architecture or documentation does not establish alpha.
