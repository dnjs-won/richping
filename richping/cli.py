import argparse
from collections import Counter
from dataclasses import replace
from datetime import timedelta
import json
from pathlib import Path
import sys

from .core import Config, LEGACY_OUTCOME_VERSION, canonical, code_hash, cutoff_at, latest_session, next_sessions, timestamp, utcnow
from .coverage import coverage_report, stored_run_evidence
from .data import import_csv, synthetic_dataset, yahoo_dataset
from .engine import Engine
from .evaluation import metrics
from .operations import (
    AttemptJournal,
    artifact_root,
    atomic_write_json,
    atomic_write_text,
    build_operational_report,
    ensure_start_manifest,
    format_operational_report,
    publish_report,
    refresh_report,
)
from .maturity import format_maturity_report, maturity_followup
from .paper import (
    PaperPolicy,
    PaperStore,
    format_paper_report,
    forward_source_items,
    operational_replay_sources,
    paper_report,
    persist_paper_report,
    stored_paper_summary,
)
from .pipeline import format_report, scan, track
from .risk_contract import risk_cohort_id
from .store import Store
from .validation import validate


def emit(event, **values):
    print(canonical({"timestamp": utcnow(), "event": event, **values}), file=sys.stderr)


def write_report(report, path):
    # Backward-compatible helper used by research artifacts and tests.
    atomic_write_json(report, path)


def parser():
    p = argparse.ArgumentParser(description="Richping research/shadow recommendation engine")
    p.add_argument("--db", default=None, help="SQLite path (default var/richping.db; demo uses var/demo.db)")
    p.add_argument("--config", default="config.toml")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("demo", help="Deterministic synthetic recommendation -> outcome replay")
    sync = sub.add_parser("sync", help="Incrementally fetch completed daily Yahoo bars")
    sync.add_argument("--start", default=None)
    run = sub.add_parser("daily", help="Sync -> track old recommendations -> pre-open shadow scan")
    run.add_argument("--start", default=None)
    run.add_argument("--output-dir", default=None, help="Derived report/attempt root")
    imp = sub.add_parser("import-csv")
    imp.add_argument("bars")
    imp.add_argument("members")
    sc = sub.add_parser("scan")
    sc.add_argument("--session")
    sc.add_argument("--mode", choices=["research", "shadow"], default="shadow")
    sc.add_argument("--output-dir", default=None)
    ob = sub.add_parser("observe")
    ob.add_argument("--as-of")
    rep = sub.add_parser("report", help="Read latest derived operational report")
    rep.add_argument("--output-dir", default=None)
    rep.add_argument("--as-of", default=None, help="Refresh staleness at this aware timestamp")
    rep.add_argument("--write", action="store_true", help="Write a derived JSON/Markdown generation (DB remains read-only)")
    ev = sub.add_parser("evaluate")
    ev.add_argument("--as-of")
    va = sub.add_parser("validate")
    va.add_argument("--train", type=int, default=504)
    va.add_argument("--validation", type=int, default=63)
    va.add_argument("--oos", type=int, default=63)
    coverage = sub.add_parser("coverage", help="Read-only v3 research coverage diagnostics")
    coverage.add_argument("--start", help="First target session (default: after 60-session warmup)")
    coverage.add_argument("--end", help="Last target session (default: dataset end)")
    coverage.add_argument("--dataset-id", help="Immutable input vintage (default: latest stored)")
    coverage.add_argument("--output", default="var/coverage_report.json")
    maturity = sub.add_parser("maturity-followup", help="Verify frozen OOS and write a separate R1 maturity/paper view")
    maturity.add_argument("--source-db", default="var/m2-1b-fresh.db")
    maturity.add_argument("--validation", default="var/validation-m2-1b.json")
    maturity.add_argument("--failure-analysis", default="var/failure-analysis-m2-1b.json")
    maturity.add_argument("--dataset-id")
    maturity.add_argument("--as-of")
    maturity.add_argument("--paper-db", default="var/research/r1/m2-1b/r1.db")
    maturity.add_argument("--output-dir", default="var/research/r1/m2-1b")
    paper_init = sub.add_parser("paper-init", help="Register a future-only virtual portfolio")
    paper_init.add_argument("--source-db", default="var/richping.db")
    paper_init.add_argument("--paper-db", default="var/paper/forward/paper.db")
    paper_init.add_argument("--dataset-id")
    paper_init.add_argument("--start-session")
    paper_advance = sub.add_parser("paper-advance", help="Advance a registered future paper portfolio")
    paper_advance.add_argument("--source-db", default="var/richping.db")
    paper_advance.add_argument("--paper-db", default="var/paper/forward/paper.db")
    paper_advance.add_argument("--dataset-id")
    paper_advance.add_argument("--as-of")
    paper_advance.add_argument("--output-dir", default="var/paper/forward")
    paper_report_cmd = sub.add_parser("paper-report", help="Read a paper ledger without changing it")
    paper_report_cmd.add_argument("--paper-db", default="var/paper/forward/paper.db")
    paper_report_cmd.add_argument("--manifest-id")
    sub.add_parser("recover-runs", help="Mark interrupted RUNNING jobs failed; only run when no job is active")
    return p


