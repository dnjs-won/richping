"""Revalidate archived admission evidence offline; never candidate/outcome replay."""
from contextlib import ExitStack
from datetime import datetime, timedelta
from hashlib import sha256
import json
from unittest.mock import patch

from richping.core import sessions
from richping.research_v2.sessions import NY
from scripts.h0001_alpaca_admission import ROOT, encode, grid, paginate, validate_bar
from scripts.h0001_long_history_audit import write_new


def forbidden(*args, **kwargs):
    raise AssertionError("Network and outcome access forbidden in offline admission")


def compare_units(raw, split):
    if [b["t"] for b in raw] != [b["t"] for b in split]:
        raise ValueError("Unit comparison needs identical observations")
    before, after, max_error, volume_ok = 0, 0, 0.0, True
    for r, s in zip(raw, split):
        trading_date = datetime.fromisoformat(r["t"].replace("Z", "+00:00")).astimezone(NY).date().isoformat()
        factor = 3 if trading_date < "2024-03-07" else 1
        for key in ("o", "h", "l", "c"):
            max_error = max(max_error, abs(r[key] / factor - s[key]))
        volume_ok &= s["v"] == r["v"] * factor
        if factor == 3: before += 1
        else: after += 1
    return {"before_split_rows": before, "after_split_rows": after,
            "max_split_price_rounding_error_USD": max_error,
            "volume_exact_new_shares_per_old_shares": volume_ok,
            "result": "PASS" if before and after and volume_ok and max_error <= 0.005000001 else "FAIL"}


