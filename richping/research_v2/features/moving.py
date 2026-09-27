"""First-observation recursive EMA; no provider parity claim."""

from dataclasses import dataclass
from typing import ClassVar

from .contracts import Spec, completed_bars, positive_int, result


@dataclass(frozen=True, slots=True)
class EMASpec(Spec):
    span: int
    min_history: int
    seed: str = "first_observation"
    field: str = "close"
    name: ClassVar[str] = "ema"
    version: ClassVar[str] = "ema_first_observation_recursive_v1"

    def __post_init__(self):
        positive_int(self.span)
        positive_int(self.min_history)
        if self.seed != "first_observation" or self.field != "close":
            raise ValueError("Unsupported EMA convention")


def recursive_ema(values, span):
    """Internal arithmetic: E[0]=x[0]; E[t]=alpha*x[t]+(1-alpha)*E[t-1]."""
    alpha = 2 / (span + 1)
    output = []
    for x in values:
        output.append(x if not output else alpha * x + (1 - alpha) * output[-1])
    return tuple(output)


def ema(context, symbol, timeframe, spec: EMASpec):
    bars = completed_bars(context, symbol, timeframe)
    if len(bars) < spec.min_history:
        return result(spec, symbol, timeframe, context.as_of, bars,
                      status="NOT_READY", reason="insufficient_history")
    values = recursive_ema((b.close for b in bars), spec.span)
    return result(spec, symbol, timeframe, context.as_of, bars, {"ema": values[-1]})
