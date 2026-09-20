"""R0 operational attempts and derived reports.

This module never changes an immutable recommendation run.  It turns stored
facts into local operator artifacts and keeps collection failures visible even
when no ``runs`` row could be created.
"""

from collections import Counter
from copy import deepcopy
from datetime import datetime, time
import json
import os
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

from .core import (
    CASH_ACTION_REVIEW_POLICY,
    DEFAULT_OUTCOME_VERSION,
    LEGACY_OUTCOME_VERSION,
    canonical,
    code_hash,
    digest,
    next_sessions,
    open_at,
    timestamp,
    utcnow,
)
from .evaluation import evaluate_outcome_eligibility
from .feature_window import FEATURE_VERSION


REPORT_SCHEMA = "richping_operational_report_v1"
ATTEMPT_SCHEMA = "richping_execution_attempt_v1"
START_SCHEMA = "richping_operational_start_v1"
SEOUL = ZoneInfo("Asia/Seoul")


def atomic_write_text(text, path):
    """Replace one complete UTF-8 artifact without exposing partial content."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    try:
        temporary.write_text(text, encoding="utf-8")
        temporary.replace(path)
    finally:
        if temporary.exists():
            temporary.unlink()


def atomic_write_json(value, path):
    atomic_write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False), path)


def artifact_root(database, command, explicit=None):
    if explicit:
        return Path(explicit)
    default_db = Path(database).resolve() == Path("var/richping.db").resolve()
    if command == "daily" and default_db:
        return Path("var/operations")
    safe_name = Path(database).stem.replace(" ", "-") or "database"
    return Path("var/research") / safe_name / command


class AttemptJournal:
    """A small file-backed lifecycle record created before data collection."""

    def __init__(self, root, command, database, role, now=None, attempt_id=None):
        started = timestamp(now or utcnow())
        self.root = Path(root)
        self.record = {
            "schema": ATTEMPT_SCHEMA,
            "attempt_id": attempt_id or f"{started.strftime('%Y%m%dT%H%M%SZ')}-{uuid4().hex[:10]}",
            "command": command,
            "role": role,
            "database": str(Path(database)),
            "status": "RUNNING",
            "stage": "STARTED",
            "started_at": started.isoformat(),
            "finished_at": None,
            "target_session": None,
            "run_id": None,
            "dataset_id": None,
            "decision": None,
            "error": None,
            "events": [{"stage": "STARTED", "at": started.isoformat()}],
        }
        self.path = self.root / "attempts" / f"{self.record['attempt_id']}.json"
        self.save()

    def save(self):
        atomic_write_json(self.record, self.path)

    def stage(self, name, now=None, **values):
        at = timestamp(now or utcnow()).isoformat()
        self.record.update(values)
        self.record["stage"] = name
        self.record["events"].append({"stage": name, "at": at})
        self.save()

    def finish(self, status, now=None, error=None, **values):
        if status not in {"SUCCEEDED", "FAILED"}:
            raise ValueError("Invalid attempt terminal status")
        at = timestamp(now or utcnow()).isoformat()
        self.record.update(values)
        self.record.update({"status": status, "stage": "COMPLETE" if status == "SUCCEEDED" else "FAILED",
                            "finished_at": at, "error": error})
        self.record["events"].append({"stage": self.record["stage"], "at": at})
        self.save()


def recent_attempts(root, limit=10, include=None):
    attempts = []
    directory = Path(root) / "attempts"
    if directory.exists():
        for path in directory.glob("*.json"):
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError, json.JSONDecodeError):
                continue
            if value.get("schema") == ATTEMPT_SCHEMA:
                attempts.append(value)
    if include is not None and not any(a.get("attempt_id") == include.get("attempt_id") for a in attempts):
        attempts.append(deepcopy(include))
    attempts.sort(key=lambda x: (x.get("started_at") or "", x.get("attempt_id") or ""), reverse=True)
    return attempts[:limit]


def _dataset_capture(dataset):
    capture = dataset.metadata.get("action_capture", {})
    captured_at = capture.get("captured_at")
    bar_known = max((bar.known_at for bar in dataset.bars), default=None)
    values = [v for v in (captured_at, bar_known) if v]
    return max(values, key=lambda v: timestamp(v)) if values else None


def _freshness(run_report, now):
    if not run_report:
        return {"status": "NO_SUCCESSFUL_RUN", "target_session": None, "next_entry_session": None,
                "valid_until": None, "past_next_open": None, "market_closed_gap": None}
    session = run_report["session"]
    next_session = next_sessions(session, 1)[0]
    valid_until = open_at(next_session)
    current = timestamp(now) < valid_until
    gap_days = (datetime.fromisoformat(next_session).date() - datetime.fromisoformat(session).date()).days
    return {"status": "CURRENT" if current else "STALE", "target_session": session,
            "next_entry_session": next_session, "valid_until": valid_until.isoformat(),
            "past_next_open": not current, "market_closed_gap": gap_days > 1}


def _schedule(attempt):
    if not attempt:
        return {"timezone": "Asia/Seoul", "planned_local_time": "08:00", "scheduled_at": None,
                "delay_seconds": None, "status": "NOT_RECORDED"}
    started = timestamp(attempt["started_at"]).astimezone(SEOUL)
    scheduled = datetime.combine(started.date(), time(8, 0), tzinfo=SEOUL)
    delay = (started - scheduled).total_seconds()
    return {"timezone": "Asia/Seoul", "planned_local_time": "08:00",
            "scheduled_at": scheduled.isoformat(), "delay_seconds": delay,
            "status": "LATE" if delay > 15 * 60 else "ON_TIME" if delay >= 0 else "EARLY"}


def _evidence_level(mode, quality):
    if quality == "synthetic":
        return "SYNTHETIC"
    if mode == "shadow":
        return "FRESH_SHADOW"
    return "RESEARCH"


def forward_evidence_summary(store, as_of=None):
    """Summarize stored facts without observing or writing any new outcome."""
    as_of = timestamp(as_of or utcnow()).isoformat()
    run_rows = store.db.execute(
        "SELECT r.id,r.model_id,r.mode,r.session,r.status,r.attempts,r.body,r.dataset_id,d.metadata "
        "FROM runs r JOIN datasets d ON d.id=r.dataset_id ORDER BY r.rowid"
    ).fetchall()
    groups = {}
    run_group = {}
    for row in run_rows:
        metadata = json.loads(row["metadata"])
        body = json.loads(row["body"]) if row["body"] else {}
        contract = body.get("outcome_contract", LEGACY_OUTCOME_VERSION)
        policy = body.get("evaluation_policy", "legacy_unversioned")
        key = (row["model_id"], row["mode"], metadata["source"], metadata["quality"], contract, policy)
        run_group[row["id"]] = key
        group = groups.setdefault(key, {
            "model_id": row["model_id"], "mode": row["mode"], "source": metadata["source"],
            "quality": metadata["quality"], "evidence_level": _evidence_level(row["mode"], metadata["quality"]),
            "outcome_contract": contract, "evaluation_policy": policy,
            "runs": Counter(), "run_attempts": 0, "sessions": set(), "recommendations": 0,
            "outcomes": Counter(), "holding_period": Counter(), "exclusion_reasons": Counter(),
            "duplicate_outcome_vintages_ignored": 0,
        })
        group["runs"][row["status"]] += 1
        group["run_attempts"] += row["attempts"]
        group["sessions"].add(row["session"])

    recommendations = store.db.execute(
        "SELECT q.id,q.run_id,q.snapshot FROM recommendations q JOIN runs r ON r.id=q.run_id ORDER BY q.rowid"
    ).fetchall()
    snapshots = {row["id"]: json.loads(row["snapshot"]) for row in recommendations}
    rec_run = {row["id"]: row["run_id"] for row in recommendations}
    for row in recommendations:
        key = run_group.get(row["run_id"])
        if key in groups:
            groups[key]["recommendations"] += 1

    # One evaluation vintage per recommendation/horizon: latest stored dataset rowid.
    outcome_rows = store.db.execute(
        "SELECT o.rowid AS outcome_rowid,o.recommendation_id,o.horizon,o.dataset_id,o.status,o.body,"
        "d.metadata FROM outcomes o JOIN datasets d ON d.id=o.dataset_id ORDER BY o.rowid"
    ).fetchall()
    selected = {}
    for row in outcome_rows:
        key = (row["recommendation_id"], row["horizon"])
        if key in selected:
            run_id = rec_run.get(row["recommendation_id"])
            group_key = run_group.get(run_id)
            if group_key in groups:
                groups[group_key]["duplicate_outcome_vintages_ignored"] += 1
        selected[key] = row

    datasets = {}
    for (rec_id, horizon), row in selected.items():
        run_id = rec_run.get(rec_id)
        group_key = run_group.get(run_id)
        if group_key not in groups:
            continue
        group = groups[group_key]
        group["outcomes"][row["status"]] += 1
        snapshot = snapshots[rec_id]
        if horizon != snapshot.get("holding_period"):
            continue
        if row["status"] == "COMPLETE":
            try:
                if row["dataset_id"] not in datasets:
                    datasets[row["dataset_id"]] = store.load_dataset(row["dataset_id"])
                dataset = datasets[row["dataset_id"]]
                eligible, reason = evaluate_outcome_eligibility(
                    snapshot, json.loads(row["body"]), dataset=dataset, as_of=as_of,
                    mode=group["mode"],
                )
            except (ValueError, KeyError, json.JSONDecodeError):
                eligible, reason = False, "invalid_stored_outcome"
            group["holding_period"]["ELIGIBLE" if eligible else "EXCLUDED"] += 1
            if reason:
                group["exclusion_reasons"][reason] += 1
        else:
            group["holding_period"][row["status"]] += 1

    result = []
    for group in groups.values():
        expected = group["recommendations"] * 5
        finalized = sum(group["outcomes"].values())
        group["outcomes"]["PENDING_OR_NOT_OBSERVED"] = max(0, expected - finalized)
        group["holding_period"]["PENDING_OR_NOT_OBSERVED"] += max(
            0, group["recommendations"] - sum(group["holding_period"].values())
        )
        result.append({**group, "runs": dict(group["runs"]), "sessions": {
            "count": len(group["sessions"]), "first": min(group["sessions"], default=None),
            "last": max(group["sessions"], default=None)}, "outcomes": dict(group["outcomes"]),
            "holding_period": dict(group["holding_period"]),
            "exclusion_reasons": dict(group["exclusion_reasons"])})
    return {"as_of": as_of, "groups": sorted(result, key=lambda g: (
        g["evidence_level"], g["mode"], g["model_id"])),
            "dedupe_rule": "latest stored dataset rowid per recommendation_id and horizon",
            "read_only": True}


def compatible_risk_latches(store, config, mode="shadow"):
    expected = canonical(config.payload())
    rows = store.db.execute(
        "SELECT r.model_id,r.state,r.since_session,m.body FROM risk_state r "
        "JOIN model_versions m ON m.id=r.model_id WHERE r.mode=? AND r.state='PAUSED'",
        (mode,),
    ).fetchall()
    return [{"model_id": row["model_id"], "state": row["state"], "since_session": row["since_session"]}
            for row in rows if row["body"] == expected]


def ensure_start_manifest(root, store, config, now=None):
    path = Path(root) / "start-manifest.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    predecessors = [row[0] for row in store.db.execute(
        "SELECT id FROM model_versions WHERE body=? AND id<>? ORDER BY rowid", (canonical(config.payload()), config.model_id)
    )]
    manifest = {
        "schema": START_SCHEMA,
        "operational_start_id": digest({"created_at": timestamp(now or utcnow()).isoformat(),
                                        "model_id": config.model_id})[:24],
        "created_at": timestamp(now or utcnow()).isoformat(),
        "status": "DEVELOPMENT_READY_OPERATION_NOT_CONFIRMED",
        "model_id": config.model_id,
        "predecessor_model_ids": predecessors,
        "provenance": {"code_hash": code_hash(), "config_hash": digest(config.payload()),
                       "reason_for_new_model_id": "package code hash includes R0 reporting code",
                       "investment_decision_contract_changed": False},
        "risk_latch_sources": compatible_risk_latches(store, config),
        "contracts": {"feature": FEATURE_VERSION, "outcome": DEFAULT_OUTCOME_VERSION,
                      "evaluation": CASH_ACTION_REVIEW_POLICY},
    }
    atomic_write_json(manifest, path)
    return manifest


def _decision_status(run_report, attempt):
    if attempt and attempt.get("status") == "FAILED":
        return "DATA_FAILURE"
    if not run_report:
        return "NOT_RUN"
    reason = run_report.get("state_reason")
    if reason == "unresolved_outcome_data":
        return "DATA_BLOCKED"
    if run_report.get("state") == "PAUSED" and reason not in {"unsupported_market_regime"}:
        return "RISK_HALT"
    if run_report.get("recommendations"):
        return "CANDIDATES_AVAILABLE"
    return "NORMAL_NO_TRADE"


def build_operational_report(store, config, run_report=None, attempt=None, root=None, now=None,
                             dataset=None, manifest=None, duplicate=False):
    now = timestamp(now or utcnow())
    if run_report is None:
        try:
            run_report = store.latest_report(mode="shadow")
        except ValueError:
            run_report = None
    if dataset is None and run_report:
        try:
            dataset = store.load_dataset(run_report["dataset_id"])
        except ValueError:
            dataset = None
    freshness = _freshness(run_report, now)
    decision_status = _decision_status(run_report, attempt)
    source_is_current = bool(run_report) and decision_status not in {"DATA_FAILURE", "NOT_RUN"}
    candidates = []
    if source_is_current:
        for item in run_report.get("recommendations", []):
            calibration = item["calibration"]
            candidates.append({
                "ticker": item["ticker"], "rank": item["rank"], "score": item["score"],
                "contributors": item["contributors"], "entry_reference_close": item["entry_reference"],
                "atr": item.get("features", {}).get("atr"), "atr_stop_reference": item["stop_reference"],
                "atr_target_reference": item["target_reference"],
                "reference_warning": "Close/ATR references only; not orders or fills",
                "entry_observation": "next XNYS session open", "evaluation_exit": "5th XNYS session close",
                "expected_value": {"mean_return": calibration["expected_return"],
                    "mean_loss": calibration["expected_loss"], "reward_risk": calibration["expected_rr"],
                    "historical_win_frequency": calibration["confidence"],
                    "samples": calibration["samples"], "independent_signal_dates": calibration["signal_dates"],
                    "edge_ci_95": calibration["edge_ci"],
                    "limitation": "research calibration from current-list/revised history; not fresh forward alpha"},
            })
    excluded = Counter((run_report or {}).get("excluded", {}).values())
    raw_reasons = {"insufficient_calibration", "edge_not_supported",
                   "reduced_exposure_edge_threshold", "below_top_k"}
    raw_signal_count = len((run_report or {}).get("recommendations", [])) + sum(
        count for reason, count in excluded.items() if reason in raw_reasons
    )
    attempt_value = deepcopy(attempt) if attempt else None
    attempts = recent_attempts(root, include=attempt_value) if root else ([attempt_value] if attempt_value else [])
    last_success = next((a for a in attempts if a.get("status") == "SUCCEEDED"), None)
    run_model = run_report.get("model") if run_report else config.model_id
    model_row = store.db.execute("SELECT body FROM model_versions WHERE id=?", (run_model,)).fetchone()
    model_config_hash = digest(json.loads(model_row["body"])) if model_row else None
    snapshots = (run_report or {}).get("recommendations", [])
    model_code_hash = (snapshots[0].get("code_hash") if snapshots else
                       code_hash() if run_model == config.model_id else None)
    feature_contract = (snapshots[0].get("feature_normalization") if snapshots else
                        FEATURE_VERSION if run_model == config.model_id else "UNKNOWN_LEGACY_UNRECORDED")
    report = {
        "schema": REPORT_SCHEMA, "generated_at": now.isoformat(),
        "execution": {"status": attempt_value.get("status") if attempt_value else "NOT_RECORDED",
            "attempt_id": attempt_value.get("attempt_id") if attempt_value else None,
            "stage": attempt_value.get("stage") if attempt_value else None,
            "error": attempt_value.get("error") if attempt_value else None,
            "duplicate_run": duplicate,
            "new_forward_observation": bool(source_is_current and attempt_value
                                             and attempt_value.get("status") == "SUCCEEDED" and not duplicate),
            "source_run_is_prior_success": bool(run_report and not source_is_current)},
        "schedule": _schedule(attempt_value), "freshness": {
            **freshness, "run_cutoff": run_report.get("cutoff") if run_report else None,
            "latest_collection_at": _dataset_capture(dataset) if dataset else None,
            "latest_dataset_session": dataset.end if dataset else None},
        "judgment": {"status": decision_status,
            "decision": run_report.get("decision") if source_is_current else None,
            "reason": (attempt_value.get("error") if decision_status == "DATA_FAILURE" else
                       run_report.get("reason") if run_report else "no_successful_shadow_run"),
            "data_failure_is_negative_expected_value": False},
        "identity": {"model_id": run_model,
            "config_hash": model_config_hash or digest(config.payload()),
            "model_code_hash": model_code_hash, "report_code_hash": code_hash(),
            "dataset_id": run_report.get("dataset_id") if run_report else None,
            "mode": run_report.get("mode") if run_report else "shadow",
            "source": dataset.metadata.get("source") if dataset else None,
            "quality": dataset.metadata.get("quality") if dataset else None,
            "feature_contract": feature_contract,
            "outcome_contract": run_report.get("outcome_contract", LEGACY_OUTCOME_VERSION) if run_report else DEFAULT_OUTCOME_VERSION,
            "evaluation_contract": run_report.get("evaluation_policy", "legacy_unversioned") if run_report else CASH_ACTION_REVIEW_POLICY,
            "operational_start_id": manifest.get("operational_start_id") if manifest else None,
            "operational_start_at": manifest.get("created_at") if manifest else None},
        "candidates": candidates,
        "no_trade": {"normal": decision_status == "NORMAL_NO_TRADE",
            "reason": run_report.get("reason") if run_report else None,
            "state": run_report.get("state") if run_report else None,
            "state_reason": run_report.get("state_reason") if run_report else None,
            "universe_size": run_report.get("universe_size") if run_report else len(config.tickers),
            "excluded_by_reason": dict(sorted(excluded.items())),
            "raw_signal_count": raw_signal_count,
            "raw_signal_denominator": len(config.tickers)},
        "outcomes": run_report.get("outcomes") if run_report else None,
        "outcomes_are_prior_success": bool(run_report and not source_is_current),
        "evidence": {"level": _evidence_level(run_report.get("mode"), run_report.get("quality")) if run_report else None,
            "alpha": "INSUFFICIENT_EVIDENCE", "portfolio_return": None,
            "portfolio_return_reason": "recommendation/cohort diagnostics are not account performance",
            "forward_observations": forward_evidence_summary(store, now.isoformat())},
        "operations": {"recent_attempts": attempts, "last_successful_attempt": last_success,
            "unattended_multi_day_stability": "NOT_ESTABLISHED",
            "scheduler_registration": "NOT_VERIFIED_BY_R0_A",
            "required_action": ("inspect attempt error and retry before the next open" if decision_status == "DATA_FAILURE"
                                else "do not reset the performance latch without approved review" if decision_status == "RISK_HALT"
                                else "run daily at the next valid pre-open window" if freshness["status"] == "STALE"
                                else "none")},
        "prior_success_reference": ({"run_id": run_report.get("run_id"), "session": run_report.get("session"),
            "cutoff": run_report.get("cutoff"), "decision": run_report.get("decision")}
            if run_report and not source_is_current else None),
    }
    return report


def refresh_report(report, now=None):
    result = deepcopy(report)
    current = timestamp(now or utcnow())
    valid_until = result.get("freshness", {}).get("valid_until")
    if valid_until:
        stale = current >= timestamp(valid_until)
        result["freshness"]["status"] = "STALE" if stale else "CURRENT"
        result["freshness"]["past_next_open"] = stale
    result["generated_at"] = current.isoformat()
    return result


def format_operational_report(report):
    def val(value):
        return "N/A" if value is None else str(value)

    lines = [f"# Richping daily shadow report - {val(report['freshness']['target_session'])}", "",
             f"- Execution: **{report['execution']['status']}** / {val(report['execution']['stage'])}",
             f"- Freshness: **{report['freshness']['status']}**; valid until {val(report['freshness']['valid_until'])}",
             f"- Run cutoff: {val(report['freshness'].get('run_cutoff'))}; next entry session {val(report['freshness'].get('next_entry_session'))}",
             f"- Judgment: **{report['judgment']['status']}** - {val(report['judgment']['reason'])}",
             f"- Data: {val(report['identity']['source'])} / {val(report['identity']['quality'])}; latest capture {val(report['freshness']['latest_collection_at'])}",
             f"- Model: `{report['identity']['model_id']}`; dataset `{val(report['identity']['dataset_id'])}`",
             f"- Contracts: feature {val(report['identity'].get('feature_contract'))}; outcome {val(report['identity'].get('outcome_contract'))}; evaluation {val(report['identity'].get('evaluation_contract'))}",
             f"- Code: model {val(report['identity'].get('model_code_hash'))}; report {val(report['identity'].get('report_code_hash'))}", ""]
    if report["judgment"]["status"] == "DATA_FAILURE":
        lines += ["The current attempt failed before a valid new judgment was produced. A prior success is reference only.", ""]
    elif report["judgment"]["status"] == "NORMAL_NO_TRADE":
        lines += ["## Normal NO TRADE", "", f"Reason: {val(report['no_trade']['reason'])}",
                  f"Excluded reasons: {json.dumps(report['no_trade']['excluded_by_reason'], ensure_ascii=False, sort_keys=True)}", ""]
    elif report["candidates"]:
        lines += ["## Candidates", ""]
        for item in report["candidates"]:
            ev = item["expected_value"]
            lines += [f"- {item['rank']}. **{item['ticker']}** score {item['score']:.2f}; "
                      f"close ref {item['entry_reference_close']:.2f}, ATR {val(item['atr'])}, "
                      f"stop/target refs {item['atr_stop_reference']:.2f}/{item['atr_target_reference']:.2f}",
                      f"  Evidence: mean {val(ev['mean_return'])}, loss {val(ev['mean_loss'])}, R/R {val(ev['reward_risk'])}, "
                      f"win frequency {val(ev['historical_win_frequency'])}; {ev['samples']} samples / "
                      f"{ev['independent_signal_dates']} dates / CI {val(ev['edge_ci_95'])}."]
        lines.append("")
    outcomes = report.get("outcomes") or {}
    evaluation = outcomes.get("evaluation", {}) if isinstance(outcomes, dict) else {}
    lines += ["## Outcomes and evidence", "",
              f"- Horizons: COMPLETE {outcomes.get('COMPLETE', 0)}, PENDING {outcomes.get('PENDING', 0)}, UNRESOLVED {outcomes.get('UNRESOLVED', 0)}",
              f"- Holding evaluation: eligible {evaluation.get('eligible_complete', 0)}, excluded {evaluation.get('excluded_complete', 0)} under {val(evaluation.get('policy'))}",
              f"- Evidence level: {val(report['evidence']['level'])}; Alpha: {report['evidence']['alpha']}; portfolio return: N/A", "",
              "## Operations", "",
              f"- Planned: 08:00 Asia/Seoul; this attempt: {report['schedule']['status']} ({val(report['schedule']['delay_seconds'])} seconds)",
              f"- Duplicate/re-display: {report['execution']['duplicate_run']}; new forward observation: {report['execution']['new_forward_observation']}",
              f"- Unattended multi-day stability: {report['operations']['unattended_multi_day_stability']}",
              f"- Required action: {report['operations'].get('required_action', 'none')}"]
    groups = report.get("evidence", {}).get("forward_observations", {}).get("groups", [])
    if groups:
        lines += ["", "Stored forward observation groups (read-only):"]
        for group in groups:
            lines.append(
                f"- {group['evidence_level']} / {group['mode']} / {group['model_id']}: "
                f"runs {json.dumps(group['runs'], sort_keys=True)}, sessions {group['sessions']['count']}, "
                f"recommendations {group['recommendations']}, outcomes {json.dumps(group['outcomes'], sort_keys=True)}"
            )
    return "\n".join(lines) + "\n"


def publish_report(report, root):
    root = Path(root)
    session = report.get("freshness", {}).get("target_session") or "no-session"
    attempt = report.get("execution", {}).get("attempt_id") or "no-attempt"
    generation = digest({"generated_at": report.get("generated_at"), "attempt": attempt,
                         "status": report.get("execution", {}).get("status")})[:10]
    stem = f"{session}-{attempt}-{generation}"
    version_json = root / "reports" / f"{stem}.json"
    version_markdown = root / "reports" / f"{stem}.md"
    published = deepcopy(report)
    published["artifacts"] = {"json": str(version_json), "markdown": str(version_markdown)}
    json_text = json.dumps(published, indent=2, ensure_ascii=False, allow_nan=False)
    markdown = format_operational_report(published)
    # Versioned files become a complete generation before latest.json points at
    # it.  A failure in either write leaves the previous latest generation.
    atomic_write_text(json_text, version_json)
    atomic_write_text(markdown, version_markdown)
    atomic_write_text(json_text, root / "latest.json")
    return {"json": str(root / "latest.json"), "markdown": str(version_markdown)}
