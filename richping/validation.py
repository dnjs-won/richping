"""Fixed-rule rolling train/validation/OOS replay, with frozen calibration per fold."""

from dataclasses import dataclass

from .core import CASH_ACTION_REVIEW_POLICY, LEGACY_OUTCOME_VERSION, canonical, code_hash, cutoff_at, utcnow
from .engine import Engine, observe
from .evaluation import block_ci, evaluate_outcome_eligibility, metrics, promotion_gate


@dataclass(frozen=True)
class Fold:
    train_start: int
    train_end: int
    validation_start: int
    validation_end: int
    oos_start: int
    oos_end: int


def walk_forward_folds(length, train=504, validation=63, oos=63, purge=21, warmup=60):
    if min(train, validation, oos, purge) < 1 or warmup < 60:
        raise ValueError("Invalid time split")
    first = warmup + train + purge
    for start in range(first, length - validation - oos + 1, oos):
        yield Fold(start - purge - train, start - purge - 1,
                   start, start + validation - 1, start + validation, start + validation + oos - 1)


def validate(store, dataset, config, train=504, validation=63, oos=63):
    from dataclasses import replace
    config = replace(config, train_sessions=train)
    spec = {"model": config.model_id, "config": config.payload(), "code": code_hash(), "dataset": dataset.id,
            "train": train, "validation": validation, "oos": oos, "purge": 21,
            "cost": config.cost, "stress_cost": config.cost * 2, "kind": "research_OOS",
            "selection": "fixed baseline; no parameter selection; frozen calibration at validation start"}
    with store.db:
        trial = store.db.execute("INSERT INTO experiments(created_at,status,specification) VALUES(?,'RUNNING',?)",
                                 (utcnow(), canonical(spec))).lastrowid
    try:
        engine = Engine(dataset, config)
        folds, all_rows = [], []
        for fold in walk_forward_folds(len(dataset.sessions), train, validation, oos):
            boundary = dataset.sessions[fold.validation_start]
            outputs = {}
            for label, start, end in (("validation", fold.validation_start, fold.validation_end),
                                       ("oos", fold.oos_start, fold.oos_end)):
                rows, counts, benchmark_rows = [], {
                    "COMPLETE": 0,
                    "PENDING": 0,
                    "UNRESOLVED": 0,
                    "evaluation": {
                        "policy": CASH_ACTION_REVIEW_POLICY,
                        "eligible_complete": 0,
                        "excluded_complete": 0,
                        "by_reason": {},
                        "by_version": {},
                    },
                }, []
                spy_evaluation = {
                    "policy": CASH_ACTION_REVIEW_POLICY,
                    "eligible_complete": 0,
                    "excluded_complete": 0,
                    "by_reason": {},
                    "by_version": {},
                }
                excluded_sessions = 0
                for i in range(start, end + 1):
                    session = dataset.sessions[i]
                    try:
                        signals = engine.signals(session)
                    except ValueError:
                        excluded_sessions += 1
                        continue
                    if not signals["supported"]:
                        continue
                    chosen = []
                    for signal in signals["candidates"]:
                        if engine.calibration(signal, boundary)["eligible"]:
                            chosen.append(signal)
                        if len(chosen) >= config.top_k:
                            break
                    for signal in chosen:
                        outcome = observe(signal, dataset, config.horizon, cutoff_at(dataset.sessions[end]).isoformat())
                        counts[outcome["status"]] += 1
                        if outcome["status"] == "COMPLETE":
                            is_eligible, reason = evaluate_outcome_eligibility(
                                signal, outcome, dataset=dataset, as_of=cutoff_at(dataset.sessions[end]).isoformat(), mode="research"
                            )
                            ver = outcome.get("outcome_version", LEGACY_OUTCOME_VERSION)
                            if is_eligible:
                                counts["evaluation"]["eligible_complete"] += 1
                                rows.append({**outcome, "session": session, "ticker": signal["ticker"], "regime": signal["regime"]})
                            else:
                                counts["evaluation"]["excluded_complete"] += 1
                                counts["evaluation"]["by_reason"][reason] = (
                                    counts["evaluation"]["by_reason"].get(reason, 0) + 1
                                )
                                counts["evaluation"]["by_version"][ver] = (
                                    counts["evaluation"]["by_version"].get(ver, 0) + 1
                                )
                    if chosen:
                        b = dataset.by_ticker["SPY"][session]
                        spy_signal = {**chosen[0], "ticker": "SPY", "entry_reference": b.close,
                                      "stop_reference": b.close * 0.9, "target_reference": b.close * 1.2}
                        observed = observe(spy_signal, dataset, config.horizon, cutoff_at(dataset.sessions[end]).isoformat())
                        if observed["status"] == "COMPLETE":
                            spy_eligible, spy_reason = evaluate_outcome_eligibility(
                                spy_signal, observed, dataset=dataset, as_of=cutoff_at(dataset.sessions[end]).isoformat(), mode="research"
                            )
                            spy_ver = observed.get("outcome_version", LEGACY_OUTCOME_VERSION)
                            if spy_eligible:
                                spy_evaluation["eligible_complete"] += 1
                                benchmark_rows.append({**observed, "session": session})
                            else:
                                spy_evaluation["excluded_complete"] += 1
                                spy_evaluation["by_reason"][spy_reason] = (
                                    spy_evaluation["by_reason"].get(spy_reason, 0) + 1
                                )
                                spy_evaluation["by_version"][spy_ver] = (
                                    spy_evaluation["by_version"].get(spy_ver, 0) + 1
                                )
                outputs[label] = {"start": dataset.sessions[start], "end": dataset.sessions[end],
                    "metrics": metrics(rows), "outcomes": counts, "invalid_sessions": excluded_sessions,
                    "recommendation_frequency": sum(counts[k] for k in ("COMPLETE", "PENDING", "UNRESOLVED")) / (end - start + 1),
                    "date_block_ci": block_ci(rows, config.bootstrap_samples, config.seed),
                    "matched_SPY": metrics(benchmark_rows),
                    "matched_SPY_evaluation": spy_evaluation,
                    "cost_stress": metrics([{**r, "net_return": r["net_return"] - config.cost} for r in rows]),
                    "by_regime": {regime: metrics([r for r in rows if r["regime"] == regime]) for regime in sorted({r["regime"] for r in rows})}}
                if label == "oos":
                    all_rows.extend(rows)
            folds.append({"train_start": dataset.sessions[fold.train_start], "train_end": dataset.sessions[fold.train_end],
                          "calibration_frozen_at": boundary, **outputs})
        if not folds:
            raise ValueError("Insufficient sessions for requested train/validation/OOS windows")
        result = {"trial": trial, "specification": spec, "folds": folds, "oos": metrics(all_rows),
                  "oos_predictions": all_rows, "promotion": promotion_gate({}),
                  "limitations": ["Research OOS only; fixed current universe/revised data or synthetic input",
                                  "No fitted challenger, no untouched final holdout, no portfolio NAV",
                                  "Fixed-model validation measures ranker, not operational kill-switch behavior"]}
        with store.db:
            store.db.execute("UPDATE experiments SET status='SUCCEEDED',result=? WHERE id=?", (canonical(result), trial))
        return result
    except Exception as exc:
        with store.db:
            store.db.execute("UPDATE experiments SET status='FAILED',result=? WHERE id=?", (canonical({"error": str(exc)}), trial))
        raise