def _same_path(left, right):
    return Path(left).resolve() == Path(right).resolve()


def _run_r1_command(args, config):
    if args.command == "maturity-followup":
        if _same_path(args.source_db, args.paper_db):
            raise ValueError("R1 output database must differ from the immutable source database")
        maturity = maturity_followup(args.source_db, args.validation, args.failure_analysis,
                                     args.dataset_id, args.as_of)
        with Store(args.source_db, read_only=True) as source:
            dataset = source.load_dataset(maturity["source"]["dataset_id"])
        period = maturity["evaluation_period"]
        policy = PaperPolicy()
        fixed_payload = {"mode": "RESEARCH_FIXED_REPLAY", "dataset_id": dataset.id,
                         "start_session": period["start"], "end_session": period["paper_end"],
                         "source": maturity["source"], "policy": policy.payload(),
                         "evidence": "consumed research OOS"}
        input_hashes = {"validation": maturity["source"]["validation_sha256"],
                        "failure_analysis": maturity["source"]["failure_analysis_sha256"]}
        with PaperStore(args.paper_db) as paper_store:
            fixed_manifest = paper_store.save_manifest("RESEARCH_FIXED_REPLAY", fixed_payload, input_hashes)
            paper_store.save_source_items(fixed_manifest, maturity["source_items"])
            paper_store.save_followup(fixed_manifest, maturity)
            fixed = paper_report(dataset, maturity["source_items"], period["start"], period["paper_end"],
                                 mode="RESEARCH_FIXED_REPLAY", policy=policy,
                                 as_of=maturity["followup"]["as_of"], manifest_id=fixed_manifest)
            persist_paper_report(paper_store, fixed_manifest, fixed)

        operational_items, operational_diagnostic = operational_replay_sources(
            args.paper_db, dataset, config, period["start"], period["last_allowed_signal_session"]
        )
        operational_payload = {"mode": "RESEARCH_OPERATIONAL_REPLAY", "dataset_id": dataset.id,
                               "start_session": period["start"], "end_session": period["paper_end"],
                               "signal_end_session": period["last_allowed_signal_session"],
                               "policy": policy.payload(), "cold_start": "NORMAL with empty eligible history",
                               "model_id": config.model_id, "model_code_hash": code_hash(),
                               "risk_cohort_id": risk_cohort_id(config), "config": config.payload(),
                               "calibration": "existing rolling past-only Engine.calibration",
                               "risk": "existing scan/track/risk_decision in isolated R1 database"}
        with PaperStore(args.paper_db) as paper_store:
            operational_manifest = paper_store.save_manifest(
                "RESEARCH_OPERATIONAL_REPLAY", operational_payload,
                {**input_hashes, "dataset_id": dataset.id}
            )
            paper_store.save_source_items(operational_manifest, operational_items)
            operational = paper_report(dataset, operational_items, period["start"], period["paper_end"],
                                       mode="RESEARCH_OPERATIONAL_REPLAY", policy=policy,
                                       as_of=maturity["followup"]["as_of"], manifest_id=operational_manifest)
            persist_paper_report(paper_store, operational_manifest, operational)
        output = {"schema": "richping_r1_delivery_v1", "maturity": maturity,
                  "fixed_paper": fixed, "operational_paper": operational,
                  "operational_diagnostic": operational_diagnostic,
                  "separation": {"fixed_uses_frozen_selection": True,
                                 "operational_uses_rolling_scan_and_risk": True,
                                 "neither_is_fresh_forward_or_actual_fill": True}}
        root = Path(args.output_dir)
        atomic_write_json(output, root / "r1-report.json")
        text = (format_maturity_report(maturity) + "\n" + format_paper_report(fixed) + "\n" +
                "# Operational-policy replay\n\n" + format_paper_report(operational))
        atomic_write_text(text, root / "r1-report.md")
        print(text, end="")
        return 0

    if args.command == "paper-init":
        if _same_path(args.source_db, args.paper_db):
            raise ValueError("Paper database must differ from the operational source database")
        created_at = utcnow()
        with Store(args.source_db, read_only=True) as source:
            dataset = source.load_dataset(args.dataset_id)
        earliest = next_sessions(dataset.end, 1)[0]
        start = args.start_session or earliest
        if start < earliest:
            raise ValueError("FORWARD_PAPER cannot register a backdated entry period")
        payload = {"mode": "FORWARD_PAPER", "source_db": str(args.source_db),
                   "dataset_at_registration": dataset.id, "registered_at": created_at,
                   "start_session": start, "policy": PaperPolicy().payload(),
                   "paper_code_hash": code_hash(),
                   "paper_admission_block_is_not_operational_risk_state": True}
        with PaperStore(args.paper_db) as paper_store:
            manifest_id = paper_store.save_manifest("FORWARD_PAPER", payload,
                                                    {"dataset_id": dataset.id}, created_at=created_at)
        print(json.dumps({"manifest_id": manifest_id, "paper_db": args.paper_db,
                          "start_session": start, "registered_at": created_at,
                          "status": "WAITING_FOR_FUTURE_SHADOW_SNAPSHOTS"}, indent=2))
        return 0

    if args.command == "paper-advance":
        if _same_path(args.source_db, args.paper_db):
            raise ValueError("Paper database must differ from the operational source database")
        as_of = args.as_of or utcnow()
        with PaperStore(args.paper_db) as paper_store:
            manifest = paper_store.manifest()
        if manifest["kind"] != "FORWARD_PAPER":
            raise ValueError("paper-advance requires a FORWARD_PAPER manifest")
        with Store(args.source_db, read_only=True) as source:
            dataset = source.load_dataset(args.dataset_id)
        target = latest_session(as_of)
        end = min(target, dataset.end)
        start = manifest["payload"]["start_session"]
        if end < start:
            print(json.dumps({"status": "WAITING_FOR_START_SESSION", "start_session": start,
                              "latest_available_session": end}, indent=2))
            return 0
        items = forward_source_items(args.source_db, manifest, dataset, as_of)
        with PaperStore(args.paper_db) as paper_store:
            paper_store.save_source_items(manifest["id"], items)
            all_items = paper_store.source_items(manifest["id"])
            result = paper_report(dataset, all_items, start, end, mode="FORWARD_PAPER",
                                  policy=PaperPolicy(), as_of=as_of, manifest_id=manifest["id"])
            persist_paper_report(paper_store, manifest["id"], result)
        root = Path(args.output_dir)
        atomic_write_json(result, root / "paper-report.json")
        atomic_write_text(format_paper_report(result), root / "paper-report.md")
        print(format_paper_report(result), end="")
        return 0

    if args.command == "paper-report":
        with PaperStore(args.paper_db, read_only=True) as paper_store:
            result = stored_paper_summary(paper_store, args.manifest_id)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    return None


