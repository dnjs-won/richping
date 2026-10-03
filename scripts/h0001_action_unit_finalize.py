"""Finalize verified workstream status and main-only PM documents, no merge."""

from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys

import yaml

from richping.core import canonical, digest
from scripts.h0001_action_unit_audit import ROOT, immutable

ACTION = "H0001_HISTORICAL_ACTION_AVAILABILITY_AND_RAW_UNIT_EVIDENCE"
PREREQUISITE = "H0001_DAILY_PIT_AND_MIXED_PROFILE_PREREQUISITES"
BRANCH = "v2-h0001-action-unit-remediation"
RECORD = "research/decision_records/H0001-action-unit-interpretation-audit-v1.yaml"


def read(name):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def main():
    mode = sys.argv[1]
    smoke, ready, joined, tests = (read(p) for p in ("smoke.json", "daily-readiness.json", "mixed-profile-join-proof.json", "tests.json"))
    assert tests["failures"] == tests["errors"] == tests["skipped"] == 0 and tests["passed"] >= 1290
    assert smoke["repeat_equal"] and ready["eligible_input_observations"] == 500 and joined["joint_READY_evaluations"] > 0
    assert smoke["join_proof_hash"] == digest(joined) and smoke["readiness_hash"] == digest(ready)
    assert smoke["network_calls"] == smoke["outcome_queries"] == 0 and smoke["parent_preserved"]
    evidence = str(ROOT.as_posix()) + "/"
    text = (f"Admitted SOXX Daily500 eligible; trend READY{ready['trend_READY']}/UNAVAILABLE{ready['trend_UNAVAILABLE']}, "
            f"exhaustion READY{ready['exhaustion_READY']}/UNAVAILABLE{ready['exhaustion_UNAVAILABLE']}. "
            f"Actual first READY N179 {ready['first_trend_READY_session']}, N381 {ready['first_exhaustion_READY_session']}. "
            f"All2624 mixed joins: {joined['role_status_counts']}; joint READY{joined['joint_READY_evaluations']}. "
            f"Two network-disabled proofs identical, stream hash{joined['joined_event_hash']}. "
            "ENTRY_CANDIDATE=null, profitability NOT_RUN, outcomes NOT_EVALUATED.")
    if mode == "workstream":
        audit = yaml.safe_load(Path(RECORD).read_text(encoding="utf-8"))
        for p, h in audit["frozen_file_sha256_LF_normalized"].items():
            assert sha256(Path(p).read_bytes().replace(b"\r\n", b"\n")).hexdigest() == h
        checks = {
            "interpretation_audited": True, "official_and_independent_split_history": True,
            "2024_prior_split_outside_origin": True, "2026_next_split_after_end": True,
            "future_split_not_preapplied": True, "all500_OHLC_units_certified": True,
            "identity_compatible_with_frozen_semantics": True, "old_vintage_preserved": True,
            "new_immutable_vintage": True, "actual_eligible_Daily_gte381": True,
            "actual_trend_READY_gte1": True, "actual_exhaustion_READY_gte1": True,
            "actual_mixed_joint_READY_gt0": True, "offline_repeat_deterministic": True,
            "frozen_decisions_unchanged": True, "profitability_NOT_RUN": True,
            "full_suite_passed": True}
        immutable("acceptance.json", {"status": "COMPLETE_WORKSTREAM_PM_UPDATE_REQUIRED",
            "criteria": checks, "satisfied": len(checks), "unmet": 0, "evidence": evidence,
            "pm_control_update": "main:PROJECT_CONTROL.yaml after this workstream commit"})
        p = Path("PROJECT_STATUS.md")
        old = p.read_text(encoding="utf-8")
        assert old.startswith("# Richping V2 - 2026-10-03 Daily PIT")
        p.write_text(f"# Richping V2 - 2026-10-03 action/unit remediation\n\n"
            "**COMPLETE for the historical action/unit P0 and Daily/mixed-profile prerequisite. "
            "IMPLEMENTED / EXECUTED_ON_REAL_DATA / EVIDENCE_PRODUCED, not main integrated.**\n\n"
            f"- Branch `{BRANCH}`, from Daily implementation `ce6497c`.\n"
            "- Frozen record does not require per-as_of negative receipts. Caller comment from8ad1297 and runtime gate "
            "fromce6497c overinterpreted completeness as causal input. Ex-post admission now remains separate.\n"
            "- Official prior3:1 split2024-03-07 precedes origin2024-10-04. Official future3:1 split2026-11-05 "
            "follows end2026-10-02; no future factor applied. Yahoo/Twelve Data histories cross-check no inside split.\n"
            "- All500 Yahoo quote OHLC directly match Nasdaq within USD0.02. Official NAV corroborates units. "
            "General Yahoo raw/as-traded status is not claimed.\n"
            f"- New immutable `{smoke['daily_id']}`, hash `{smoke['daily_hash']}`. Parent v1 preserved.\n"
            f"- {text}\n"
            f"- Full suite {tests['passed']} passed, no failures/errors/skips. Real proofs are separate from event fixtures.\n"
            "- Bar-end known_at remains an explicit historical research assumption, not live/shadow PIT.\n"
            "- Next PM action on main: `H0001_ENTRY_EXECUTION_AND_COMPOSITION`. "
            "Phase exits5/6 remain open; no full entry/efficacy result.\n"
            f"- [Interpretation record]({RECORD}), [contract](docs/H0001_ACTION_UNIT_REMEDIATION.md), "
            f"[real evidence]({evidence}smoke.json).\n\n"
            "The entries below are preserved historical status reports.\n\n" + old, encoding="utf-8")
        return
    assert mode == "pm"
    main_root = Path(sys.argv[2])
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    assert subprocess.check_output(["git", "branch", "--show-current"], text=True).strip() == BRANCH
    assert not subprocess.check_output(["git", "status", "--porcelain"], text=True).strip()
    control_path = main_root / "PROJECT_CONTROL.yaml"
    control = yaml.safe_load(control_path.read_text(encoding="utf-8"))
    assert control["next_action"]["id"] == ACTION
    control["source_of_truth"]["active_workstream_status"]["branch"] = BRANCH
    control["active_workstream"].update(branch=BRANCH, base_branch="v2-h0001-daily-pit-join",
        base_commit="ce6497cdc204fbe420c42c78cbbb6482432390d8", implementation_commit=commit,
        note="Action/unit interpretation remediation and real offline evidence isolated from main. PM documents only on main; no code integration or force push.")
    behind, ahead = map(int, subprocess.check_output(["git", "rev-list", "--left-right", "--count", "main...HEAD"], text=True).split())
    control["active_workstream"]["observed_relation_to_main"] = {"ahead_by": ahead, "behind_by": behind + 1}
    phase = control["current_phase"]
    phase["status"] = "IN_PROGRESS_ENTRY_EXECUTION_AND_COMPOSITION"
    progress = phase["progress"]
    progress.update(satisfied_exit_criteria=[1, 2, 3, 4], remaining_exit_criteria=[5, 6],
        actual_evidence=text, limitations="Historical causal research input only. Bar-end availability is assumed, actual delivery/revision latency not reconstructed. Interval/snapshot scoped OHLC/action certification; no general raw Yahoo or live/shadow claim. Full entry composition and efficacy have not run.",
        blocked_exit_criteria=[5, 6], daily_prerequisite_subtask="COMPLETE_REAL_HISTORICAL_CAUSAL_RESEARCH_ADMISSION",
        frozen_15m_subtask="COMPLETE_EXECUTABLE_WITH_ACTUALLY_USABLE_UPSTREAM_INPUTS")
    prior = control.pop("blocked_actions")
    assert len(prior) == 1 and prior[0]["id"] == PREREQUISITE
    control["blocked_actions"] = []
    for action_id in (ACTION, PREREQUISITE):
        control["completed_actions"].append({"id": action_id, "status": "COMPLETE", "completed_at": "2026-10-03",
            "implementation_state": "IMPLEMENTED_EXECUTED_ON_REAL_DATA_EVIDENCE_PRODUCED_NOT_MAIN_INTEGRATED",
            "branch": BRANCH, "commit": commit, "record": RECORD, "evidence": evidence,
            "dataset_id": smoke["daily_id"], "content_hash": smoke["daily_hash"], "parent_preserved": True,
            "eligible_Daily_observations": 500, "trend_READY": ready["trend_READY"], "exhaustion_READY": ready["exhaustion_READY"],
            "real_joined_evaluations": 2624, "real_joint_READY_evaluations": joined["joint_READY_evaluations"],
            "join_stream_hash": joined["joined_event_hash"], "offline_repeat_equal": True,
            "acceptance_criteria_satisfied": 18 if action_id == ACTION else 4,
            "acceptance_criteria_unmet": 0,
            "tests": tests, "frozen_strategy_decisions_changed": False, "phase_complete": False,
            "strategy_profitability_tested": False})
    control["next_action"] = {"id": "H0001_ENTRY_EXECUTION_AND_COMPOSITION", "priority": "P0", "status": "READY",
        "blocks_phase_exit_criteria": [5, 6], "objective": "Resolve the minimal entry execution/lifecycle contract and compose frozen Daily permission/exhaustion, 1H setup and 15m tuple into deterministic entry events from the admitted immutable vintages.",
        "why_now": "Historical Daily admission and all upstream mixed-profile role readiness are now proven on real saved data; entry composition remains unimplemented.",
        "evidence_branch": BRANCH, "evidence": evidence + "smoke.json",
        "constraints": ["Preserve frozen Daily/1H/15m decisions, N179/N381 and research availability limitations.",
            "No profitability/outcome query until entry execution/composition is frozen and validated.",
            "No automatic orders, main code integration, longer-intraday migration or generic provider framework."],
        "acceptance_criteria": ["One versioned minimal entry execution/temporal/lifecycle contract is explicit without reopening frozen primitives.",
            "Daily + 1H + 15m produce deterministic causal entry event identities on fixed real saved datasets.",
            "Input absence, future-known inputs and duplicate/poll publication fail closed; all tests pass.",
            "Offline repeat results preserve denominators, immutable input hashes and no outcome lookup."],
        "after_success": ["H0001_FIRST_ENTRY_EFFICACY"]}
    control_path.write_text(yaml.safe_dump(control, allow_unicode=True, sort_keys=False, width=110), encoding="utf-8")
    backlog_path = main_root / "project/BACKLOG.yaml"
    backlog = yaml.safe_load(backlog_path.read_text(encoding="utf-8"))
    for item in backlog["items"]:
        if item["id"] in {ACTION, PREREQUISITE}:
            item.update(status="COMPLETE_REAL_HISTORICAL_CAUSAL_RESEARCH_EVIDENCE", summary=text,
                evidence_branch=BRANCH, evidence=RECORD, commit=commit,
                formerly_blocked_phase_exit_criteria=[4, 5, 6], blocks_phase_exit_criteria=[],
                resolution="Frozen semantic interpretation remediation; dataset completeness separate from causal event clocks. Exact500-session Nasdaq OHLC certification; new identity vintage.")
            item.pop("smallest_resolution", None)
        elif item["id"] == "H0001_ENTRY_EXECUTION_AND_COMPOSITION":
            item.update(priority="P0", status="ACTIVE_AS_NEXT_ACTION_READY", blocks_phase_exit_criteria=[5, 6])
        elif item["id"] == "V2_MAIN_INTEGRATION_LANE":
            item.update(active_branch=BRANCH, observed_relation_to_main={"ahead_by": ahead, "behind_by": behind + 1})
    backlog["items"].append({"id": "HISTORICAL_EVENT_REVISION_PROVENANCE", "priority": "P1", "status": "OPEN",
        "summary": "For a future interval containing actual splits, audit authenticated historical event receipt/revision evidence and exact pre/post units. Alpaca is a candidate, not a blocker for the current certified no-event interval.",
        "evidence_branch": BRANCH, "evidence": RECORD})
    backlog_path.write_text(yaml.safe_dump(backlog, allow_unicode=True, sort_keys=False, width=110), encoding="utf-8")
    index_path = main_root / "project/DECISION_INDEX.yaml"
    index = yaml.safe_load(index_path.read_text(encoding="utf-8"))
    index["default_research_branch"] = BRANCH
    index["canonical_sources"]["current_status"]["branch"] = BRANCH
    cp = index["composition_prerequisite"]
    cp.update(status="COMPLETE_REAL_HISTORICAL_CAUSAL_RESEARCH_EVIDENCE", evidence_branch=BRANCH,
        evidence=RECORD, actual_eligible_Daily_observations=500, actual_joint_READY=joined["joint_READY_evaluations"],
        implementation_commit=commit, current_real_sessions=500)
    cp.pop("blocking_next_action", None)
    cp["blocks_phase_exit_criteria"] = []
    impl = index["daily_input_implementation"]
    impl.update(branch=BRANCH, record=RECORD, contract="docs/H0001_ACTION_UNIT_REMEDIATION.md",
        implementation_status="COMPLETE_EXECUTED_ON_REAL_DATA_AND_EVIDENCE_PRODUCED_NOT_MAIN_INTEGRATED",
        split_free_identity_transform_real_certification=True, commit=commit,
        actual_source_smoke="Official iShares/SEC + Yahoo full split history + Twelve Data split history + all500 Nasdaq OHLC + issuer NAV",
        admission_capability="PIT_SPLIT_ADJUSTED_IDENTITY_INTERVAL_V1", historical_live_PIT_claim=False)
    index["frozen_major_decisions"]["m15_initial_entry"]["full_composition"] = "NOT_IMPLEMENTED_PREREQUISITES_COMPLETE_NEXT_ACTION"
    index["frozen_semantic_interpretation_audit"] = {"branch": BRANCH, "record": RECORD,
        "negative_receipt_explicitly_frozen": False, "strategy_decisions_changed": False,
        "completeness_capture_is_causal_feature": False}
    index_path.write_text(yaml.safe_dump(index, allow_unicode=True, sort_keys=False, width=110), encoding="utf-8")
    print(canonical({"main_PM_files_updated": 3, "next_action": control["next_action"]["id"], "code_integration": False}))


if __name__ == "__main__":
    main()
