import argparse
from collections import Counter
from dataclasses import replace
from datetime import timedelta
import json
from pathlib import Path
import sys

from .core import Config, LEGACY_OUTCOME_VERSION, canonical, cutoff_at, latest_session, timestamp, utcnow
from .data import import_csv, synthetic_dataset, yahoo_dataset
from .engine import Engine
from .evaluation import metrics
from .pipeline import format_report, scan, track
from .store import Store
from .validation import validate


def emit(event, **values):
    print(canonical({"timestamp": utcnow(), "event": event, **values}), file=sys.stderr)


def write_report(report, path):
    # Runtime artifact generation; atomic replace prevents half-written reports.
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    temporary.replace(path)


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
    imp = sub.add_parser("import-csv")
    imp.add_argument("bars")
    imp.add_argument("members")
    sc = sub.add_parser("scan")
    sc.add_argument("--session")
    sc.add_argument("--mode", choices=["research", "shadow"], default="shadow")
    ob = sub.add_parser("observe")
    ob.add_argument("--as-of")
    sub.add_parser("report")
    ev = sub.add_parser("evaluate")
    ev.add_argument("--as-of")
    va = sub.add_parser("validate")
    va.add_argument("--train", type=int, default=504)
    va.add_argument("--validation", type=int, default=63)
    va.add_argument("--oos", type=int, default=63)
    sub.add_parser("recover-runs", help="Mark interrupted RUNNING jobs failed; only run when no job is active")
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    database = args.db or ("var/demo.db" if args.command == "demo" else "var/richping.db")
    try:
        config = Config.load(args.config)
        with Store(database) as store:
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
                start = args.start or (timestamp(end + "T00:00:00+00:00") - timedelta(days=1460)).date().isoformat()
                try:
                    previous = store.load_dataset()
                except ValueError:
                    previous = None
                dataset = yahoo_dataset(config.tickers, start, end, previous)
                store.save_dataset(dataset)
                emit("data_synced", dataset=dataset.id, bars=len(dataset.bars), end=end)
                if args.command == "daily":
                    counts, _ = track(store, dataset, utcnow())
                    report = scan(store, dataset, config, end, "shadow")
                    write_report(report, "var/daily-report.json")
                    print(format_report(report))
                    emit("daily_complete", outcomes=counts, decision=report["decision"])
            elif args.command == "report":
                print(format_report(store.latest_report()))
            elif args.command == "recover-runs":
                with store.db:
                    changed = store.db.execute("UPDATE runs SET status='FAILED',error='operator_recovered_interrupted_run' WHERE status='RUNNING'").rowcount
                print(f"Recovered {changed} interrupted runs")
            else:
                dataset = store.load_dataset()
                if dataset.metadata["quality"] == "synthetic":
                    config = replace(config, tickers=tuple(m["ticker"] for m in dataset.members))
                if args.command == "scan":
                    report = scan(store, dataset, config, args.session or latest_session(), args.mode)
                    write_report(report, "var/daily-report.json")
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
        emit("job_failed", command=args.command, error_type=type(exc).__name__, error=str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
