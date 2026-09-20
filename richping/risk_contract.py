"""Stable risk-cohort identity, separate from package/build identity."""

import json
from pathlib import Path

from .core import CASH_ACTION_REVIEW_POLICY, DEFAULT_OUTCOME_VERSION, canonical, digest
from .feature_window import FEATURE_VERSION


RISK_COHORT_SCHEMA = "richping_risk_cohort_v1"

# Only modules that can change recommendations, eligible outcomes, or risk
# decisions belong here.  Reporting/CLI/store edits keep the cohort stable;
# an unclassified investment-code edit starts a new cohort conservatively.
INVESTMENT_CODE_MODULES = (
    "core.py",
    "data.py",
    "engine.py",
    "evaluation.py",
    "feature_window.py",
    "pipeline.py",
    "risk_contract.py",
)


def investment_code_hash():
    root = Path(__file__).parent
    return digest({name: (root / name).read_text(encoding="utf-8")
                   for name in INVESTMENT_CODE_MODULES})


def risk_cohort_contract(config):
    """Complete contract required before risk evidence may cross model IDs."""
    return {
        "schema": RISK_COHORT_SCHEMA,
        "strategy": "baseline-v1",
        "config": json.loads(canonical(config.payload())),
        "investment_code_hash": investment_code_hash(),
        "signal_contract": "baseline_trend_relative_strength_v1",
        "score_contract": "baseline_weighted_rank_v1",
        "selection_contract": "baseline_threshold_top_k_v1",
        "feature_contract": FEATURE_VERSION,
        "calibration_contract": "historical_block_bootstrap_edge_v1",
        "outcome_contract": DEFAULT_OUTCOME_VERSION,
        "evaluation_contract": CASH_ACTION_REVIEW_POLICY,
        "risk_contract": {
            "version": "eligible_recent_30_v1",
            "warmup_samples": 30,
            "reduce_expectancy_below": 0.0,
            "pause_expectancy_lte": -0.02,
            "pause_cohort_drawdown_lte": -0.15,
        },
    }


def risk_cohort_id(config):
    return digest(risk_cohort_contract(config))


def verified_risk_cohort_models(store, config, mode="shadow"):
    """Return models with an exact, self-consistent recorded cohort contract."""
    contract = risk_cohort_contract(config)
    cohort_id = digest(contract)
    models = {config.model_id}
    claims = {}
    rows = store.db.execute(
        "SELECT model_id,body FROM runs WHERE mode=? AND status='SUCCEEDED' AND body IS NOT NULL ORDER BY rowid",
        (mode,),
    ).fetchall()
    for row in rows:
        valid = False
        try:
            body = json.loads(row["body"])
            recorded = body.get("risk_cohort_contract")
            valid = (
                body.get("risk_cohort_id") == cohort_id
                and isinstance(recorded, dict)
                and digest(recorded) == cohort_id
                and canonical(recorded) == canonical(contract)
                and body.get("outcome_contract") == contract["outcome_contract"]
                and body.get("evaluation_policy") == contract["evaluation_contract"]
            )
        except (TypeError, ValueError, KeyError):
            valid = False
        claims.setdefault(row["model_id"], []).append(valid)
    for model_id, verified in claims.items():
        if all(verified):
            models.add(model_id)
    return cohort_id, contract, sorted(models)


def conservative_legacy_pause_models(store, config, cohort_models, mode="shadow"):
    """Keep an unknown legacy PAUSED latch without admitting its performance."""
    rows = store.db.execute(
        "SELECT r.model_id FROM risk_state r JOIN model_versions m ON m.id=r.model_id "
        "WHERE r.mode=? AND r.state='PAUSED' AND m.body=? ORDER BY r.since_session",
        (mode, canonical(config.payload())),
    ).fetchall()
    result = []
    for row in rows:
        model_id = row["model_id"]
        if model_id in cohort_models:
            continue
        bodies = store.db.execute(
            "SELECT body FROM runs WHERE model_id=? AND mode=? AND status='SUCCEEDED' AND body IS NOT NULL",
            (model_id, mode),
        ).fetchall()
        has_explicit_contract = False
        for run in bodies:
            try:
                body = json.loads(run["body"])
                recorded = body.get("risk_cohort_contract")
                claimed = body.get("risk_cohort_id")
                if isinstance(recorded, dict) and isinstance(claimed, str) and digest(recorded) == claimed:
                    has_explicit_contract = True
                    break
            except (TypeError, ValueError):
                continue
        if not has_explicit_contract:
            result.append(model_id)
    return result
