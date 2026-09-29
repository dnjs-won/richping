"""C0 admission adapter for the existing V2-A/B primitives; no rule evaluation.

Contract names/versions are protocol identifiers, never narrative descriptions.
Feature parameters are explicit and validated by the existing V2-B spec classes.
Adding a future capability requires an implementation and a reviewed adapter.
"""

from dataclasses import fields

from ..aggregation import AGGREGATION_VERSION
from ..contracts import AVAILABILITY_VERSION
from ..features.continuity import CONTINUITY_VERSION
from ..features.macd import MACDSpec
from ..features.relative import NormalizeSpec, PercentileSpec, ZScoreSpec
from ..features.structure import FractalSpec
from ..features.volatility import ATRSpec
from .specification import exact


def current_engine():
    return {
        "capability_profile": "v2_ab_c1_signal_v1",
        "base_timeframe": "15m",
        "session_policy": "XNYS_RTH",
        "availability": AVAILABILITY_VERSION,
        "continuity": CONTINUITY_VERSION,
        "aggregation": AGGREGATION_VERSION,
        "macd_feature_version": MACDSpec.version,
        "percentile_feature_version": PercentileSpec.version,
        "zscore_feature_version": ZScoreSpec.version,
        "normalization_feature_version": NormalizeSpec.version,
        "atr_feature_version": ATRSpec.version,
        "swing_feature_version": FractalSpec.version,
        "classification_feature_version": "confirmed_same_kind_comparison_v1",
    }


def _contract(value, identifier, keys, where):
    exact(value, {"name", "version", "parameters"}, f"C1 {where}")
    name, version = identifier.rsplit("_", 1)
    if (value["name"], value["version"]) != (name, version):
        raise ValueError(f"C1 {where}: unsupported contract; future implementation required")
    exact(value["parameters"], keys, f"C1 {where} parameters")
    return {key: record["value"] for key, record in value["parameters"].items()}


def _primitive(value, cls, where, *, extra=()):
    params = _contract(value, cls.version, {f.name for f in fields(cls)} | set(extra), where)
    arguments = {f.name: params[f.name] for f in fields(cls)}
    try:
        cls(**arguments)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"C1 {where}: unsupported feature convention: {exc}") from exc
    return params


def require_current_engine(value):
    """Validate chosen input/feature contracts independently of structural freeze."""
    capabilities = {key: record["value"] for key, record in value["engine_capabilities"].items()}
    if capabilities != current_engine():
        raise ValueError("C1 engine capability/version mismatch; future implementation required")
    frames, rules, features = (value[key] for key in (
        "timeframe_contracts", "rule_parameters", "feature_contracts"))
    if frames["base"]["value"] != capabilities["base_timeframe"]:
        raise ValueError("C1 unsupported base timeframe; future implementation required")
    if {"RTH": "XNYS_RTH"}.get(frames["session_policy"]["value"]) != capabilities["session_policy"]:
        raise ValueError("C1 unsupported session policy; future implementation required")
    if rules["swing_detector"]["value"] != "FRACTAL":
        raise ValueError("C1 unsupported swing detector; future implementation required")

    conventions = {
        "macd_ema_seed": "first_observation_recursive_v1",
        "macd_signal_start": "first_macd_observation_v1",
        "macd_price_field": "close_v1",
        "macd_feature_version": MACDSpec.version,
        "history_origin": "available_completed_history_prefix_v1",
    }
    for key, identifier in conventions.items():
        _contract(features[key]["value"], identifier, (), key)
    for suffix in ("daily", "1h", "15m"):
        MACDSpec(*(features["macd_" + key]["value"] for key in ("fast", "slow", "signal")),
                 min_history=features["macd_min_history_" + suffix]["value"])

    for prefix in ("setup_1h", "entry_15m", "exit_1h"):
        method = rules[prefix + "_relative_transform"]["value"]
        convention = features[prefix + "_relative_conventions"]["value"]
        where = prefix + "_relative_conventions"
        lookback = rules[prefix + "_rolling_lookback"]["value"]
        if method in {"ROLLING_PERCENTILE", "ROLLING_ZSCORE"}:
            cls = PercentileSpec if method == "ROLLING_PERCENTILE" else ZScoreSpec
            params = _primitive(convention, cls, where, extra=("field",))
            field = params["field"]
            if params["window"] != lookback:
                raise ValueError(f"C1 {where}: lookback/window mismatch")
        elif method == "MACD_ATR":
            params = _contract(convention, "macd_atr_normalization_v1", ("normalization", "atr"), where)
            scale = _primitive(params["atr"], ATRSpec, where + ".atr")
            norm = _primitive(params["normalization"], NormalizeSpec, where + ".normalization")
            field = norm["numerator_field"]
            if scale["period"] != lookback or norm["denominator_field"] != "atr":
                raise ValueError(f"C1 {where}: ATR period/field mismatch")
        else:
            raise ValueError(f"C1 {where}: unsupported relative method")
        if type(field) is not str or field not in {"macd_line", "signal_line", "histogram"}:
            raise ValueError(f"C1 {where}: unsupported MACD field")
    _primitive(rules["swing_parameters"]["value"], FractalSpec, "swing_parameters")
