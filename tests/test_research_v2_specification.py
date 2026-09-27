"""C0 contract tests only. Fixture resolutions are not H0001 decisions."""

import ast
from dataclasses import FrozenInstanceError
from hashlib import sha256
import json
from pathlib import Path
import subprocess

import pytest
import yaml

from richping.core import digest
from richping.research_v2.contracts import payload
from richping.research_v2.strategy.specification import (
    StrategySpecification, C1, PERFORMANCE, OPTIONAL, SECTIONS, UNRESOLVED,
)
from richping.research_v2.strategy.h0001_spec import (
    H0001Specification, REQUIRED, SOURCE_SHA256, load_h0001,
)

ROOT = Path(__file__).resolve().parents[1]
DRAFT = ROOT / "research/strategy_specs/H0001-r03-draft.yaml"
SOURCE = ROOT / "research/hypotheses/H0001-r03.yaml"
BASE = "887810629a46912bd7cd4dcfca2709b1b33d7f74"


def draft():
    return load_h0001(DRAFT, hypothesis_path=SOURCE)


def at(value, path):
    if not path:
        return value
    for key in path.split("."):
        value = value[key]
    return value


def resolve_fixture(spec, categories):
    """Only in-memory fake conventions to exercise gates; never persisted/run."""
    value = spec.unpack()
    for path, info in spec.unresolved_fields.items():
        if info["classification"] not in categories:
            continue
        record = at(value, path)
        record["value"] = {
            "text": "fixture-only observation, not chart evidence",
            "contract": {"name": "fixture_only", "version": "v1", "parameters": {}},
            "integer": 1, "number": 0, "boolean": False, "timeframe": "15m",
            "enum": record["choices"][0] if record["choices"] else None,
        }[record["kind"]]
    return value


def test_draft_inventory_and_no_plugin_or_profitability_export():
    spec = draft()
    assert spec.unpack()["status"] == "DRAFT"
    assert len(spec.unresolved_fields) == 107
    assert sum(len(spec.blockers(c)) for c in (C1, PERFORMANCE, OPTIONAL)) == 75
    for method in (spec.plugin_specification, spec.require_profitability_ready,
                   spec.require_historical_reproduction_ready):
        with pytest.raises(ValueError):
            method()
    value = spec.unpack()
    value["status"] = "FROZEN"
    with pytest.raises(ValueError, match="C1"):
        H0001Specification.of(value)


def test_signal_freeze_leaves_performance_and_optional_decisions_blocked():
    value = resolve_fixture(draft(), {C1})
    value["status"] = "FROZEN"
    frozen = H0001Specification.of(value)
    assert not frozen.blockers(C1)
    assert frozen.blockers(PERFORMANCE) and frozen.blockers(OPTIONAL)
    assert digest(payload(frozen.plugin_specification())) == frozen.specification_hash
    with pytest.raises(ValueError, match="Profitability"):
        frozen.require_profitability_ready()
    with pytest.raises(ValueError, match="chart parity"):
        frozen.require_historical_reproduction_ready()


def test_performance_readiness_and_parity_are_separate_from_optional_extensions():
    value = resolve_fixture(draft(), {C1, PERFORMANCE})
    value["status"] = "FROZEN"
    for parity in ("UNVERIFIED", "MISMATCH"):
        value["chart_parity"]["parity_status"]["value"] = parity
        with pytest.raises(ValueError, match="parity"):
            H0001Specification.of(value).require_profitability_ready()
    value["chart_parity"]["parity_status"]["value"] = "VERIFIED"
    ready = H0001Specification.of(value)
    ready.require_profitability_ready()
    assert ready.blockers(OPTIONAL)
    # This is structural gate coverage, not real verification of the chart.


def test_chart_claim_without_observed_conventions_fails():
    value = draft().unpack()
    value["chart_parity"]["parity_status"]["value"] = "VERIFIED"
    with pytest.raises(ValueError, match="observed"):
        H0001Specification.of(value)


def test_yaml_json_mapping_order_comments_and_timestamp_spelling_canonicalize():
    original = draft()
    value = original.unpack()
    value["created_at"] = "2026-09-27T09:00:00+09:00"
    value["updated_at"] = "2026-09-27T00:00:00Z"
    value["state_machine"]["states"].reverse()
    for decision in value["decisions"].values():
        decision["candidate_choices"].reverse()
        decision["source_refs"].reverse()
    for transition in value["state_machine"]["transitions"].values():
        transition["prerequisites"].reverse()
    value = dict(reversed(list(value.items())))
    loaded = H0001Specification.loads("# comment\n" + yaml.safe_dump(value, sort_keys=False))
    assert loaded.text == original.text
    assert H0001Specification.loads(json.dumps(value), format="json") == original
    assert draft().specification_hash == original.specification_hash


