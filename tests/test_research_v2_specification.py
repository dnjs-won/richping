"""C0 contract tests only. Fixture resolutions are not H0001 decisions."""

import ast
from dataclasses import FrozenInstanceError, asdict
from hashlib import sha256
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import subprocess
import sys
import tomllib

import pytest
import yaml

from richping.core import digest
from richping.research_v2.contracts import payload
from richping.research_v2.strategy.specification import (
    StrategySpecification, C1, PERFORMANCE, OPTIONAL, SECTIONS, UNRESOLVED,
)
from richping.research_v2.strategy.h0001_spec import (
    H0001Specification, REQUIRED, SOURCE_SHA256, STATES, LIFECYCLE_RETURNS,
    load_h0001, validate_signal_lifecycle, ENGINE_BOUNDARIES,
)
from richping.research_v2.features.relative import NormalizeSpec, PercentileSpec, ZScoreSpec
from richping.research_v2.features.structure import FractalSpec
from richping.research_v2.features.volatility import ATRSpec
from richping.research_v2.strategy.capabilities import current_engine

ROOT = Path(__file__).resolve().parents[1]
DRAFT = ROOT / "research/strategy_specs/H0001-r03-draft.yaml"
SOURCE = ROOT / "research/hypotheses/H0001-r03.yaml"
BASE = "887810629a46912bd7cd4dcfca2709b1b33d7f74"


def draft():
    return load_h0001(DRAFT, hypothesis_path=SOURCE)


def input_freeze_draft():
    return H0001Specification.loads(subprocess.check_output([
        "git", "show", "f517374f66b75c84a0ea025ced91cacf866b2b8a:" + DRAFT.relative_to(ROOT).as_posix(),
    ], cwd=ROOT).decode("utf-8"))


def input_audit_draft():
    """Immutable v6 audit fixture; later semantic freeze has separate tests."""
    return H0001Specification.loads(subprocess.check_output([
        "git", "show", "382bd202ed394fbe5b2247af0752a4d29efaaa26:" + DRAFT.relative_to(ROOT).as_posix(),
    ], cwd=ROOT).decode("utf-8"))


def prior_decision_inventory(value):
    """Compare historical decisions, excluding the three later Daily input IDs."""
    decisions = {k: dict(v) for k, v in value["decisions"].items()
                 if k not in {"H1-DAILY-SESSION", "H1-DAILY-PRICE-BASIS", "H1-DAILY-FRESHNESS"}}
    for key in ("question", "current_hypothesis_statement", "available_v2_primitive"):
        decisions["H1-SESSION"].pop(key)
    return decisions


def prior_unresolved_fields(spec):
    return {p: info for p, info in spec.unresolved_fields.items()
            if info["decision_id"] not in {"H1-DAILY-SESSION", "H1-DAILY-PRICE-BASIS", "H1-DAILY-FRESHNESS"}}


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
    if C1 in categories:
        compatible_features_fixture(value)
    return value


def typed(value):
    kind = {str: "text", int: "integer", bool: "boolean", dict: "contract"}[type(value)]
    return {"kind": kind, "value": value, "choices": [], "decision_id": None}


def contract(identifier, parameters=None):
    name, version = identifier.rsplit("_", 1)
    return {"name": name, "version": version,
            "parameters": {k: typed(v) for k, v in (parameters or {}).items()}}


def feature_contract(spec, **extra):
    return contract(spec.version, {**asdict(spec), **extra})


