import json

from .core import (
    CASH_ACTION_REVIEW_POLICY,
    DEFAULT_OUTCOME_VERSION,
    LEGACY_OUTCOME_VERSION,
    OUTCOME_VERSION_V1,
    OUTCOME_VERSION_V2,
    OUTCOME_VERSION_V3,
    SUPPORTED_OUTCOME_VERSIONS,
    canonical,
    code_hash,
    cutoff_at,
    digest,
    next_sessions,
    open_at,
    timestamp,
    utcnow,
)
from .engine import Engine, observe
from .evaluation import evaluate_outcome_eligibility, metrics, risk_decision


def track(store, dataset, as_of, model_id=None, mode=None):
    """Retry safe; immutable outcome vintages, pending observations aren't finalized."""
    counts = {
        "COMPLETE": 0,
        "PENDING": 0,
        "UNRESOLVED": 0,
        "evaluation": {
            "policy": CASH_ACTION_REVIEW_POLICY,
            "eligible_complete": 0,
            "excluded_complete": 0,
            "by_reason": {},
            "by_version": {},
            "excluded_groups": [],
            "by_group": {},
        },
    }
    rows = []
    records = store.db.execute("SELECT r.id,r.snapshot,u.model_id,u.mode,u.dataset_id,d.metadata FROM recommendations r "
        "JOIN runs u ON u.id=r.run_id JOIN datasets d ON d.id=u.dataset_id ORDER BY u.session,r.rank").fetchall()
    with store.db:
        for rec in records:
            if model_id and rec["model_id"] != model_id or mode and rec["mode"] != mode:
                continue
            if rec["mode"] == "research" and rec["dataset_id"] != dataset.id:
                continue
            metadata = json.loads(rec["metadata"])
            if metadata["source"] != dataset.metadata["source"] or metadata["quality"] != dataset.metadata["quality"]:
                continue
            snap = json.loads(rec["snapshot"])
            if timestamp(snap["cutoff"]) > timestamp(as_of):
                continue

            group_key = f"{rec['model_id']}:{rec['mode']}"
            if group_key not in counts["evaluation"]["by_group"]:
                counts["evaluation"]["by_group"][group_key] = {
                    "model_id": rec["model_id"],
                    "mode": rec["mode"],
                    "eligible_complete": 0,
                    "excluded_complete": 0,
                    "by_reason": {},
                    "by_version": {},
                }

            for horizon in (1, 3, 5, 10, 20):
                # Check for existing finalized outcome in store
                stored_row = store.db.execute(
                    "SELECT status, body FROM outcomes WHERE recommendation_id=? AND horizon=? AND dataset_id=?",
                    (rec["id"], horizon, dataset.id),
                ).fetchone()

                use_stored = False
                if stored_row is not None:
                    stored_body = json.loads(stored_row["body"])
                    end_sess = stored_body.get("end_session") or next_sessions(snap["session"], horizon)[-1]
                    obs_at = stored_body.get("observed_at")
                    # Enforce point-in-time rules: do not use future stored outcomes before as_of
                    if cutoff_at(end_sess) <= timestamp(as_of) and (not obs_at or timestamp(obs_at) <= timestamp(as_of)):
                        result = stored_body
                        use_stored = True

                if not use_stored:
                    result = observe(snap, dataset, horizon, as_of, rec["mode"])
                    if result["status"] != "PENDING":
                        store.db.execute(
                            "INSERT OR IGNORE INTO outcomes VALUES(?,?,?,?,?)",
                            (rec["id"], horizon, dataset.id, result["status"], canonical(result)),
                        )

                counts[result["status"]] += 1

                if horizon == snap["holding_period"] and result["status"] == "COMPLETE":
                    is_eligible, reason = evaluate_outcome_eligibility(
                        snap, result, dataset=dataset, as_of=as_of, mode=rec["mode"]
                    )
                    ver = result.get("outcome_version", LEGACY_OUTCOME_VERSION)
                    grp = counts["evaluation"]["by_group"][group_key]

                    if is_eligible:
                        counts["evaluation"]["eligible_complete"] += 1
                        grp["eligible_complete"] += 1
                        rows.append({
                            **result,
                            "session": snap["session"],
                            "ticker": snap["ticker"],
                            "regime": snap.get("regime", ""),
                            "recommendation_id": rec["id"],
                            "model_id": rec["model_id"],
                            "mode": rec["mode"],
                            "outcome_version": ver,
                        })
                    else:
                        counts["evaluation"]["excluded_complete"] += 1
                        grp["excluded_complete"] += 1
                        counts["evaluation"]["by_reason"][reason] = (
                            counts["evaluation"]["by_reason"].get(reason, 0) + 1
                        )
                        grp["by_reason"][reason] = grp["by_reason"].get(reason, 0) + 1
                        counts["evaluation"]["by_version"][ver] = (
                            counts["evaluation"]["by_version"].get(ver, 0) + 1
                        )
                        grp["by_version"][ver] = grp["by_version"].get(ver, 0) + 1

    counts["evaluation"]["excluded_groups"] = [
        g for g in counts["evaluation"]["by_group"].values()
        if g["excluded_complete"] > 0 and g["eligible_complete"] == 0
    ]
    return counts, rows


