"""H0001 Daily input commands attached to the existing research-v2-data CLI."""

import json
from pathlib import Path

from ...core import canonical, timestamp
from ..real_data import archive_capture
from ..store import ResearchStore


def add_actions(actions):
    daily_sync = actions.add_parser("daily-sync", help="Explicit long RTH Daily capture; no implicit PIT certification")
    daily_sync.add_argument("--symbol", default="SOXX")
    daily_sync.add_argument("--start")
    daily_sync.add_argument("--end", required=True)
    daily_sync.add_argument("--sessions", type=int, default=500)
    daily_sync.add_argument("--dataset-id", required=True)
    daily_import = actions.add_parser("daily-import")
    daily_import.add_argument("capture")
    daily_import.add_argument("--dataset-id", required=True)
    action_import = actions.add_parser("daily-action-import", help="New vintage from explicit audited split evidence")
    action_import.add_argument("dataset_id")
    action_import.add_argument("evidence")
    action_import.add_argument("--new-dataset-id", required=True)
    action_import.add_argument("--unit-audit", help="Audited raw price basis/known_at evidence JSON; never inferred")
    identity = actions.add_parser("daily-identity-import", help="New vintage from ex-post split-free interval and OHLC audits")
    identity.add_argument("dataset_id")
    identity.add_argument("action_audit")
    identity.add_argument("unit_audit")
    identity.add_argument("--new-dataset-id", required=True)
    for name in ("daily-inspect", "daily-proof", "mixed-proof"):
        inspect = actions.add_parser(name)
        inspect.add_argument("dataset_id")
        if name == "mixed-proof":
            inspect.add_argument("--intraday-id", required=True)


def run(args):
    root = Path(args.output_dir)
    from dataclasses import replace
    from ..contracts import JsonObject
    from ..daily_data import (daily_request, warmup_request, fetch_daily, normalize_daily,
                             load_daily, save_daily, daily_coverage, validate_actions)
    from .daily_proof import readiness_proof
    from .mixed_profile import mixed_proof

    if args.data_action in {"daily-sync", "daily-import"}:
        if args.data_action == "daily-sync":
            req = (daily_request(args.symbol, args.start, args.end) if args.start
                   else warmup_request(args.symbol, args.end, args.sessions))
            capture = fetch_daily(req)
        else:
            capture = json.loads(Path(args.capture).read_text(encoding="utf-8"))
        raw = archive_capture(capture, root)
        vintage = normalize_daily(capture, args.dataset_id)
        path = save_daily(vintage, root)
        result = {**daily_coverage(vintage), "raw_capture": str(raw), "vintage_path": str(path)}
    else:
        vintage = load_daily(args.dataset_id, root)
        if args.data_action == "daily-identity-import":
            from ..daily_identity import admit_identity_interval
            vintage = admit_identity_interval(vintage, args.new_dataset_id,
                json.loads(Path(args.action_audit).read_text(encoding="utf-8")),
                json.loads(Path(args.unit_audit).read_text(encoding="utf-8")))
            save_daily(vintage, root)
            result = daily_coverage(vintage)
        elif args.data_action == "daily-action-import":
            if args.new_dataset_id == vintage.dataset_id:
                raise ValueError("Action corrections require a new Daily vintage")
            actions = validate_actions(json.loads(Path(args.evidence).read_text(encoding="utf-8")))
            meta = vintage.manifest.unpack()
            meta["parent_dataset_id"], meta["parent_content_hash"] = vintage.dataset_id, vintage.content_hash
            meta["captured_at"] = max(timestamp(meta["captured_at"]), timestamp(actions.unpack()["captured_at"])).isoformat()
            if args.unit_audit:
                audit = json.loads(Path(args.unit_audit).read_text(encoding="utf-8"))
                if audit["raw_capture_hash"] != meta["raw_capture_hash"]:
                    raise ValueError("Unit audit must bind the exact raw capture")
                meta.update({"raw_unit_status": "VERIFIED_AS_TRADED", "raw_price_basis": audit["price_basis"],
                             "unit_audit_ref": audit["evidence_ref"], "unit_known_at": audit["known_at"]})
            bars = tuple(replace(b, dataset_id=args.new_dataset_id,
                         provenance=JsonObject.of({**b.provenance.unpack(), "raw_price_basis": meta["raw_price_basis"]}))
                         for b in vintage.bars)
            vintage = replace(vintage, dataset_id=args.new_dataset_id, bars=bars,
                              manifest=JsonObject.of(meta), actions=actions)
            save_daily(vintage, root)
            result = daily_coverage(vintage)
        elif args.data_action == "daily-inspect":
            result = daily_coverage(vintage)
        elif args.data_action == "daily-proof":
            result = readiness_proof(vintage)
        else:
            with ResearchStore(args.store, read_only=True) as store:
                intraday = store.load_dataset(args.intraday_id)
            result = mixed_proof(vintage, intraday)
    print(canonical(result))
    return 0