@pytest.mark.parametrize("path,value", [
    ("rule_parameters.setup_1h_downside_threshold.value", 0.17),
    ("hypothesis_revision", 4),
    ("feature_contracts.macd_feature_version.value", {"name": "macd", "version": "v2", "parameters": {}}),
    ("engine_capabilities.macd_feature_version.value", "future_macd_v2"),
    ("specification_version", "future_spec_v2"),
    ("updated_at", "2026-09-27T00:00:01Z"),
])
def test_every_semantic_or_provenance_change_changes_hash(path, value):
    spec = draft()
    body = spec.unpack()
    keys = path.split(".")
    at(body, ".".join(keys[:-1]))[keys[-1]] = value
    # Generic schema can describe another revision. H0001-r03 profile cannot.
    assert StrategySpecification.of(body).specification_hash != spec.specification_hash


def test_numeric_threshold_spellings_canonicalize():
    body = draft().unpack()
    body["rule_parameters"]["setup_1h_downside_threshold"]["value"] = 1
    a = H0001Specification.of(body)
    body["rule_parameters"]["setup_1h_downside_threshold"]["value"] = 1.0
    assert H0001Specification.of(body) == a


@pytest.mark.parametrize("section,field", list(REQUIRED))
def test_omitting_any_required_h0001_parameter_never_means_unresolved(section, field):
    value = draft().unpack()
    del value[section][field]
    with pytest.raises(ValueError):
        H0001Specification.of(value)


@pytest.mark.parametrize("field", ["status", "hypothesis_revision", "source", *SECTIONS, "state_machine"])
def test_required_generic_field_missing_fails_closed(field):
    value = draft().unpack()
    del value[field]
    with pytest.raises(ValueError):
        StrategySpecification.of(value)


@pytest.mark.parametrize("bad", [None, True, "0.1", {}, [], float("nan"), float("inf")])
def test_invalid_threshold_type_is_not_a_decision(bad):
    value = draft().unpack()
    value["rule_parameters"]["setup_1h_downside_threshold"]["value"] = bad
    with pytest.raises(ValueError):
        H0001Specification.of(value)


@pytest.mark.parametrize("section,field,bad", [
    ("timeframe_contracts", "base", "4H"),
    ("timeframe_contracts", "base", "1h"),
    ("rule_parameters", "setup_1h_relative_transform", "magic"),
    ("rule_parameters", "swing_detector", "future-pivot"),
    ("rule_parameters", "setup_1h_rolling_lookback", 0),
    ("rule_parameters", "setup_1h_rolling_lookback", 1.0),
    ("rule_parameters", "setup_1h_rolling_lookback", True),
    ("rule_parameters", "daily_long_permission", "narrative is not an executable contract"),
    ("state_machine_parameters", "max_adds", -1),
])
def test_invalid_enum_timeframe_or_contract_value(section, field, bad):
    value = draft().unpack()
    value[section][field]["value"] = bad
    with pytest.raises(ValueError):
        H0001Specification.of(value)


def test_percentile_units_checked_without_selecting_percentile_for_draft():
    value = draft().unpack()
    value["rule_parameters"]["setup_1h_relative_transform"]["value"] = "ROLLING_PERCENTILE"
    value["rule_parameters"]["setup_1h_downside_threshold"]["value"] = 10
    with pytest.raises(ValueError, match="Percentile"):
        H0001Specification.of(value)


@pytest.mark.parametrize("mutation", ["category", "type", "choice", "orphan", "status", "extra", "transition", "condition"])
def test_h0001_cannot_hide_unknown_by_reclassifying_or_changing_schema(mutation):
    value = draft().unpack()
    if mutation == "category":
        value["decisions"]["H1-DAILY-LONG"].update(classification=OPTIONAL, required_for_c1=False, required_for_profitability=False)
    elif mutation == "type":
        value["rule_parameters"]["setup_1h_downside_threshold"]["kind"] = "text"
    elif mutation == "choice":
        value["rule_parameters"]["swing_detector"]["choices"].append("MAGIC")
    elif mutation == "orphan":
        value["decisions"]["unused"] = value["decisions"]["H1-DAILY-LONG"]
    elif mutation == "status":
        value["status"] = "PROFITABLE"
    elif mutation == "extra":
        value["silent_default"] = True
    elif mutation == "transition":
        del value["state_machine"]["transitions"]["daily_permission"]
    else:
        value["state_machine"]["transitions"]["daily_permission"]["condition"]["decision_id"] = "H1-4H"
    with pytest.raises(ValueError):
        H0001Specification.of(value)