def scan(store, dataset, config, session, mode="research", now=None, engine=None):
    store.save_model(config)
    if mode not in {"research", "shadow"}:
        raise ValueError("Invalid run mode")
    cutoff = timestamp(now or utcnow()) if mode == "shadow" else cutoff_at(session)
    if cutoff_at(session) > cutoff:
        raise ValueError("Incomplete session")
    # Real-time recommendations can't backdate an already missed next-open entry.
    if mode == "shadow" and cutoff >= open_at(next_sessions(session, 1)[0]):
        raise ValueError("Stale signal: next session already opened")
    run_id = digest({"model": config.model_id, "session": session, "mode": mode,
                     "dataset": dataset.id if mode == "research" else None})
    with store.db:
        store.db.execute("BEGIN IMMEDIATE")
        existing = store.db.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
        if existing and existing["status"] == "SUCCEEDED":
            return json.loads(existing["body"])
        if existing and existing["status"] == "RUNNING":
            raise ValueError("Run already active; use recover-runs after confirming no process is running")
        if existing:
            store.db.execute("UPDATE runs SET status='RUNNING',attempts=attempts+1,error=NULL,dataset_id=? WHERE id=?", (dataset.id, run_id))
        else:
            store.db.execute("INSERT INTO runs VALUES(?,?,?,?,?,'RUNNING',1,NULL,NULL,?)",
                (run_id, dataset.id, config.model_id, session, mode, utcnow()))
    try:
        counts, rows = track(store, dataset, cutoff.isoformat(), config.model_id, mode)
        prior = store.db.execute("SELECT state,since_session FROM risk_state WHERE model_id=? AND mode=?",
                                 (config.model_id, mode)).fetchone()
        previous = prior["state"] if prior and prior["since_session"] <= session else "NORMAL"
        state, reason = risk_decision(rows, previous)
        engine = engine or Engine(dataset, config)
        signals = engine.signals(session, cutoff.isoformat(), mode)
        if not signals["supported"] and state != "PAUSED":
            state, reason = "PAUSED", "unsupported_market_regime"
        if (counts["UNRESOLVED"] or counts.get("evaluation", {}).get("excluded_complete", 0)) and state != "PAUSED":
            state, reason = "PAUSED", "unresolved_outcome_data"
        limit = 1 if state == "REDUCED_EXPOSURE" else config.top_k
        picks, rejected = [], dict(signals["excluded"])
        if state != "PAUSED":
            for candidate in signals["candidates"]:
                calibration = engine.calibration(candidate)
                if not calibration["eligible"]:
                    rejected[candidate["ticker"]] = calibration["reason"]
                    continue
                if state == "REDUCED_EXPOSURE" and calibration["edge_ci"][0] <= max(0.002, config.min_edge):
                    rejected[candidate["ticker"]] = "reduced_exposure_edge_threshold"
                    continue
                if len(picks) >= limit:
                    rejected[candidate["ticker"]] = "below_top_k"
                    continue
                member = next(m for m in dataset.members if m["ticker"] == candidate["ticker"])
                picks.append({**candidate, "calibration": calibration, "model_version": config.model_id,
                    "data_id": dataset.id, "config_hash": digest(config.payload()), "code_hash": code_hash(),
                    "mode": mode, "quality": dataset.metadata["quality"], "sector": member.get("sector"),
                    "industry": member.get("industry"), "rank": len(picks) + 1,
                    "id": digest([run_id, candidate["ticker"]])})
        recent = sorted(rows, key=lambda r: (r["session"], r["ticker"]))[-30:]
        report = {"run_id": run_id, "session": session, "cutoff": cutoff.isoformat(), "mode": mode,
            "quality": dataset.metadata["quality"], "model": config.model_id, "dataset_id": dataset.id,
            "regime": signals["regime"], "state": state, "state_reason": reason,
            "outcome_contract": DEFAULT_OUTCOME_VERSION,
            "evaluation_policy": CASH_ACTION_REVIEW_POLICY,
            "decision": "TRADE CANDIDATES AVAILABLE" if picks else "NO TRADE",
            "reason": "qualified_candidates" if picks else (reason if state == "PAUSED" else "insufficient_evidence_or_edge"),
            "recommendations": picks, "excluded": rejected, "universe_size": len(config.tickers),
            "outcomes": counts, "recent_30": metrics(recent),
            "limitations": ["research/shadow only; no validated alpha or order execution",
                            "current-list/revised historical calibration is not point-in-time validated",
                            "corporate-action windows (splits, capital gains, cash dividends) and missing outcome windows are unresolved in v3"]}
        with store.db:
            for snap in picks:
                store.db.execute("INSERT INTO recommendations VALUES(?,?,?,?,?)",
                                 (snap["id"], run_id, snap["ticker"], snap["rank"], canonical(snap)))
            # Regime pauses are transient; performance pauses latch permanently.
            if reason not in {"unsupported_market_regime", "unresolved_outcome_data"} and (prior is None or session >= prior["since_session"]):
                store.db.execute("INSERT INTO risk_state VALUES(?,?,?,?) ON CONFLICT(model_id,mode) "
                                 "DO UPDATE SET state=excluded.state,since_session=excluded.since_session",
                                 (config.model_id, mode, state, session))
            store.db.execute("UPDATE runs SET status='SUCCEEDED',body=? WHERE id=?", (canonical(report), run_id))
        return report
    except Exception as exc:
        with store.db:
            store.db.execute("UPDATE runs SET status='FAILED',error=? WHERE id=?", (str(exc), run_id))
        raise


