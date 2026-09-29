"""Versioned, immutable specification values, not a rule evaluator.

Generic structure validates explicit typed parameters and decision references.
Requires the optional ``richping[research]`` extra (including JSON APIs).
Strategy-specific subclasses supply their mandatory field inventory. No imports
from a concrete strategy, execution engine, dataset or store are permitted here.
"""

from dataclasses import dataclass
import json
import math
from pathlib import Path
import re

import yaml

from ...core import digest, timestamp
from ..contracts import JsonObject, TIMEFRAMES, nonempty

SCHEMA_VERSION = "strategy_specification_v1"
UNRESOLVED = "UNRESOLVED"
C1 = "C1_IMPLEMENTATION_BLOCKER"
PERFORMANCE = "PERFORMANCE_EXPERIMENT_BLOCKER"
OPTIONAL = "OPTIONAL_FUTURE_EXTENSION"
SECTIONS = (
    "feature_contracts", "timeframe_contracts", "rule_parameters",
    "state_machine_parameters", "execution_requirements", "research_requirements",
    "optional_extensions", "chart_parity", "engine_capabilities",
)


def exact(value, keys, where):
    if not isinstance(value, dict) or set(value) != set(keys):
        raise ValueError(f"{where}: required/unknown fields; expected {sorted(keys)}")


def positive(value, where):
    if type(value) is not int or value < 1:
        raise ValueError(f"{where}: positive integer required")


class _Loader(yaml.SafeLoader):
    """JSON-compatible YAML scalars; reject aliases and duplicate/merge keys."""

    def compose_node(self, parent, index):
        if self.check_event(yaml.AliasEvent):
            raise ValueError("YAML aliases are not supported")
        return super().compose_node(parent, index)


def _mapping(loader, node):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node)
        if not isinstance(key, str) or key in result or key == "<<":
            raise ValueError("Duplicate/non-string/merge key")
        result[key] = loader.construct_object(value_node)
    return result


_Loader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping)
# Unquoted timestamps must remain strings, and yes/no must not silently become
# booleans. Do not mutate SafeLoader's process-global resolver table.
_Loader.yaml_implicit_resolvers = {
    key: [(tag, pattern) for tag, pattern in entries
          if tag not in {"tag:yaml.org,2002:timestamp", "tag:yaml.org,2002:bool"}]
    for key, entries in yaml.SafeLoader.yaml_implicit_resolvers.items()
}
_Loader.add_implicit_resolver("tag:yaml.org,2002:bool", re.compile(r"^(true|false)$"), list("tf"))


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def _json_value(value):
    if isinstance(value, dict):
        if any(type(k) is not str for k in value):
            raise ValueError("String keys required")
        return {k: _json_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_value(v) for v in value]
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError("Finite numbers required")
        # 1, 1.0, 1e0 and negative zero carry the same numeric meaning.
        return int(value) if value.is_integer() else value
    if value is None or type(value) in (str, int, bool):
        return value
    raise ValueError("JSON-compatible values required")


def parameter(record, path):
    exact(record, {"kind", "value", "choices", "decision_id"}, path)
    kind, value, choices = record["kind"], record["value"], record["choices"]
    if kind not in {"text", "contract", "enum", "timeframe", "integer", "number", "boolean"}:
        raise ValueError(f"{path}: unknown parameter kind")
    if not isinstance(choices, list) or any(type(c) is not str or not c for c in choices):
        raise ValueError(f"{path}: invalid choices")
    if len(set(choices)) != len(choices) or UNRESOLVED in choices:
        raise ValueError(f"{path}: duplicate/reserved choice")
    if (kind == "enum") != bool(choices):
        raise ValueError(f"{path}: enum requires choices; other kinds forbid them")
    record["choices"] = sorted(choices)
    if record["decision_id"] is not None:
        nonempty(record["decision_id"])
    if value == UNRESOLVED:
        if record["decision_id"] is None:
            raise ValueError(f"{path}: unresolved requires a decision")
        return
    if kind == "contract":
        exact(value, {"name", "version", "parameters"}, path + ".value")
        if (not isinstance(value["name"], str)
                or not re.fullmatch(r"[a-z][a-z0-9_]*", value["name"])
                or not isinstance(value["version"], str)
                or not re.fullmatch(r"v[1-9][0-9]*", value["version"])
                or not isinstance(value["parameters"], dict)):
            raise ValueError(f"{path}: versioned contract and explicit parameters required")
        return
    valid = {
        "text": lambda: type(value) is str and bool(value.strip()),
        "enum": lambda: type(value) is str and value in choices,
        "timeframe": lambda: type(value) is str and value in TIMEFRAMES,
        "integer": lambda: type(value) is int and value >= 0,
        "number": lambda: type(value) in (int, float) and math.isfinite(value),
        "boolean": lambda: type(value) is bool,
    }[kind]()
    if not valid:
        raise ValueError(f"{path}: invalid {kind} value")