def compatible_features_fixture(value, method="ROLLING_PERCENTILE"):
    """Synthetic admission fixture only: never a selection for the stored draft."""
    for key, record in current_engine().items():
        value["engine_capabilities"][key]["value"] = record
    value["chart_parity"]["engine_1h_boundary"]["value"] = ENGINE_BOUNDARIES["XNYS_RTH"]
    value["timeframe_contracts"]["base"]["value"] = "15m"
    value["timeframe_contracts"]["session_policy"]["value"] = "RTH"
    if "daily_session_policy" in value["timeframe_contracts"]:
        value["timeframe_contracts"]["daily_session_policy"]["value"] = "RTH_DAILY"
    value["rule_parameters"]["swing_detector"]["value"] = "FRACTAL"
    value["rule_parameters"]["swing_parameters"]["value"] = feature_contract(FractalSpec(1, 1))
    for key, identifier in {
        "macd_ema_seed": "first_observation_recursive_v1",
        "macd_signal_start": "first_macd_observation_v1",
        "macd_price_field": "close_v1",
        "macd_feature_version": "macd_first_observation_recursive_v1",
        "history_origin": "available_completed_history_prefix_v1",
    }.items():
        value["feature_contracts"][key]["value"] = contract(identifier)
    for prefix in ("setup_1h", "entry_15m", "exit_1h"):
        value["rule_parameters"][prefix + "_relative_transform"]["value"] = method
        convention = {
            "ROLLING_PERCENTILE": feature_contract(PercentileSpec(1, 1), field="macd_line"),
            "ROLLING_ZSCORE": feature_contract(ZScoreSpec(1, 1, ddof=0), field="macd_line"),
            "MACD_ATR": contract("macd_atr_normalization_v1", {
                "normalization": feature_contract(NormalizeSpec("macd_line", "atr")),
                "atr": feature_contract(ATRSpec(1, 1)),
            }),
        }[method]
        value["feature_contracts"][prefix + "_relative_conventions"]["value"] = convention


