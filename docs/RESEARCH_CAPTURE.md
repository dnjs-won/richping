# Research Capture Contract v1

## Purpose

Chat/mobile discussions are a research input, not evidence and not production configuration.
This contract preserves an idea with enough structure to reproduce what was meant, while keeping it isolated from Richping's immutable recommendation, outcome, evaluation, risk, paper, and promotion contracts.

Flow:

```text
Chat / observation
  -> DRAFT hypothesis
  -> SPECIFIED hypothesis
  -> experiment design
  -> existing isolated research/validation machinery
  -> REJECTED | INCONCLUSIVE | CANDIDATE
  -> fresh evidence / promotion gate (future contract)
```

No state in this document authorizes production recommendations or changes the champion.

## Source of truth

- Discussion remains useful context, but the repository record is the durable source of truth.
- One hypothesis has one stable `hypothesis_id`.
- Material changes create a new `revision`; do not silently rewrite what was tested.
- Raw screenshots/chat transcripts are optional references. The normalized hypothesis must stand alone.
- Do not copy remembered details into a hypothesis as facts. Mark missing items `unknown`.

## Storage

```text
research/
  hypotheses/   # normalized hypothesis YAML files, e.g. H0001-r01.yaml
  templates/    # capture templates only
```

Execution artifacts stay in the existing research paths/DBs. Do not put backtest outputs, mutable caches, market datasets, or paper ledgers here.

## Hypothesis states

- `DRAFT`: captured but ambiguous; not executable.
- `SPECIFIED`: falsifiable rules and required data are defined; experiment may be designed.
- `TESTING`: an experiment ID/spec is linked. This state does not imply success.
- `REJECTED`: tested evidence failed the predeclared criterion or invalidated the thesis.
- `INCONCLUSIVE`: evidence/data/sample quality is insufficient.
- `CANDIDATE`: passed the hypothesis-level research criterion only. Not production-approved.
- `ARCHIVED`: superseded or intentionally retired.

Only evidence from Richping's versioned experiment/evaluation path may move a hypothesis beyond `SPECIFIED`. Chat judgment alone cannot set `TESTING`, `REJECTED`, `INCONCLUSIVE`, or `CANDIDATE`.

## Required fields

Use `research/templates/hypothesis.yaml`.

Identity/provenance:
- `schema_version`, `hypothesis_id`, `revision`, `status`
- `created_at`, `updated_at`
- `source.type`, `source.discussion_date`, optional URL/issue/reference
- `supersedes` for a material revision

Research meaning:
- `title`, `thesis`
- `observations[]`: what was seen; not proof
- `rules`: regime, setup, trigger, exit, invalidation
- `timeframes`
- `required_data[]`
- `unknowns[]`

Testability:
- `null_hypothesis`
- `primary_metric`
- `decision_rule`
- `cost_assumption`
- `sample_unit`
- `leakage_risks[]`
- `multiple_testing_family`
- `experiment_refs[]`
- `evidence_refs[]`

## Revision rules

Cosmetic clarification may update the same revision before testing starts.
After an experiment is registered, changing entry/exit/regime/threshold/timeframe/metric/decision rule/cost assumption creates a new revision and sets `supersedes` to the prior file. Prior revisions remain immutable.

A failed revision must not be deleted. This prevents repeated rediscovery from erasing the trial count.

## Boundary with existing Richping contracts

This layer is intentionally upstream of existing `experiments`.

- It does not alter dataset, bars, members, model_versions, runs, recommendations, outcomes, experiments, risk_state, or paper ledgers.
- It does not alter M2-1B feature normalization, v3 outcome, `cash_action_review_v1`, risk cohort, or existing promotion logic.
- A `CANDIDATE` hypothesis is still research. Existing/future promotion requirements remain authoritative.
- Existing research OOS cannot become fresh evidence merely because a hypothesis file is created later.
- Discovery data and confirmatory evidence must be identified separately.

## Mobile / Chat operating procedure

At the end of a useful discussion, request: "Save this as a Richping research hypothesis using RESEARCH_CAPTURE.md."

The capture should:
1. summarize only claims actually discussed;
2. preserve uncertainty explicitly;
3. assign the next available hypothesis ID only after checking existing files;
4. start at `DRAFT` unless every required test field is explicit;
5. create a new revision instead of overwriting a tested one;
6. avoid running tests or changing production behavior unless separately requested.

GitHub Issues may be used as an inbox. Issue content is not the canonical hypothesis until normalized into `research/hypotheses/`.