def validate(value):
    exact(value, {"schema_version", "strategy_id", "specification_version", "hypothesis_id",
                  "hypothesis_revision", "status", "created_at", "updated_at", "source",
                  "direction", "decisions", "state_machine", *SECTIONS}, "specification")
    if value["schema_version"] != SCHEMA_VERSION:
        raise ValueError("Unsupported schema version")
    for key in ("strategy_id", "specification_version", "hypothesis_id"):
        nonempty(value[key])
        if value[key] == UNRESOLVED:
            raise ValueError("Identity must be resolved")
    positive(value["hypothesis_revision"], "hypothesis_revision")
    if value["status"] not in {"DRAFT", "FROZEN"}:
        raise ValueError("Unknown specification status")
    if value["direction"] not in {"LONG_ONLY", "SHORT_ONLY", "LONG_SHORT"}:
        raise ValueError("Unknown direction")
    for key in ("created_at", "updated_at"):
        if not isinstance(value[key], str):
            raise ValueError("Timestamp string required")
        value[key] = timestamp(value[key]).isoformat()
    if value["updated_at"] < value["created_at"]:
        raise ValueError("updated_at precedes created_at")
    exact(value["source"], {"path", "sha256"}, "source")
    nonempty(value["source"]["path"])
    if not re.fullmatch(r"[0-9a-f]{64}", value["source"]["sha256"]):
        raise ValueError("Source SHA-256 required")
    decisions = value["decisions"]
    if not isinstance(decisions, dict):
        raise ValueError("Decision mapping required")
    for key, decision in decisions.items():
        nonempty(key)
        exact(decision, {"classification", "question", "current_hypothesis_statement",
                         "source_refs", "available_v2_primitive", "candidate_choices",
                         "required_for_c1", "required_for_profitability"}, key)
        category = decision["classification"]
        if category not in {C1, PERFORMANCE, OPTIONAL}:
            raise ValueError("Unknown blocker classification")
        if (decision["required_for_c1"] is not (category == C1)
                or decision["required_for_profitability"] is not (category != OPTIONAL)):
            raise ValueError("Decision gates disagree with classification")
        for field in ("question", "current_hypothesis_statement", "available_v2_primitive"):
            nonempty(decision[field])
        for field in ("source_refs", "candidate_choices"):
            items = decision[field]
            if not isinstance(items, list) or not items or any(type(s) is not str or not s for s in items):
                raise ValueError("Nonempty decision reference/candidate list required")
            if len(set(items)) != len(items):
                raise ValueError("Duplicate decision reference/candidate")
            decision[field] = sorted(items)
    parameters = {}
    for section in SECTIONS:
        records = value[section]
        if not isinstance(records, dict):
            raise ValueError(f"{section}: mapping required")
        for key, record in records.items():
            nonempty(key)
            parameters[f"{section}.{key}"] = record
    machine = value["state_machine"]
    exact(machine, {"states", "transitions"}, "state_machine")
    states, transitions = machine["states"], machine["transitions"]
    if (not isinstance(states, list) or not states or any(type(s) is not str or not s for s in states)
            or len(set(states)) != len(states) or not isinstance(transitions, dict)):
        raise ValueError("Unique state names and transition mapping required")
    machine["states"] = sorted(states)
    for key, transition in transitions.items():
        exact(transition, {"from", "to", "condition", "prerequisites"}, key)
        if transition["from"] not in states or transition["to"] not in states:
            raise ValueError("Unknown transition state")
        refs = transition["prerequisites"]
        if (not isinstance(refs, list) or not refs or any(type(r) is not str or r not in decisions for r in refs)
                or len(set(refs)) != len(refs)):
            raise ValueError("Unique known transition prerequisites required")
        transition["prerequisites"] = sorted(refs)
        parameters[f"state_machine.transitions.{key}.condition"] = transition["condition"]
    referenced, unresolved = set(), {}
    pending = [(path, record, None) for path, record in parameters.items()]
    while pending:
        path, record, parent_decision = pending.pop()
        parameter(record, path)
        decision_id = record["decision_id"]
        if decision_id is not None:
            if decision_id not in decisions:
                raise ValueError(f"{path}: unknown decision reference")
            referenced.add(decision_id)
            rank = {OPTIONAL: 0, PERFORMANCE: 1, C1: 2}
            if parent_decision is not None and rank[decisions[decision_id]["classification"]] < rank[
                    decisions[parent_decision]["classification"]]:
                raise ValueError("Nested contract cannot downgrade its parent's requirement")
        if record["kind"] == "contract" and record["value"] != UNRESOLVED:
            for name, child in record["value"]["parameters"].items():
                nonempty(name)
                pending.append((f"{path}.value.parameters.{name}", child, decision_id or parent_decision))
        if record["value"] == UNRESOLVED:
            unresolved[path] = decision_id
    if referenced != set(decisions):
        raise ValueError("Orphan decision; required field may have been omitted")
    if value["status"] == "FROZEN" and any(
            decisions[key]["classification"] == C1 for key in unresolved.values()):
        raise ValueError("FROZEN forbids unresolved C1 implementation blockers")
    return unresolved