def format_report(report):
    def pct(value):
        return "N/A" if value is None else f"{value:+.2%}"
    if "outcome_contract" not in report:
        contract = OUTCOME_VERSION_V1
    else:
        raw_contract = report["outcome_contract"]
        if raw_contract in SUPPORTED_OUTCOME_VERSIONS:
            contract = str(raw_contract)
        elif raw_contract is None or raw_contract == "":
            contract = "unsupported (empty)"
        else:
            contract = f"{raw_contract} (unsupported)"
    lines = [f"{report['session']} DAILY RECOMMENDATION", f"Data: {report['quality'].upper()} / {report['mode']}",
             f"Market: {report['regime']}", f"System: {report['state']} ({report['state_reason']})",
             f"Model: {report['model']}", f"Outcome Contract: {contract}", "", report["decision"]]
    if not report["recommendations"]:
        lines.append("Reason: " + report["reason"])
    else:
        lines.append("Rank Ticker Score Exp.Return Exp.Loss R/R Confidence")
    for s in report["recommendations"]:
        e = s["calibration"]
        rr = "N/A" if e["expected_rr"] is None else f"{e['expected_rr']:.2f}"
        lines.append(f"{s['rank']:>4} {s['ticker']:<6} {s['score']:5.1f} {pct(e['expected_return']):>10} "
                     f"{pct(-e['expected_loss']) if e['expected_loss'] is not None else 'N/A':>8} {rr:>5} {e['confidence']:.1%}")
        lines.append(f"     Entry ref {s['entry_reference']:.2f} | Stop {s['stop_reference']:.2f} | "
                     f"Target {s['target_reference']:.2f} | Hold {s['holding_period']} sessions")
        lines.append("     Contributors: " + ", ".join(f"{k} +{v:.1f}" for k, v in s["contributors"].items()))
        lines.append(f"     Evidence: {e['samples']} samples / {e['signal_dates']} dates; "
                     f"edge CI [{pct(e['edge_ci'][0])}, {pct(e['edge_ci'][1])}]")
    m = report.get("recent_30", {"samples": 0, "expectancy": None})
    lines += ["", f"Recent completed recommendations: {m.get('samples', 0)} | Expectancy {pct(m.get('expectancy'))}",
              f"Outcome horizons: {report.get('outcomes', {})}",
              "Confidence = historical win frequency. References are not fills.",
              "Research/shadow only. Synthetic results are not investment evidence."]

    eval_info = report.get("outcomes", {}).get("evaluation")
    if eval_info:
        policy = eval_info.get("policy", CASH_ACTION_REVIEW_POLICY)
        el = eval_info.get("eligible_complete", 0)
        ex = eval_info.get("excluded_complete", 0)
        reasons_str = ", ".join(f"{k}: {v}" for k, v in sorted(eval_info.get("by_reason", {}).items())) or "none"
        lines.append(f"Evaluation Policy: {policy} | Eligible: {el} | Excluded: {ex} (Reasons: {reasons_str})")

    if contract == OUTCOME_VERSION_V2:
        lines.append("Note: Historical v2 calculation record; excluded from current cash_action_review_v1 performance evaluation.")

    return "\n".join(lines)