def test_nested_contract_unknowns_are_still_blockers():
    body = resolve_fixture(draft(), {C1})
    body["rule_parameters"]["daily_long_permission"]["value"]["parameters"]["threshold"] = {
        "kind": "number", "value": UNRESOLVED, "choices": [], "decision_id": "H1-DAILY-LONG"}
    d = H0001Specification.of(body)
    assert "H1-DAILY-LONG" in d.blockers(C1)
    body["status"] = "FROZEN"
    with pytest.raises(ValueError, match="C1"):
        H0001Specification.of(body)


def test_nested_unknown_cannot_claim_a_weaker_parent_requirement():
    body = resolve_fixture(draft(), {C1})
    body["rule_parameters"]["daily_long_permission"]["value"]["parameters"]["threshold"] = {
        "kind": "number", "value": UNRESOLVED, "choices": [], "decision_id": "H1-SIZING"}
    with pytest.raises(ValueError, match="downgrade"):
        H0001Specification.of(body)


def test_nested_immutability():
    s = draft()
    before = s.text
    detached = s.unpack()
    detached["rule_parameters"]["daily_long_permission"]["value"] = "changed"
    s.unresolved_fields.clear()
    with pytest.raises(FrozenInstanceError):
        s.text = "{}"
    assert s.text == before and s.unresolved_fields


@pytest.mark.parametrize("text", [
    "strategy_id: one\nstrategy_id: two\n",
    "value: &a [1]\nother: *a\n",
    "value: !!python/object/apply:os.system ['whoami']",
    "1: value\n", "value: .nan\n", "value: !!set {one: null}\n",
])
def test_unsafe_ambiguous_or_non_json_yaml_rejected(text):
    with pytest.raises(ValueError):
        StrategySpecification.loads(text)


def test_json_duplicate_and_nonstring_mapping_keys_rejected():
    with pytest.raises(ValueError, match="Duplicate"):
        StrategySpecification.loads('{"a":1,"a":2}', format="json")
    with pytest.raises(ValueError, match="String keys"):
        StrategySpecification.of({1: "one"})


def test_generic_modules_never_import_h0001_or_strategy_layer():
    root = ROOT / "richping/research_v2"
    for path in [*root.glob("*.py"), *(root / "features").glob("*.py"), root / "strategy/specification.py", root / "strategy/__init__.py"]:
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                statement = ast.unparse(node).lower()
                assert "h0001" not in statement
                if path.parent.name != "strategy":
                    assert "strategy" not in (node.module or "").split(".") if isinstance(node, ast.ImportFrom) else True


def test_hypothesis_original_and_v2_a_b_contracts_unchanged():
    original = subprocess.check_output(["git", "show", f"{BASE}:research/hypotheses/H0001-r03.yaml"], cwd=ROOT)
    assert sha256(original).hexdigest() == SOURCE_SHA256
    assert SOURCE.read_bytes().replace(b"\r\n", b"\n") == original
    assert not (SOURCE.parent / "H0001-r04.yaml").exists()
    protected = [* (ROOT / "richping/research_v2").glob("*.py"),
                 * (ROOT / "richping/research_v2/features").glob("*.py"),
                 *(ROOT / "tests" / name for name in ("test_research_v2.py", "test_research_v2_features.py", "test_research_v2_continuity.py"))]
    for path in protected:
        original = subprocess.check_output(["git", "show", f"{BASE}:{path.relative_to(ROOT).as_posix()}"], cwd=ROOT)
        assert path.read_bytes().replace(b"\r\n", b"\n") == original.replace(b"\r\n", b"\n")


def test_decision_matrix_contains_every_decision_and_resolvable_source_reference():
    body = draft().unpack()
    matrix = (ROOT / "docs/V2_C0_H0001_SPECIFICATION.md").read_text(encoding="utf-8")
    hypothesis = yaml.safe_load(SOURCE.read_text(encoding="utf-8"))
    import re
    for id, decision in body["decisions"].items():
        assert f"| {id} / " in matrix
        for ref in decision["source_refs"]:
            current = hypothesis
            for name, index in re.findall(r"([a-z_]+)|\[(\d+)\]", ref):
                current = current[name] if name else current[int(index)]
            assert current is not None or ref == "test.confirmatory_period"
