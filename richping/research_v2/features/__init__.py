"""Strategy-neutral, deterministic services over detached causal inputs."""

from .contracts import FeatureResult, FeatureSpec, ScalarPoint, ScalarSeries, close_series
from .moving import EMASpec, ema
from .macd import MACDSpec, macd, macd_series
from .volatility import ATRSpec, TRSpec, atr, true_range
from .relative import (NormalizeSpec, PercentileSpec, ZScoreSpec, normalize,
                       rolling_percentile, rolling_zscore)
from .structure import FractalSpec, SwingDetector, SwingEvent, classify_swings, confirmed_swings
