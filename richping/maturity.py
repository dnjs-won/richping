"""Read-only maturity follow-up for a frozen validation selection.

The source validation remains immutable.  This module reconstructs only the
observation inputs recorded by the R1-A artifact, verifies them at the original
fold cutoff, and then evaluates the identical selection at a later cutoff.
"""

from collections import Counter
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

from .core import CASH_ACTION_REVIEW_POLICY, OUTCOME_VERSION_V3, cutoff_at, next_sessions
from .engine import observe
from .evaluation import evaluate_outcome_eligibility, metrics
from .store import Store


SCHEMA = "richping_maturity_followup_v1"


def file_sha256(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def _snapshot(record, cost, horizon):
    features = record.get("features") or {}
    price = features.get("price")
    atr = features.get("atr")
    if not isinstance(price, (int, float)) or not isinstance(atr, (int, float)):
        raise ValueError("SOURCE_RECONSTRUCTION_UNVERIFIED: missing price/atr")
    return {
        "ticker": record["ticker"],
        "session": record["session"],
        "regime": record["regime"],
        "entry_reference": price,
        "stop_reference": price - 2 * atr,
        "target_reference": price + 4 * atr,
        "cost": cost,
        "holding_period": horizon,
        "outcome_version": OUTCOME_VERSION_V3,
    }


def _same_outcome(record, outcome):
    if outcome["status"] != record.get("outcome_status"):
        return False
    if outcome.get("reason") != record.get("outcome_reason"):
        return False
    expected = record.get("net_return")
    actual = outcome.get("net_return")
    if expected is None:
        return actual is None
    return isinstance(actual, (int, float)) and abs(actual - expected) <= 1e-12


def _counts(rows, key):
    values = Counter(row[key]["status"] for row in rows)
    return {name: values.get(name, 0) for name in ("COMPLETE", "PENDING", "UNRESOLVED")}


def _pairing(rows, spy_rows, candidate_key, spy_key):
    by_session = {}
    for row in rows:
        by_session.setdefault(row["session"], []).append(row)
    result = {"attempted_signal_dates": len(by_session), "both": [], "candidate_only": [],
              "spy_only": [], "neither": [], "candidate_reasons": {}, "spy_reasons": {}}
    candidate_metrics = []
    spy_metrics = []
    for session in sorted(by_session):
        candidates = by_session[session]
        candidate_returns = [row[candidate_key]["net_return"] for row in candidates
                             if row[candidate_key]["eligible"]]
        candidate_ok = bool(candidate_returns)
        spy = spy_rows[session][spy_key]
        spy_ok = spy["eligible"]
        bucket = ("both" if candidate_ok and spy_ok else "candidate_only" if candidate_ok else
                  "spy_only" if spy_ok else "neither")
        result[bucket].append(session)
        for row in candidates:
            if not row[candidate_key]["eligible"]:
                reason = row[candidate_key].get("eligibility_reason") or row[candidate_key].get("reason")
                result["candidate_reasons"][reason] = result["candidate_reasons"].get(reason, 0) + 1
        if not spy_ok:
            reason = spy.get("eligibility_reason") or spy.get("reason")
            result["spy_reasons"][reason] = result["spy_reasons"].get(reason, 0) + 1
        if bucket == "both":
            candidate_metrics.append({"session": session,
                                      "net_return": sum(candidate_returns) / len(candidate_returns)})
            spy_metrics.append({"session": session, "net_return": spy["net_return"]})
    result["paired_signal_dates"] = len(result["both"])
    result["unmatched_signal_dates"] = len(by_session) - len(result["both"])
    result["candidate_metrics"] = metrics(candidate_metrics)
    result["spy_metrics"] = metrics(spy_metrics)
    return result


def maturity_followup(source_db, validation_path, failure_path, dataset_id=None, followup_as_of=None):
    """Return a verified original/follow-up view without writing source artifacts."""
    validation_path, failure_path = Path(validation_path), Path(failure_path)
    validation = json.loads(validation_path.read_text(encoding="utf-8"))
    failure = json.loads(failure_path.read_text(encoding="utf-8"))
    records = failure.get("oos_selected_records")
    if not isinstance(records, list) or not records:
        raise ValueError("SOURCE_RECONSTRUCTION_UNVERIFIED: selected records unavailable")
    spec = validation.get("specification") or {}
    dataset_id = dataset_id or spec.get("dataset") or (failure.get("contract") or {}).get("dataset_id")
    cost = spec.get("cost")
    horizon = (spec.get("config") or {}).get("horizon", 5)
    if not dataset_id or not isinstance(cost, (int, float)):
        raise ValueError("SOURCE_RECONSTRUCTION_UNVERIFIED: dataset/cost unavailable")
    folds = validation.get("folds") or []
    if not folds:
        raise ValueError("SOURCE_RECONSTRUCTION_UNVERIFIED: fold cutoffs unavailable")

    with Store(source_db, read_only=True) as store:
        dataset = store.load_dataset(dataset_id)
    followup_as_of = followup_as_of or cutoff_at(dataset.end).isoformat()
    rows = []
    seen = set()
    for source in records:
        fold_index = int(source["fold"]) - 1
        if fold_index < 0 or fold_index >= len(folds):
            raise ValueError("SOURCE_RECONSTRUCTION_UNVERIFIED: invalid fold")
        key = (file_sha256(failure_path), source["fold"], source.get("phase"),
               source["session"], source["ticker"], horizon)
        if key in seen:
            raise ValueError("SOURCE_RECONSTRUCTION_UNVERIFIED: duplicate selected record")
        seen.add(key)
        snapshot = _snapshot(source, cost, horizon)
        original_as_of = cutoff_at(folds[fold_index]["oos"]["end"]).isoformat()
        original = observe(snapshot, dataset, horizon, original_as_of, "research")
        if not _same_outcome(source, original):
            raise ValueError(f"SOURCE_RECONSTRUCTION_UNVERIFIED: {source['session']} {source['ticker']}")
        old_ok, old_reason = evaluate_outcome_eligibility(
            snapshot, original, dataset=dataset, as_of=original_as_of, mode="research"
        )
        later = observe(snapshot, dataset, horizon, followup_as_of, "research")
        later_ok, later_reason = evaluate_outcome_eligibility(
            snapshot, later, dataset=dataset, as_of=followup_as_of, mode="research"
        )
        rows.append({
            "source_key": "|".join(map(str, key)), "fold": source["fold"], "phase": source.get("phase"),
            "session": source["session"], "ticker": source["ticker"], "rank": None,
            "score": source.get("score"), "regime": source.get("regime"),
            "provenance": "DERIVED_RESEARCH_INPUT", "snapshot": snapshot,
            "original_as_of": original_as_of,
            "original": {**deepcopy(original), "eligible": old_ok, "eligibility_reason": old_reason},
            "followup_as_of": followup_as_of,
            "followup": {**deepcopy(later), "eligible": later_ok, "eligibility_reason": later_reason},
        })
    for session in sorted({row["session"] for row in rows}):
        ranked = sorted((row for row in rows if row["session"] == session),
                        key=lambda row: (-row["score"], row["ticker"]))
        for rank, row in enumerate(ranked, 1):
            row["rank"] = rank

    spy_rows = {}
    for session in sorted({row["session"] for row in rows}):
        first = next(row for row in rows if row["session"] == session)
        bar = dataset.by_ticker.get("SPY", {}).get(session)
        if bar is None:
            raise ValueError("SOURCE_RECONSTRUCTION_UNVERIFIED: SPY signal bar missing")
        snapshot = {**first["snapshot"], "ticker": "SPY", "entry_reference": bar.close,
                    "stop_reference": bar.close * .9, "target_reference": bar.close * 1.2}
        original = observe(snapshot, dataset, horizon, first["original_as_of"], "research")
        old_ok, old_reason = evaluate_outcome_eligibility(
            snapshot, original, dataset=dataset, as_of=first["original_as_of"], mode="research"
        )
        later = observe(snapshot, dataset, horizon, followup_as_of, "research")
        later_ok, later_reason = evaluate_outcome_eligibility(
            snapshot, later, dataset=dataset, as_of=followup_as_of, mode="research"
        )
        spy_rows[session] = {"snapshot": snapshot,
            "original": {**original, "eligible": old_ok, "eligibility_reason": old_reason},
            "followup": {**later, "eligible": later_ok, "eligibility_reason": later_reason}}

    stored_predictions = validation.get("oos_predictions") or []
    eligible_rows = [row for row in rows if row["original"]["eligible"]]
    if len(eligible_rows) != len(stored_predictions):
        raise ValueError("SOURCE_RECONSTRUCTION_UNVERIFIED: eligible prediction denominator mismatch")
    transitions = Counter(f"{row['original']['status']}->{row['followup']['status']}" for row in rows)
    return {
        "schema": SCHEMA,
        "source": {"database": str(source_db), "dataset_id": dataset.id,
            "validation": str(validation_path), "validation_sha256": file_sha256(validation_path),
            "failure_analysis": str(failure_path), "failure_analysis_sha256": file_sha256(failure_path),
            "model_id": spec.get("model"), "outcome_contract": OUTCOME_VERSION_V3,
            "evaluation_policy": CASH_ACTION_REVIEW_POLICY, "selection": "frozen OOS; not reselected"},
        "evaluation_period": {"start": folds[0]["oos"]["start"],
                              "last_allowed_signal_session": folds[-1]["oos"]["end"],
                              "paper_end": next_sessions(folds[-1]["oos"]["end"], horizon)[-1]},
        "verification": {"status": "VERIFIED", "selected_records": len(rows),
            "original_outcomes_and_returns_matched": len(rows),
            "stored_eligible_predictions_matched": len(eligible_rows)},
        "original": {"as_of_by_fold": {str(i + 1): cutoff_at(fold["oos"]["end"]).isoformat()
                                        for i, fold in enumerate(folds)},
            "outcomes": _counts(rows, "original"),
            "eligible_complete": sum(row["original"]["eligible"] for row in rows),
            "pairing": _pairing(rows, spy_rows, "original", "original")},
        "followup": {"as_of": followup_as_of, "dataset_id": dataset.id,
            "outcomes": _counts(rows, "followup"),
            "eligible_complete": sum(row["followup"]["eligible"] for row in rows),
            "pairing": _pairing(rows, spy_rows, "followup", "followup")},
        "transitions": dict(sorted(transitions.items())), "source_items": rows,
        "spy_items": spy_rows,
        "limitations": ["Consumed research OOS; not fresh shadow or untouched confirmation",
                        "Reconstructed observation inputs are not immutable issued recommendation snapshots",
                        "Maturity follow-up does not rewrite calibration, risk state, or original outcomes"],
    }


def format_maturity_report(report):
    old, new = report["original"], report["followup"]
    lines = ["# Richping R1 maturity follow-up", "",
             f"- Source verification: **{report['verification']['status']}**; {report['verification']['selected_records']} frozen selections",
             f"- Original: {old['outcomes']}; eligible {old['eligible_complete']}; SPY paired {old['pairing']['paired_signal_dates']}/{old['pairing']['attempted_signal_dates']}",
             f"- Follow-up: {new['outcomes']}; eligible {new['eligible_complete']}; SPY paired {new['pairing']['paired_signal_dates']}/{new['pairing']['attempted_signal_dates']}",
             f"- Transitions: {json.dumps(report['transitions'], sort_keys=True)}", "",
             "This is a separate consumed-research maturity view. It does not replace the frozen OOS or prove Alpha."]
    return "\n".join(lines) + "\n"
