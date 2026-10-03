"""Small isolated V2 ingestion CLI. Inspect/list never import the network client."""

import json
from pathlib import Path
import re

from ..core import canonical, digest
from .real_data import (archive_capture, coverage, fetch_capture, incremental_request,
                        new_vintage, normalize_capture, request, write_coverage, expected_slots)
from .store import ResearchStore


def add_parser(sub):
    command = sub.add_parser("research-v2-data", help="Explicit real 15m sync/import; offline list/inspect/proof")
    command.add_argument("--store", default="var/research/v2-real/market.sqlite")
    command.add_argument("--output-dir", default="var/research/v2-real")
    actions = command.add_subparsers(dest="data_action", required=True)
    sync = actions.add_parser("sync")
    sync.add_argument("--symbol", default="SOXX")
    sync.add_argument("--start")
    sync.add_argument("--end", required=True, help="Exclusive local date; completed days only")
    sync.add_argument("--parent", help="Immutable parent dataset for incremental refresh")
    sync.add_argument("--overlap-days", type=int, default=7)
    sync.add_argument("--dataset-id")
    imp = actions.add_parser("import", help="Offline import of archived provider capture")
    imp.add_argument("capture")
    imp.add_argument("--dataset-id")
    actions.add_parser("list")
    for name in ("inspect", "proof"):
        inspect = actions.add_parser(name)
        inspect.add_argument("dataset_id")
    return actions


def offline_proof(dataset):
    """Stream through existing completed aggregation and ReplayEvent contracts.

    Mechanics only: no strategy, returns, signals or frozen Daily input admission.
    Bounded memory instead of retaining quadratic full replay contexts/traces.
    """
    from collections import Counter
    from hashlib import sha256
    from itertools import groupby
    from .aggregation import CompletedAggregator
    from .contracts import ReplayEvent, payload
    from .market_data import availability_order, market_order

    if dataset.manifest.unpack()["coverage_status"] != "COMPLETE_GRID":
        raise ValueError("Real dataset UNKNOWN/UNAVAILABLE coverage; offline iteration refused")
    aggregator = CompletedAggregator(profile=dataset.session_profile)
    fingerprint = sha256()
    counts = Counter()
    run_id = digest({"purpose": "offline_aggregation_proof_v1", "dataset_hash": dataset.content_hash})
    events = 0
    for sequence, (known, members) in enumerate(groupby(
            sorted(dataset.bars, key=availability_order), key=lambda b: b.known_at)):
        base = tuple(members)
        completed = tuple(sorted((v for b in base for v in aggregator.accept(b, known)), key=market_order))
        event = ReplayEvent(run_id, sequence, known, base, completed)
        fingerprint.update(canonical(payload(event)).encode())
        counts.update(v.timeframe for v in completed)
        events += 1
    return {"dataset_id": dataset.dataset_id, "content_hash": dataset.content_hash,
            "run_id": run_id, "event_stream_hash": fingerprint.hexdigest(),
            "events": events, "completed_bars": dict(counts), "incomplete": aggregator.incomplete(),
            "network_calls": 0, "evidence": "REAL_SNAPSHOT_OFFLINE_MECHANICS_NOT_STRATEGY_OR_PIT"}


def _dataset_id(value, capture):
    value = value or "yahoo-" + capture["request"]["symbol"].lower() + "-15m-" + digest(capture)[:20]
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,120}", value):
        raise ValueError("Safe dataset label required")
    return value


def run(args):
    root = Path(args.output_dir)
    if args.data_action in {"list", "inspect", "proof"}:
        with ResearchStore(args.store, read_only=True) as store:
            if args.data_action == "list":
                result = store.list_datasets()
            else:
                dataset = store.load_dataset(args.dataset_id)  # revalidates content hash
                result = coverage(dataset) if args.data_action == "inspect" else offline_proof(dataset)
        print(canonical(result))
        return 0
    parent = None
    if args.data_action == "import":
        capture = json.loads(Path(args.capture).read_text(encoding="utf-8"))
    else:
        if args.parent:
            with ResearchStore(args.store, read_only=True) as store:
                parent = store.load_dataset(args.parent)
            if args.start or args.symbol != parent.manifest.unpack()["symbols"][0]:
                raise ValueError("Parent controls incremental symbol/start")
            req = incremental_request(parent, args.end, args.overlap_days)
        else:
            if not args.start:
                raise ValueError("Initial sync requires --start")
            req = request(args.symbol, args.start, args.end)
        capture = fetch_capture(req)
    raw_path = archive_capture(capture, root)
    dataset_id = _dataset_id(args.dataset_id, capture)
    try:
        incoming = normalize_capture(capture, dataset_id)
        dataset = new_vintage(parent, incoming, dataset_id) if parent else incoming
        with ResearchStore(args.store) as store:
            store.save_dataset(dataset)
        report = write_coverage(dataset, root)
    except Exception as exc:
        # Raw capture survives rejection. Report unsupported days even when the
        # unchanged extended contract refuses materialization.
        _, unsupported = expected_slots(capture["request"])
        from datetime import datetime, timezone
        from collections import Counter
        from .sessions import NY
        rows = capture.get("response", {}).get("chart", {}).get("result") or []
        times = rows[0].get("timestamp", []) if rows else []
        days = Counter(datetime.fromtimestamp(t, timezone.utc).astimezone(NY).date().isoformat()
                       for t in times if type(t) is int)
        for day in unsupported:
            day["observed_bars"] = days[day["session"]]
        failure = {"status": "REJECTED_NOT_REPLAYABLE", "dataset_id": dataset_id,
                   "raw_capture": str(raw_path), "raw_capture_hash": digest(capture),
                   "requested_range": capture["request"], "observed_rows": len(times),
                   "unsupported_sessions": unsupported, "error": str(exc)}
        path = root / (digest(failure) + ".failure.json")
        path.write_text(canonical(failure), encoding="utf-8")
        raise
    print(canonical({"store": str(Path(args.store).resolve()), "raw_capture": str(raw_path), **report}))
    return 0 if report["coverage_status"] == "COMPLETE_GRID" else 2
