"""Persist ex-ante minimal composition; does not load any market datasets."""
from hashlib import sha256
from pathlib import Path
import yaml

from richping.core import canonical, digest
from richping.research_v2.strategy.entry_composition import contract, contract_hash, specification_root
from richping.research_v2.strategy.h0001_spec import H0001Specification
from richping.research_v2.strategy.specification import C1, PERFORMANCE, OPTIONAL

ROOT = Path("research/data_evidence/h0001-entry-composition-20261003")
RECORD = Path("research/decision_records/H0001-entry-composition-freeze-v1.yaml")
SPEC = Path("research/strategy_specs/H0001-r03-draft.yaml")


def immutable(path, value):
    path = Path(path)
    text = canonical(value)
    if path.exists():
        if path.read_text(encoding="utf-8") != text:
            raise ValueError("immutable artifact collision: " + str(path))
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x", encoding="utf-8") as f:
            f.write(text)


def main():
    if RECORD.exists():
        return
    before = H0001Specification.load(SPEC)
    assert before.unpack()["specification_version"] == "h0001_r03_spec_v12"
    immutable(ROOT / "specification-v12.json", before.unpack())
    value = before.unpack()
    value["specification_version"] = "h0001_r03_spec_v13"
    value["updated_at"] = "2026-10-03T00:00:00+00:00"
    value["state_machine_parameters"]["transition_priority_and_resets"]["value"] = specification_root()
    after = H0001Specification.of(value)
    SPEC.write_text(yaml.safe_dump(after.unpack(), sort_keys=False, allow_unicode=True), encoding="utf-8")
    sources = ["daily-input", "daily-trend", "daily-trend-readiness-remediation", "daily-blocker",
               "1h-relative-setup", "15m-entry", "action-unit-interpretation-audit"]
    paths = [Path("research/decision_records") / ("H0001-" + n + ("-v1.yaml" if n.endswith("remediation") or n.endswith("audit") else "-freeze-v1.yaml")) for n in sources]
    paths += [Path("richping/research_v2/strategy") / (n + ".py") for n in ("daily_trend", "daily_exhaustion", "h1_setup", "entry_15m")]
    record = {"schema_version": "h0001_entry_composition_freeze_v1", "record_id": "H0001-ENTRY-COMPOSITION-FREEZE-v1",
        "status": "FROZEN_BEFORE_ACTUAL_CANDIDATE_REPLAY", "decision_date": "2026-10-03",
        "basis_commit": "1c661d85f4da869c34945da203f29143c2556428", "author": "AI_PM_under_explicit_user_delegation",
        "contract": contract(), "composer_contract_hash": contract_hash(),
        "source_LF_sha256": {str(p).replace("\\", "/"): sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest() for p in paths},
        "position_evidence": {"states": ["FLAT", "OPEN", "UNAVAILABLE"], "missing": "UNAVAILABLE",
            "mode": contract()["position_mode"], "version": contract()["position_version"],
            "meaning": "explicit fixed-dataset research admission; no actual portfolio claim or automatic OPEN; forbidden for execution/portfolio evaluation"},
        "episode_identity": {"version": contract()["episode_version"], "definition": "reuse frozen H1SetupEpisode.episode_id",
            "hash_inputs": ["symbol", "activation raw.hash", "activation as_of", "frozen lifetime hash"],
            "refresh": "same episode ID; never clears consumed", "new": "terminated episode then new completed extreme activation"},
        "H1_STATE_TRANSITIONS": {"overall": "PARTIALLY_RESOLVED", "initial_entry_candidate": "RESOLVED",
            **{n: "UNRESOLVED" for n in ("actual_position_open", "add", "exit", "reentry", "execution")}},
        "specification": {"old_version": before.unpack()["specification_version"], "old_hash": before.specification_hash,
            "new_version": value["specification_version"], "new_hash": after.specification_hash,
            "unresolved_paths": len(after.unresolved_fields),
            "unresolved_inventory": {c: list(after.blockers(c)) for c in (C1, PERFORMANCE, OPTIONAL)}},
        "fixed_inputs": {"daily": "soxx-yahoo-rth-daily-pit-20261003-v2", "intraday": "soxx-yahoo-15m-20261003-v1"},
        "explicit_non_claims": ["order", "fill", "position", "trade", "profitability", "full_C1", "live_PIT", "main_integration"],
        "outcomes_queried": False, "performance_information_used": "NONE", "evaluation_protocol": "UNRESOLVED_REQUIRED_BEFORE_OUTCOMES"}
    RECORD.write_text(yaml.safe_dump(record, sort_keys=False, allow_unicode=True), encoding="utf-8")
    immutable(ROOT / "composition-contract.json", {**contract(), "hash": contract_hash(), "freeze_record_hash": digest(record)})
    print(canonical(record["specification"]))


if __name__ == "__main__":
    main()
