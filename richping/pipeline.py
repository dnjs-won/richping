import json

from .core import canonical, code_hash, cutoff_at, digest, next_sessions, open_at, timestamp, utcnow
from .engine import Engine, observe
from .evaluation import metrics, risk_decision


def track(store, dataset, as_of, model_id=None, mode=None):
    """Retry safe; immutable outcome vintages, pending observations aren't finalized."""
    counts = {"COMPLETE": 0, "PENDING": 0, "UNRESOLVED": 0}
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
            for horizon in (1, 3, 5, 10, 20):
                result = observe(snap, dataset, horizon, as_of, rec["mode"])
                counts[result["status"]] += 1
                if result["status"] != "PENDING":
                    store.db.execute("INSERT OR IGNORE INTO outcomes VALUES(?,?,?,?,?)",
                        (rec["id"], horizon, dataset.id, result["status"], canonical(result)))
                if horizon == snap["holding_period"] and result["status"] == "COMPLETE":
                    rows.append({**result, "session": snap["session"], "ticker": snap["ticker"],
                                 "regime": snap["regime"], "recommendation_id": rec["id"],
                                 "model_id": rec["model_id"], "mode": rec["mode"]})
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
        if counts["UNRESOLVED"] and state != "PAUSED":
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
            "decision": "TRADE CANDIDATES AVAILABLE" if picks else "NO TRADE",
            "reason": "qualified_candidates" if picks else (reason if state == "PAUSED" else "insufficient_evidence_or_edge"),
            "recommendations": picks, "excluded": rejected, "universe_size": len(config.tickers),
            "outcomes": counts, "recent_30": metrics(recent),
            "limitations": ["research/shadow only; no validated alpha or order execution",
                            "current-list/revised historical calibration is not point-in-time validated",
                            "corporate-action and missing outcome windows are unresolved"]}
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
    lines = [f"{report['session']} DAILY RECOMMENDATION", f"Data: {report['quality'].upper()} / {report['mode']}",
             f"Market: {report['regime']}", f"System: {report['state']} ({report['state_reason']})",
             f"Model: {report['model']}", "", report["decision"]]
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
    m = report["recent_30"]
    lines += ["", f"Recent completed recommendations: {m['samples']} | Expectancy {pct(m['expectancy'])}",
              f"Outcome horizons: {report['outcomes']}",
              "Confidence = historical win frequency. References are not fills.",
              "Research/shadow only. Synthetic results are not investment evidence."]
    return "\n".join(lines)