def prove(root=ROOT):
    probes, evidence_hashes = [], {}
    for path in sorted(root.glob("probes-*.json")):
        body = path.read_bytes()
        if sha256(body).hexdigest() != path.stem.removeprefix("probes-"):
            raise ValueError("Probe manifest bytes changed")
        report = json.loads(body)
        for record in report["requests"]:
            if record["transport"] != "HTTP_RESPONSE": continue
            raw_path = root / "raw" / (record["sha256"] + ".json")
            raw_body = raw_path.read_bytes()
            if sha256(raw_body).hexdigest() != record["sha256"] or len(raw_body) != record["bytes"]:
                raise ValueError("Raw response hash/size mismatch")
            payload = json.loads(raw_body)
            if record["http_status"] == 200:
                if record["endpoint"].endswith("/bars"):
                    if record["params"]["feed"] != "sip" or payload["symbol"] != "SOXX":
                        raise ValueError("Feed/symbol provenance mismatch")
                    for bar in payload["bars"]: validate_bar(bar)
                if any(key in payload for key in ("error", "code", "message")):
                    raise ValueError("Error masquerading as market response")
        # Reconstruct every saved bar case from the exact original page chain.
        for identity, case in report["cases"].items():
            records = [r for r in report["requests"] if r["id"] == identity and r["endpoint"].endswith("/bars")]
            if not records: raise ValueError("Case has no request provenance")
            replay = iter(records)
            def fetch(params):
                try: record = next(replay)
                except StopIteration: raise ValueError("Pagination page omitted") from None
                if params != record["params"] or record["http_status"] != 200:
                    raise ValueError("Pagination request continuity mismatch")
                return json.loads((root / "raw" / (record["sha256"] + ".json")).read_bytes())
            restored = paginate(fetch, records[0]["params"])
            if restored != {k: case[k] for k in ("rows", "pages", "terminal_token")}:
                raise ValueError("Archived normalized case/page stream mismatch")
            if next(replay, None) is not None: raise ValueError("Pages after terminal token")
        probes.append(report)
        evidence_hashes[path.name] = sha256(body).hexdigest()
    primary = next(p for p in probes if "earliest" in p["cases"])
    supplement = next(p for p in probes if "2026-07" in p["cases"])
    depth = next(p for p in probes if "2026-Q2" in p["cases"])
    repeat = next(r for r in primary["requests"] if r["id"] == "summer-repeat")
    if json.loads((root / "raw" / (repeat["sha256"] + ".json")).read_bytes())["bars"] != primary["cases"]["summer-dst"]["rows"]:
        raise ValueError("Repeated live pagination capture mismatch")
    diagnostics = {}
    for name, start, end, source in [
        ("earliest", "2016-01-04", "2016-01-06", primary),
        ("old-2016", "2016-01-04", "2016-01-05", primary),
        ("winter-dst", "2025-03-07", "2025-03-08", primary),
        ("summer-dst", "2025-03-10", "2025-03-11", primary),
        ("early-close", "2025-11-28", "2025-11-29", primary),
        ("recent-complete", "2026-10-01", "2026-10-02", primary),
        *[(name, start, end, supplement) for name, start, end in supplement["predeclared_windows"]],
        ("2026-Q2", "2026-04-01", "2026-07-01", depth),
        ("2026-Q3-plus", "2026-07-01", "2026-10-03", depth)]:
        result = source["cases"][name]
        diagnostics[name] = {"query_start": start, "query_end_exclusive": end,
                             "pagination_pages": result["pages"], **grid(result["rows"], start, end)}
    large = [b for name in ("2026-Q2", "2026-Q3-plus") for b in depth["cases"][name]["rows"]]
    combined = grid(large, "2026-04-01", "2026-10-03")
    missing_days = {datetime.fromisoformat(t).astimezone(NY).date().isoformat() for t in combined["missing_slots"]}
    longest, current = [], []
    for day in sessions("2026-04-01", "2026-10-02"):
        if day in missing_days:
            current = []
        else:
            current.append(day)
            if len(current) > len(longest): longest = list(current)
    units = {timeframe: compare_units(supplement["cases"]["unit-full-" + timeframe + "-raw"]["rows"],
                                     supplement["cases"]["unit-full-" + timeframe + "-split"]["rows"])
             for timeframe in ("15Min", "1Day")}
    original_actions = primary["actions"]["corporate_actions"]
    repeated_actions = supplement["actions-small-pages"]["corporate_actions"]
    normalized = lambda groups: {k: sorted(v, key=lambda a: a["id"]) for k, v in groups.items()}
    actions_equal = normalized(original_actions) == normalized(repeated_actions)
    if not actions_equal or not primary["pagination_repeat_equal"] or any(v["result"] != "PASS" for v in units.values()):
        raise ValueError("Provider pagination/unit evidence failed")
    minute = supplement["cases"]["volume-1Min"]["rows"]
    m15 = supplement["cases"]["volume-15Min"]["rows"]
    daily = supplement["cases"]["volume-1Day"]["rows"]
    minute_bins = {}
    for b in minute:
        t = datetime.fromisoformat(b["t"].replace("Z", "+00:00"))
        key = t.replace(minute=(t.minute // 15) * 15, second=0, microsecond=0)
        minute_bins[key] = minute_bins.get(key, 0) + b["v"]
    intraday_volume_equal = all(minute_bins[datetime.fromisoformat(b["t"].replace("Z", "+00:00"))] == b["v"] for b in m15)
    trades = supplement["missing-slot-trades"]
    if trades["next_page_token"] is not None: raise ValueError("Incomplete trade probe")
    return {"schema": "alpaca_basic_h0001_admission_v1", "status": "BLOCKED", "provider": "alpaca", "feed": "sip",
            "scope": "LONG_HISTORY_FROZEN_FULL_PREFIX_DISCOVERY_ADMISSION",
            "user_selection": "Trading API Basic free; no upgrade or other provider payment authorized",
            "earliest_observed": primary["cases"]["earliest"]["rows"][0]["t"],
            "latest_observed": depth["cases"]["2026-Q3-plus"]["rows"][-1]["t"],
            "depth": "2016-01-04..2026-10-02 endpoints observed (~10 years9 months), NOT continuous full-history capture",
            "capabilities": {"historical_sip_access": "PASS", "15m_bars": "PASS", "pagination": "PASS",
                "interpretable_volume": "PASS_QUALIFIED_MINUTE_BAR_SHARE_VOLUME", "raw_split_price_volume": "PASS_SPOT_UNIT_TEST",
                "sufficient_multi_year_extended_completed_grid": "BLOCKED_ACTUAL_MISSING_OBSERVATIONS",
                "historical_action_known_at": "UNPROVEN_NOT_DERIVED_FROM_EX_PROCESS_RECORD_PAYABLE_DATES",
                "interval_specific_action_unit_admission": "NOT_COMPLETED_NO_INTERVAL_ADMITTED"},
            "grid": diagnostics, "fixed_2026_half_year": combined,
            "alternative_complete_observation_run": {"first": longest[0], "last": longest[-1], "sessions": len(longest),
                "status": "COVERAGE_METADATA_ONLY_NOT_SELECTED_OR_ADMITTED", "Daily_warmup_units_actions": "NOT_ADMITTED",
                "note": "A narrower fixed discovery origin/scope could be considered before signals; no silent gap trimming, reset or candidate-driven selection."},
            "volume": {"minute_sum": sum(b["v"] for b in minute), "15m_sum": sum(b["v"] for b in m15),
                "daily_reported": daily[0]["v"], "each_15m_equals_published_minute_volume_sum": intraday_volume_equal,
                "missing_1945_ET_slot_actual_trades": len(trades["trades"]),
                "all_missing_slot_trades_include_odd_lot_I": all("I" in b["c"] for b in trades["trades"]),
                "missing_slot_trade_shares": sum(b["s"] for b in trades["trades"]),
                "zero_volume_sample_bars": sum(b["v"] == 0 for p in probes for case in p["cases"].values() for b in case["rows"]),
                "meaning": "SIP condition-eligible bar share volume; missing price bars can have trades. Minute/15m and nativeDaily totals are different aggregation domains; no equality or every-print claim."},
            "units": units, "action_pagination_repeat_equal": actions_equal,
            "action_pages": supplement["actions-small-pages"]["pages"], "action_counts": {k: len(v) for k,v in original_actions.items()},
            "action_provenance": "Current snapshot supplies ex/process/record/payable dates and IDs, not historical announcement/ingest/revision known_at. No timestamp backdated. Actual-event transforms fail closed. This limitation alone need not block a separately certified no-event raw identity interval.",
            "Daily_intraday": "Both request raw USD share units; both pass3:1 price/inverse-volume comparison. NativeDaily price update conditions differ from intraday and volume includes extended trading. Exact new RTH/auction/interval certificate still required before H0001 join.",
            "blocker": "EXTENDED_SESSION_HISTORY_INCOMPLETE_FOR_FROZEN_COMPLETE_GRID_FULL_PREFIX; no synth fill/compression/reset permitted. Not authentication, SIP absence, Basic subscription restriction or uninterpretable volume.",
            "capture": {"dataset_created": False, "dataset_id": None, "content_hash": None,
                        "reason": "Admission BLOCKED; immutable API probe receipts are evidence, not an admitted market dataset."},
            "candidate_count": None, "candidate_replay": "NOT_RUN_ADMISSION_BLOCKED", "existing_candidates": 0,
            "original_ZERO_SIGNAL_preserved": True, "confirmation_contract_changed": False,
            "next_action": "LONG_HISTORY_EXTENDED_COVERAGE_SCOPE_DECISION",
            "smallest_options": ["Keep multi-year frozen full-grid target: probe a read-only feed with actual extended price observations; quote capability/cost before any purchase.",
                f"Authorize a narrower fixed complete recent interval as DISCOVERY, with a new Daily/action/unit audit; coverage metadata suggests{len(longest)} sessions but does not certify replay."],
            "payment_needed": "NOT_ESTABLISHED; paid Alpaca tier not shown to repair eligible-trade omissions",
            "strategy_semantics_changed": False, "outcome_queries": 0, "performance_calculations": 0,
            "profitability": "NOT_RUN", "network_probes_separate_from_offline_tests": True,
            "probe_manifest_hashes": evidence_hashes}


def main():
    with ExitStack() as guards:
        for target in ("socket.socket.connect", "socket.create_connection", "curl_cffi.requests.get", "urllib.request.urlopen"):
            guards.enter_context(patch(target, forbidden))
        first, second = prove(), prove()
        assert first == second
        write_new(ROOT / "admission.json", encode(first))
        write_new(ROOT / "offline-reload-proof.json", encode({"repeat_equal": True,
            "admission_sha256": sha256(encode(first)).hexdigest(), "network_disabled": True,
            "network_calls": 0, "outcome_reads": 0, "strategy_replay": "NOT_RUN",
            "raw_response_hashes_verified": True, "dataset_identity": None}))
        print(json.dumps({"status": first["status"], "alternative_complete_run": first["alternative_complete_observation_run"],
                          "units": first["units"], "volume": first["volume"]}), flush=True)


if __name__ == "__main__":
    main()
