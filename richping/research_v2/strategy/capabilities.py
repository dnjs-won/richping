"""C0 admission adapter for the existing V2-A/B primitives; no rule evaluation.

Contract names/versions are protocol identifiers, never narrative descriptions.
Feature parameters are explicit and validated by the existing V2-B spec classes.
Adding a future capability requires an implementation and a reviewed adapter.
"""

from dataclasses import fields

from ..features.macd import MACDSpec
from ..features.relative import NormalizeSpec, PercentileSpec, ZScoreSpec
from ..features.structure import FractalSpec
from ..features.volatility import ATRSpec
from .specification import exact
from ..sessions import RTH, EXTENDED, session_profile


def current_engine(profile=RTH):
    selected = session_profile(profile)
    return {
        "capability_profile": "v2_ab_c1_signal_v1" if profile == RTH else "v2_extended_c1_signal_v1",
        "base_timeframe": "15m",
        "session_policy": selected.name,
        "availability": selected.availability,
        "continuity": selected.continuity,
        "aggregation": selected.aggregation,
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


def require_session_capability(value):
    """Intraday (15m/1H) session/base/profile admission only, not C1 readiness.

    A profile's generic Daily aggregation capability does not select H0001's
    Daily regime series. That decision has its own admission below.
    """
    capabilities = {key: record["value"] for key, record in value["engine_capabilities"].items()}
    profile = {"v2_ab_c1_signal_v1": RTH, "v2_extended_c1_signal_v1": EXTENDED}.get(
        capabilities["capability_profile"])
    if profile is None or capabilities != current_engine(profile):
        raise ValueError("C1 engine capability/version mismatch; future implementation required")
    frames = value["timeframe_contracts"]
    if frames["base"]["value"] != capabilities["base_timeframe"]:
        raise ValueError("C1 unsupported base timeframe; future implementation required")
    if {"RTH": RTH, "RTH_EXTENDED": EXTENDED}.get(frames["session_policy"]["value"]) != capabilities["session_policy"]:
        raise ValueError("C1 unsupported session policy; future implementation required")
    return capabilities


def require_daily_session_capability(value):
    """Explicit Daily regime semantics, independent of the intraday profile."""
    daily = value["timeframe_contracts"].get("daily_session_policy", {}).get("value")
    profile = {"RTH_DAILY": RTH, "EXTENDED_DAILY": EXTENDED}.get(daily)
    if profile is None:
        raise ValueError("C1 Daily session requires resolved H1-DAILY-SESSION")
    return current_engine(profile)


def require_current_engine(value):
    """Validate chosen input/feature contracts independently of structural freeze."""
    capabilities = require_session_capability(value)
    daily_capabilities = require_daily_session_capability(value)
    rules, features = value["rule_parameters"], value["feature_contracts"]
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
                 min_history=features["macd_min_history_" + suffix]["value"],
                 continuity=(daily_capabilities if suffix == "daily" else capabilities)["continuity"])

    for prefix in ("setup_1h", "entry_15m", "exit_1h"):
        method = rules[prefix + "_relative_transform"]["value"]
        convention = features[prefix + "_relative_conventions"]["value"]
        where = prefix + "_relative_conventions"
        lookback = rules[prefix + "_rolling_lookback"]["value"]
        if method in {"ROLLING_PERCENTILE", "ROLLING_ZSCORE"}:
            cls = PercentileSpec if method == "ROLLING_PERCENTILE" else ZScoreSpec
            extra = ("field", "macd_line_lt_zero") if (
                value["specification_version"] in {"h0001_r03_spec_v11", "h0001_r03_spec_v12", "h0001_r03_spec_v13"} and prefix == "setup_1h") else ("field",)
            if value["specification_version"] in {"h0001_r03_spec_v12", "h0001_r03_spec_v13"} and prefix == "entry_15m":
                extra = ("field", "macd_line_lt_zero", "first_READY_N", "session_profile",
                         "history_origin", "unavailable", "known_at")
            params = _primitive(convention, cls, where, extra=extra)
            if "macd_line_lt_zero" in params and params["macd_line_lt_zero"] is not True:
                raise ValueError("C1 frozen 1H negative polarity required")
            if params["continuity"] != capabilities["continuity"]:
                raise ValueError(f"C1 {where}: session continuity mismatch")
            field = params["field"]
            if params["window"] != lookback:
                raise ValueError(f"C1 {where}: lookback/window mismatch")
        elif method == "MACD_ATR":
            params = _contract(convention, "macd_atr_normalization_v1", ("normalization", "atr"), where)
            scale = _primitive(params["atr"], ATRSpec, where + ".atr")
            if scale["continuity"] != capabilities["continuity"]:
                raise ValueError(f"C1 {where}: session continuity mismatch")
            norm = _primitive(params["normalization"], NormalizeSpec, where + ".normalization")
            field = norm["numerator_field"]
            if scale["period"] != lookback or norm["denominator_field"] != "atr":
                raise ValueError(f"C1 {where}: ATR period/field mismatch")
        else:
            raise ValueError(f"C1 {where}: unsupported relative method")
        if type(field) is not str or field not in {"macd_line", "signal_line", "histogram"}:
            raise ValueError(f"C1 {where}: unsupported MACD field")
    swing = _primitive(rules["swing_parameters"]["value"], FractalSpec, "swing_parameters")
    expected = "xnys_completed_grid" if capabilities["session_policy"] == RTH else capabilities["continuity"]
    if swing["continuity"] != expected:
        raise ValueError("C1 swing_parameters: session continuity mismatch")