@dataclass(frozen=True, slots=True)
class StrategySpecification:
    """Immutable canonical JSON; detached copies never mutate the source value.

    FROZEN means signal-contract completeness, not profitability or approval.
    Concrete plugins must consume their strategy-specific validated subclass.
    """

    text: str

    def __post_init__(self):
        value = json.loads(self.text, object_pairs_hook=_pairs)
        # Validate before normalizing numeric spelling, so a fractional/inexact
        # integer or a float masquerading as an integer parameter fails closed.
        validate(value)
        object.__setattr__(self, "text", JsonObject.of(_json_value(value)).text)

    @classmethod
    def of(cls, value):
        # Reject non-string keys before JSON can coerce them to strings.
        _json_value(value)
        return cls(json.dumps(value, allow_nan=False))

    @classmethod
    def loads(cls, text, *, format="yaml"):
        try:
            if format == "yaml":
                value = yaml.load(text, Loader=_Loader)
            elif format == "json":
                value = json.loads(text, object_pairs_hook=_pairs)
            else:
                raise ValueError("Unsupported serialization format")
            return cls.of(value)
        except (yaml.YAMLError, TypeError, OverflowError) as exc:
            raise ValueError("Invalid specification serialization") from exc

    @classmethod
    def load(cls, path):
        path = Path(path)
        if path.suffix not in {".yaml", ".yml", ".json"}:
            raise ValueError("Unsupported specification file extension")
        return cls.loads(path.read_text(encoding="utf-8"),
                         format="json" if path.suffix == ".json" else "yaml")

    def unpack(self):
        return json.loads(self.text)

    @property
    def specification_hash(self):
        return digest(self.unpack())

    @property
    def unresolved_fields(self):
        value = self.unpack()
        return {path: {"decision_id": key, "classification": value["decisions"][key]["classification"]}
                for path, key in validate(value).items()}

    def blockers(self, classification):
        if classification not in {C1, PERFORMANCE, OPTIONAL}:
            raise ValueError("Unknown blocker classification")
        return tuple(sorted({item["decision_id"] for item in self.unresolved_fields.values()
                             if item["classification"] == classification}))

    def require_profitability_ready(self):
        self.require_c1_ready()
        if self.blockers(PERFORMANCE):
            raise ValueError("Profitability experiment blocked; frozen complete contracts required")

    def require_c1_ready(self):
        """Implementation admission gate, not proof that a plugin exists."""
        value = self.unpack()
        if value["status"] != "FROZEN" or self.blockers(C1):
            raise ValueError("C1 requires FROZEN specification without C1 blockers")
        for key, transition in value["state_machine"]["transitions"].items():
            refs = [*transition["prerequisites"], transition["condition"]["decision_id"]]
            if any(ref is None or value["decisions"][ref]["classification"] != C1 for ref in refs):
                raise ValueError(f"C1 transition {key} depends on a lower-stage decision")
        self._require_engine_compatibility(value)

    def _require_engine_compatibility(self, value):
        # A generic structural value cannot attest a strategy's capabilities.
        raise ValueError("C1 compatibility requires a supported strategy profile")

    def plugin_specification(self):
        self.require_c1_ready()
        # Existing replay hashes this exact JSON body; no self-referential hash.
        return JsonObject(self.text)