def main(argv=None):
    args = parser().parse_args(argv)
    database = args.db or ("var/demo.db" if args.command == "demo" else "var/richping.db")
    attempt = None
    output_root = None
    config = None
    if args.command == "daily":
        output_root = artifact_root(database, "daily", args.output_dir)
        role = "operations" if Path(database).resolve() == Path("var/richping.db").resolve() else "research"
        try:
            attempt = AttemptJournal(output_root, "daily", database, role)
        except Exception as exc:
            emit("job_failed", command=args.command, error_type=type(exc).__name__, error=str(exc))
            return 1
    try:
        config = Config.load(args.config)
        if args.command in {"maturity-followup", "paper-init", "paper-advance", "paper-report"}:
            return _run_r1_command(args, config)
        with Store(database, read_only=args.command in {"coverage", "report"}) as store:
            if args.command == "demo":
                symbols = ("ALFA", "BETA", "GAMA", "DELT")
                config = replace(config, tickers=symbols)
                dataset = synthetic_dataset(symbols=symbols)
                store.save_dataset(dataset)
                engine = Engine(dataset, config)
                reports = []
                for i, session in enumerate(dataset.sessions[-90:-20]):
                    report = scan(store, dataset, config, session, engine=engine)
                    reports.append(report)
                    if i % 20 == 0:
                        emit("demo_progress", completed=i + 1, total=70)
                counts, rows = track(store, dataset, cutoff_at(dataset.end).isoformat(), config.model_id, "research")
                report = reports[-1]
                # Latest report is immutable; post-demo outcomes are a separate artifact.
                summary = {"quality": "SYNTHETIC", "runs": len(reports),
                    "decisions": dict(Counter(r["decision"] for r in reports)), "outcomes": counts,
                    "performance": metrics(rows), "sample_outcomes": rows[-5:]}
                write_report(report, "var/demo-report.json")
                write_report(summary, "var/demo-outcomes.json")
                print(format_report(report))
                print("\nSYNTHETIC replay summary: " + canonical(summary))
            elif args.command == "import-csv":
                dataset = import_csv(args.bars, args.members)
                print(store.save_dataset(dataset))
            elif args.command in {"sync", "daily"}:
                end = latest_session()
                if attempt:
                    attempt.stage("COLLECTING", target_session=end)
                start = args.start or (timestamp(end + "T00:00:00+00:00") - timedelta(days=1460)).date().isoformat()
                try:
                    previous = store.load_dataset()
                except ValueError:
                    previous = None
                dataset = yahoo_dataset(config.tickers, start, end, previous)
                store.save_dataset(dataset)
                if attempt:
                    attempt.stage("COLLECTED", dataset_id=dataset.id)
                emit("data_synced", dataset=dataset.id, bars=len(dataset.bars), end=end)
                if args.command == "daily":
                    manifest = ensure_start_manifest(output_root, store, config)
                    duplicate = store.db.execute(
                        "SELECT 1 FROM runs WHERE model_id=? AND mode='shadow' AND session=? AND status='SUCCEEDED'",
                        (config.model_id, end),
                    ).fetchone() is not None
                    attempt.stage("TRACKING")
                    counts, _ = track(store, dataset, utcnow())
                    attempt.stage("SCANNING")
                    report = scan(store, dataset, config, end, "shadow")
                    attempt.finish("SUCCEEDED", target_session=end, run_id=report["run_id"],
                                   dataset_id=dataset.id, decision=report["decision"])
                    derived = build_operational_report(
                        store, config, report, attempt.record, output_root, dataset=dataset,
                        manifest=manifest, duplicate=duplicate,
                    )
                    paths = publish_report(derived, output_root)
                    print(format_operational_report(derived), end="")
                    emit("daily_complete", outcomes=counts, decision=report["decision"])
                    emit("daily_artifacts", **paths)
            elif args.command == "report":
                root = artifact_root(database, "daily", args.output_dir)
                latest = root / "latest.json"
                if latest.exists():
                    derived = json.loads(latest.read_text(encoding="utf-8"))
                    derived = refresh_report(derived, args.as_of)
                else:
                    report = store.latest_report(mode="shadow")
                    derived = build_operational_report(store, config, report, root=root, now=args.as_of)
                if args.write:
                    publish_report(derived, root)
                print(format_operational_report(derived), end="")
            elif args.command == "recover-runs":
                with store.db:
                    changed = store.db.execute("UPDATE runs SET status='FAILED',error='operator_recovered_interrupted_run' WHERE status='RUNNING'").rowcount
                print(f"Recovered {changed} interrupted runs")
            else:
                dataset = store.load_dataset(args.dataset_id if args.command == "coverage" else None)
                if dataset.metadata["quality"] == "synthetic":
                    config = replace(config, tickers=tuple(m["ticker"] for m in dataset.members))
                if args.command == "coverage":
                    if Path(args.output).resolve() == Path(database).resolve():
                        raise ValueError("Coverage output must not overwrite the source database")
                    result = coverage_report(dataset, config, args.start, args.end)
                    result["operational_evidence"] = stored_run_evidence(store)
                    write_report(result, args.output)
                    print(json.dumps({"output": args.output, "dataset_id": dataset.id,
                                      "period": result["period"], "trading_days": result["trading_days"],
                                      "signal_blocks": result["signal_blocks"]}, indent=2))
                elif args.command == "scan":
                    report = scan(store, dataset, config, args.session or latest_session(), args.mode)
                    root = artifact_root(database, "scan", args.output_dir)
                    stem = f"{report['session']}-{report['run_id']}"
                    atomic_write_json(report, root / "reports" / f"{stem}.json")
                    atomic_write_text(format_report(report) + "\n", root / "reports" / f"{stem}.txt")
                    print(format_report(report))
                elif args.command in {"observe", "evaluate"}:
                    as_of = args.as_of or utcnow()
                    counts, rows = track(store, dataset, as_of)
                    all_groups = set((r["model_id"], r["mode"]) for r in rows)
                    by_group_eval = counts.get("evaluation", {}).get("by_group", {})
                    for g in by_group_eval.values():
                        all_groups.add((g["model_id"], g["mode"]))
                    groups = sorted(all_groups)
                    summaries = []
                    for model, mode in groups:
                        group = [r for r in rows if (r["model_id"], r["mode"]) == (model, mode)]
                        grp_eval = by_group_eval.get(f"{model}:{mode}", {})
                        versions = sorted(
                            set(r.get("outcome_version", LEGACY_OUTCOME_VERSION) for r in group)
                            | set(grp_eval.get("by_version", {}).keys())
                        )
                        by_version = {}
                        for ver in versions:
                            v_group = [r for r in group if r.get("outcome_version", LEGACY_OUTCOME_VERSION) == ver]
                            by_version[ver] = {
                                "samples": len(v_group),
                                "performance": metrics(v_group),
                                "by_regime": {regime: metrics([r for r in v_group if r["regime"] == regime])
                                              for regime in sorted({r["regime"] for r in v_group})},
                                "evaluation": {
                                    "eligible": len(v_group),
                                    "excluded": grp_eval.get("by_version", {}).get(ver, 0),
                                },
                            }
                        summaries.append({"model": model, "mode": mode,
                            "outcome_versions": versions,
                            "by_version": by_version,
                            "performance": metrics(group),
                            "evaluation": grp_eval,
                            "by_regime": {regime: metrics([r for r in group if r["regime"] == regime])
                                for regime in sorted({r["regime"] for r in group})}})
                    result = {"quality": dataset.metadata["quality"], "outcomes": counts, "by_model_mode": summaries}
                    write_report(result, "var/evaluation.json")
                    print(json.dumps(result, indent=2))
                elif args.command == "validate":
                    result = validate(store, dataset, config, args.train, args.validation, args.oos)
                    write_report(result, "var/validation.json")
                    print(json.dumps({"trial": result["trial"], "folds": len(result["folds"]),
                                      "oos": result["oos"], "promotion": result["promotion"]}, indent=2))
        return 0
    except Exception as exc:
        if attempt is not None:
            try:
                attempt.finish("FAILED", error=f"{type(exc).__name__}: {exc}")
                if config is not None and Path(database).exists():
                    with Store(database, read_only=True) as report_store:
                        derived = build_operational_report(
                            report_store, config, attempt=attempt.record, root=output_root,
                        )
                        publish_report(derived, output_root)
            except Exception as report_exc:
                emit("failure_report_failed", command=args.command,
                     error_type=type(report_exc).__name__, error=str(report_exc))
        emit("job_failed", command=args.command, error_type=type(exc).__name__, error=str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