def test_draft_inventory_and_no_plugin_or_profitability_export():
    spec = draft()
    assert spec.unpack()["status"] == "DRAFT"
    assert len(spec.unresolved_fields) == 95
    assert sum(len(spec.blockers(c)) for c in (C1, PERFORMANCE, OPTIONAL)) == 68
    for method in (spec.require_c1_ready, spec.plugin_specification, spec.require_profitability_ready,
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
    frozen.require_c1_ready()
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
    for field in ("created_at", "updated_at"):
        value[field] = datetime.fromisoformat(value[field]).astimezone(
            timezone(timedelta(hours=9))).isoformat()
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
    body = resolve_fixture(input_freeze_draft(), {C1})
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


def test_hypothesis_original_and_existing_rth_tests_unchanged():
    original = subprocess.check_output(["git", "show", f"{BASE}:research/hypotheses/H0001-r03.yaml"], cwd=ROOT)
    assert sha256(original).hexdigest() == SOURCE_SHA256
    assert SOURCE.read_bytes().replace(b"\r\n", b"\n") == original
    assert not (SOURCE.parent / "H0001-r04.yaml").exists()
    protected = [*(ROOT / "richping/research_v2" / name for name in ("store.py", "clock.py", "dummy.py", "__init__.py")),
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


def frozen_fixture(*, performance=False):
    value = resolve_fixture(draft(), {C1, PERFORMANCE} if performance else {C1})
    value["status"] = "FROZEN"
    if performance:
        value["chart_parity"]["parity_status"]["value"] = "VERIFIED"
    return value


@pytest.mark.parametrize("method", ["ROLLING_PERCENTILE", "ROLLING_ZSCORE", "MACD_ATR"])
def test_current_feature_contracts_admit_all_available_relative_methods(method):
    value = frozen_fixture()
    compatible_features_fixture(value, method)
    spec = H0001Specification.of(value)
    spec.require_c1_ready()
    assert spec.blockers(PERFORMANCE)
    assert payload(spec.plugin_specification()) == spec.unpack()


@pytest.mark.parametrize("section,field,choice", [
    ("timeframe_contracts", "session_policy", "RTH_EXTENDED"),
    ("timeframe_contracts", "base", "1H"),
    ("timeframe_contracts", "base", "Daily"),
    ("rule_parameters", "swing_detector", "ATR_REVERSAL"),
    ("rule_parameters", "swing_detector", "DIRECTIONAL_CHANGE"),
])
def test_valid_frozen_future_contract_cannot_start_current_c1_or_profitability(section, field, choice):
    value = frozen_fixture(performance=True)
    value[section][field]["value"] = choice
    spec = H0001Specification.of(value)
    assert not spec.blockers(C1) and not spec.blockers(PERFORMANCE)
    assert H0001Specification.loads(spec.text, format="json") == spec
    for gate in (spec.require_c1_ready, spec.plugin_specification,
                 spec.require_profitability_ready, spec.require_historical_reproduction_ready):
        with pytest.raises(ValueError, match="C1.*future implementation"):
            gate()


@pytest.mark.parametrize("field", list(current_engine()))
def test_every_engine_capability_mismatch_fails_closed(field):
    value = frozen_fixture(performance=True)
    value["engine_capabilities"][field]["value"] = "1H" if field == "base_timeframe" else "future_v999"
    spec = H0001Specification.of(value)
    for gate in (spec.require_c1_ready, spec.require_profitability_ready):
        with pytest.raises(ValueError, match="capability/version mismatch"):
            gate()


@pytest.mark.parametrize("section,field", [
    ("feature_contracts", "macd_ema_seed"),
    ("feature_contracts", "macd_signal_start"),
    ("feature_contracts", "macd_price_field"),
    ("feature_contracts", "macd_feature_version"),
    ("feature_contracts", "history_origin"),
    ("feature_contracts", "setup_1h_relative_conventions"),
    ("feature_contracts", "entry_15m_relative_conventions"),
    ("feature_contracts", "exit_1h_relative_conventions"),
    ("rule_parameters", "swing_parameters"),
])
@pytest.mark.parametrize("part", ["name", "version"])
def test_selected_feature_contract_name_and_version_must_be_supported(section, field, part):
    value = frozen_fixture(performance=True)
    value[section][field]["value"][part] = "future_contract" if part == "name" else "v999"
    spec = H0001Specification.of(value)
    with pytest.raises(ValueError, match="unsupported contract"):
        spec.require_c1_ready()
    with pytest.raises(ValueError, match="unsupported contract"):
        spec.require_profitability_ready()


@pytest.mark.parametrize("method,parameter,bad", [
    ("ROLLING_PERCENTILE", "ties", "first"),
    ("ROLLING_PERCENTILE", "include_current", False),
    ("ROLLING_PERCENTILE", "window", 2),
    ("ROLLING_PERCENTILE", "min_history", 2),
    ("ROLLING_PERCENTILE", "field", "unknown_field"),
    ("ROLLING_PERCENTILE", "continuity", "future_grid_v2"),
    ("ROLLING_ZSCORE", "ddof", 2),
    ("ROLLING_ZSCORE", "zero_variance", "zero"),
])
def test_relative_conventions_cannot_hide_unsupported_parameters(method, parameter, bad):
    value = frozen_fixture()
    compatible_features_fixture(value, method)
    params = value["feature_contracts"]["setup_1h_relative_conventions"]["value"]["parameters"]
    params[parameter] = typed(bad)
    with pytest.raises(ValueError, match="C1"):
        H0001Specification.of(value).require_c1_ready()


@pytest.mark.parametrize("part,parameter,bad", [
    ("atr", "smoothing", "ema"), ("atr", "period", 2),
    ("atr", "seed", "first_observation"),
    ("normalization", "alignment", "nearest"),
    ("normalization", "denominator_field", "close"),
])
def test_macd_atr_nested_conventions_are_checked(part, parameter, bad):
    value = frozen_fixture()
    compatible_features_fixture(value, "MACD_ATR")
    params = value["feature_contracts"]["setup_1h_relative_conventions"]["value"]["parameters"]
    params[part]["value"]["parameters"][parameter] = typed(bad)
    with pytest.raises(ValueError, match="C1"):
        H0001Specification.of(value).require_c1_ready()


@pytest.mark.parametrize("mutation", ["missing", "extra", "ties", "width", "continuity"])
def test_swing_convention_parameters_are_explicit_and_supported(mutation):
    value = frozen_fixture()
    params = value["rule_parameters"]["swing_parameters"]["value"]["parameters"]
    if mutation == "missing":
        del params["right"]
    elif mutation == "extra":
        params["atr_threshold"] = typed(1)
    elif mutation == "ties":
        params["ties"] = typed("allow_equal")
    elif mutation == "width":
        params["right"] = typed(0)
    else:
        params["continuity"] = typed("future_grid_v2")
    with pytest.raises(ValueError, match="C1"):
        H0001Specification.of(value).require_c1_ready()


def test_all_signal_transition_prerequisites_are_available_at_c1():
    spec = H0001Specification.of(frozen_fixture())
    spec.require_c1_ready()
    value = spec.unpack()
    unavailable = {item["decision_id"] for item in spec.unresolved_fields.values()}
    assert {"H1-FILL", "H1-SIZING", "H1-EXPOSURE", "H1-ORDER-TIMING"} <= unavailable
    machine = value["state_machine"]
    assert "ACTIVE_SIGNAL" in machine["states"] and "INACTIVE_SIGNAL" in machine["states"]
    assert not {"POSITION_OPEN", "FLAT"} & set(machine["states"])
    for transition in machine["transitions"].values():
        for decision in [*transition["prerequisites"], transition["condition"]["decision_id"]]:
            assert decision not in unavailable
            assert value["decisions"][decision]["classification"] == C1


@pytest.mark.parametrize("dependency", ["H1-FILL", "H1-ORDER-TIMING", "H1-SIZING", "H1-EXPOSURE", "H1-4H"])
def test_lower_stage_transition_dependencies_cannot_be_smuggled_into_c1(dependency):
    value = frozen_fixture()
    value["state_machine"]["transitions"]["enter_intent_emitted"]["prerequisites"].append(dependency)
    with pytest.raises(ValueError, match="prerequisites"):
        H0001Specification.of(value)
    # Even generic structural specs cannot export a lower-stage transition.
    with pytest.raises(ValueError, match="lower-stage"):
        StrategySpecification.of(value).require_c1_ready()


def test_generic_frozen_structure_cannot_attest_current_engine_compatibility():
    with pytest.raises(ValueError, match="supported strategy profile"):
        StrategySpecification.of(frozen_fixture()).require_c1_ready()


def test_capability_narrative_is_not_used_for_admission():
    value = frozen_fixture()
    for decision in value["decisions"].values():
        decision["available_v2_primitive"] = "changed human explanation"
    H0001Specification.of(value).require_c1_ready()


def test_implementation_version_drift_rejects_old_capability_claim(monkeypatch):
    spec = H0001Specification.of(frozen_fixture())
    monkeypatch.setattr(PercentileSpec, "version", "rolling_empirical_midrank_v2")
    with pytest.raises(ValueError, match="capability/version mismatch"):
        spec.require_c1_ready()


def test_nested_transition_contract_cannot_depend_on_unresolved_execution():
    value = frozen_fixture()
    condition = value["state_machine"]["transitions"]["enter_intent_emitted"]["condition"]
    condition["value"]["parameters"]["fill"] = {
        "kind": "contract", "value": UNRESOLVED, "choices": [], "decision_id": "H1-FILL"}
    with pytest.raises(ValueError, match="downgrade"):
        H0001Specification.of(value)


def test_remediation_preserves_every_decision_and_unresolved_strategy_parameter():
    original = StrategySpecification.loads(subprocess.check_output([
        "git", "show", "e2bce5b0dd0bd49a7b132f3aced2a3fcaadbfb0f:research/strategy_specs/H0001-r03-draft.yaml",
    ], cwd=ROOT).decode("utf-8"))
    current = input_freeze_draft()
    old, new = original.unpack(), current.unpack()
    assert prior_decision_inventory(old) == prior_decision_inventory(new)
    for section in set(SECTIONS) - {"engine_capabilities", "feature_contracts", "timeframe_contracts", "chart_parity"}:
        assert old[section] == new[section]
    assert len(current.unresolved_fields) == 97
    assert len(original.unresolved_fields) == 107
    assert len(new["decisions"]) == len(old["decisions"]) + 3 == 78
    assert [len(current.blockers(c)) for c in (C1, PERFORMANCE, OPTIONAL)] == [46, 17, 7]


def signal_paths(machine, start, end):
    """Enumerate simple paths independently of the production graph validator."""
    pending = [(start,)]
    while pending:
        path = pending.pop()
        if path[-1] == end:
            yield path
            continue
        for transition in machine['transitions'].values():
            if transition['from'] == path[-1] and transition['to'] not in path:
                pending.append((*path, transition['to']))


def test_inactive_is_nonterminal_and_both_exit_branches_can_start_new_cycles():
    machine = draft().unpack()['state_machine']
    assert {t['to'] for t in machine['transitions'].values()
            if t['from'] == 'INACTIVE_SIGNAL'} == {'DAILY_LONG_ALLOWED', 'DISABLED'}
    for watch in ('EXIT_WATCH_WEAK', 'EXIT_WATCH_STRONG'):
        paths = list(signal_paths(machine, watch, 'ACTIVE_SIGNAL'))
        assert paths
        assert any('DISABLED' in path for path in paths)
        for path in paths:
            assert path[:2] == (watch, 'INACTIVE_SIGNAL')
            assert path[-4:] == ('DAILY_LONG_ALLOWED', 'SETUP_1H_DOWNSIDE',
                                'ENTRY_READY', 'ACTIVE_SIGNAL')


@pytest.mark.parametrize('state', STATES)
def test_every_nonterminal_state_is_reachable_and_can_complete_and_restart(state):
    machine = draft().unpack()['state_machine']
    assert list(signal_paths(machine, 'DISABLED', state))
    assert list(signal_paths(machine, state, 'INACTIVE_SIGNAL'))
    assert list(signal_paths(machine, state, 'ENTRY_READY'))


@pytest.mark.parametrize('state', STATES)
@pytest.mark.parametrize('self_loop', [False, True])
def test_graph_validation_rejects_every_nonterminal_dead_end(state, self_loop):
    value = draft().unpack()
    machine = value['state_machine']
    for key in list(machine['transitions']):
        edge = machine['transitions'][key]
        if edge['from'] == state:
            if self_loop:
                edge['to'] = state
            else:
                del machine['transitions'][key]
    with pytest.raises(ValueError, match='lifecycle dead-end'):
        validate_signal_lifecycle(machine)
    with pytest.raises(ValueError, match='lifecycle dead-end'):
        H0001Specification.of(value)


@pytest.mark.parametrize('source,target', [
    (source, target)
    for source in ('INACTIVE_SIGNAL', 'DISABLED', 'DAILY_LONG_ALLOWED')
    for target in ('SETUP_1H_DOWNSIDE', 'ENTRY_READY', 'ACTIVE_SIGNAL',
                   'ADD_READY', 'EXIT_WATCH_WEAK', 'EXIT_WATCH_STRONG')
    if (source, target) != ('DAILY_LONG_ALLOWED', 'SETUP_1H_DOWNSIDE')
    and (source == 'INACTIVE_SIGNAL' or not target.startswith('EXIT_WATCH'))
])
def test_graph_validation_rejects_direct_and_indirect_activation_bypasses(source, target):
    value = draft().unpack()
    machine = value['state_machine']
    edge = dict(machine['transitions']['daily_permission'], **{'from': source, 'to': target})
    machine['transitions']['shortcut'] = edge
    with pytest.raises(ValueError, match='lifecycle'):
        validate_signal_lifecycle(machine)
    with pytest.raises(ValueError, match='lifecycle'):
        H0001Specification.of(value)


@pytest.mark.parametrize('unreachable', [False, True])
def test_graph_rejects_closed_components_even_when_every_state_has_outgoing_edges(unreachable):
    machine = draft().unpack()['state_machine']
    if unreachable:
        # Watch states still form a live pair, but cannot be reached from start.
        for key in ('weak_watch_candidate', 'strong_watch_candidate'):
            del machine['transitions'][key]
        machine['transitions']['weak_structure_exit_candidate']['to'] = 'EXIT_WATCH_STRONG'
        machine['transitions']['strong_structure_exit_candidate']['to'] = 'EXIT_WATCH_WEAK'
    else:
        for key in ('weak_structure_exit_candidate', 'strong_structure_exit_candidate'):
            machine['transitions'][key]['to'] = 'ACTIVE_SIGNAL'
        # INACTIVE_SIGNAL still reachable through the entry node, but the active
        # component can never exit to it or reach a fresh ENTRY_READY again.
        machine['transitions']['entry_to_inactive'] = {'from': 'ENTRY_READY', 'to': 'INACTIVE_SIGNAL'}
    with pytest.raises(ValueError, match='unreachable|complete/restart'):
        validate_signal_lifecycle(machine)


def test_lifecycle_returns_reuse_unresolved_contract_without_resolving_or_adding_decisions():
    before = StrategySpecification.loads(subprocess.check_output([
        'git', 'show', '03438243b0ce35a456bf350adcdbdf6da5416c26:research/strategy_specs/H0001-r03-draft.yaml',
    ], cwd=ROOT).decode('utf-8'))
    current = input_freeze_draft()
    resolved = {"H1-SESSION", "H1-BASE", "H1-EMA-SEED", "H1-MACD-HISTORY", "H1-HISTORY-ORIGIN"}
    assert prior_unresolved_fields(current) == {p: info for p, info in before.unresolved_fields.items()
                                         if info['decision_id'] not in resolved}
    assert prior_decision_inventory(current.unpack()) == prior_decision_inventory(before.unpack())
    assert len(current.unresolved_fields) == 97
    assert len(current.unpack()['decisions']) == 78
    for key in LIFECYCLE_RETURNS:
        edge = current.unpack()['state_machine']['transitions'][key]
        assert set(edge['prerequisites']) == {'H1-DAILY-LONG', 'H1-DAILY-BLOCKER', 'H1-STATE-TRANSITIONS'}
        reference = edge['condition']['value']
        assert reference['name'] == 'existing_contract_reference'
        target = at(current.unpack(), reference['parameters']['path']['value'])
        assert target['value'] == UNRESOLVED
        assert target['decision_id'] == edge['condition']['decision_id'] == 'H1-STATE-TRANSITIONS'
    for decision in ('daily_long_permission', 'daily_exhaustion_blocker', 'transition_priority_and_resets'):
        value = frozen_fixture()
        section = 'state_machine_parameters' if decision == 'transition_priority_and_resets' else 'rule_parameters'
        value[section][decision]['value'] = UNRESOLVED
        with pytest.raises(ValueError, match='C1'):
            H0001Specification.of(value)


@pytest.mark.parametrize('key', LIFECYCLE_RETURNS)
@pytest.mark.parametrize('mutation', ['target', 'guard', 'performance'])
def test_lifecycle_reference_cannot_be_replaced_or_depend_on_execution(key, mutation):
    value = frozen_fixture()
    edge = value['state_machine']['transitions'][key]
    if mutation == 'target':
        edge['condition']['value']['parameters']['path']['value'] = 'execution_requirements.fill_price_contract'
    elif mutation == 'guard':
        edge['condition']['value'] = contract('unconditional_v1')
    else:
        edge['prerequisites'].append('H1-FILL')
    with pytest.raises(ValueError, match='reference|prerequisites'):
        H0001Specification.of(value)


def test_liveness_fix_preserves_source_worktree_bytes_at_audit_head():
    original = subprocess.check_output([
        'git', 'cat-file', '--filters',
        '03438243b0ce35a456bf350adcdbdf6da5416c26:research/hypotheses/H0001-r03.yaml',
    ], cwd=ROOT)
    assert SOURCE.read_bytes() == original


def test_missing_or_extra_feature_convention_parameters_fail_closed():
    for mutation in ("missing", "extra"):
        value = frozen_fixture()
        params = value["feature_contracts"]["setup_1h_relative_conventions"]["value"]["parameters"]
        if mutation == "missing":
            del params["include_current"]
        else:
            params["future_option"] = typed(True)
        with pytest.raises(ValueError, match="C1.*required/unknown"):
            H0001Specification.of(value).require_c1_ready()


def test_research_extra_owns_pyyaml_and_base_engine_imports_without_it():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert not any(dep.lower().startswith("pyyaml") for dep in project["dependencies"])
    assert "PyYAML>=6,<7" in project["optional-dependencies"]["research"]
    subprocess.run([sys.executable, "-c", """
import importlib.abc
import sys
class WithoutYaml(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'yaml' or fullname.startswith('yaml.'):
            raise ModuleNotFoundError('research extra missing', name='yaml')
sys.meta_path.insert(0, WithoutYaml())
import richping.cli
import richping.research_v2.replay
import richping.research_v2.features
try:
    import richping.research_v2.strategy.specification
except ModuleNotFoundError as exc:
    assert exc.name == 'yaml'
else:
    raise AssertionError('Specification API requires the research extra')
"""], cwd=ROOT, check=True)
