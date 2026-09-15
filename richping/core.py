from dataclasses import asdict, dataclass, fields
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from hashlib import sha256
import json
from pathlib import Path
import re
import tomllib

import exchange_calendars as xcals


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return sha256(canonical(value).encode()).hexdigest()


def timestamp(value):
    dt = datetime.fromisoformat(value) if isinstance(value, str) else value
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError("Timezone-aware timestamp required")
    return dt.astimezone(UTC)


def utcnow():
    return datetime.now(UTC).isoformat()


def ticker(value):
    value = value.strip().upper()
    if not re.fullmatch(r"[A-Z][A-Z0-9.\-]{0,14}", value):
        raise ValueError(f"Invalid ticker: {value!r}")
    return value


@lru_cache(maxsize=1)
def calendar():
    return xcals.get_calendar("XNYS", start="1990-01-01", end="2035-12-31")


def sessions(start, end):
    return [str(d.date()) for d in calendar().sessions_in_range(start, end)]


def close_at(session):
    return calendar().session_close(session).to_pydatetime()


def open_at(session):
    return calendar().session_open(session).to_pydatetime()


def cutoff_at(session):
    return close_at(session) + timedelta(minutes=30)


def next_sessions(session, n):
    cal = calendar()
    pos = cal.sessions.get_loc(session)
    return [str(d.date()) for d in cal.sessions[pos + 1:pos + n + 1]]


def latest_session(now=None):
    now = timestamp(now or utcnow())
    candidates = sessions((now - timedelta(days=15)).date().isoformat(), now.date().isoformat())
    return next(s for s in reversed(candidates) if cutoff_at(s) <= now)


def code_hash():
    return digest({p.name: p.read_text(encoding="utf-8") for p in sorted(Path(__file__).parent.glob("*.py"))})


@dataclass(frozen=True)
class Config:
    tickers: tuple = ("AAPL", "MSFT", "NVDA", "AVGO", "AMZN", "META", "GOOGL", "PLTR")
    top_k: int = 3
    horizon: int = 5
    min_score: float = 60.0
    min_edge: float = 0.0
    min_samples: int = 60
    min_dates: int = 30
    train_sessions: int = 504
    commission_bps: float = 10.0
    slippage_bps: float = 10.0
    min_price: float = 5.0
    min_dollar_volume: float = 5_000_000.0
    bootstrap_samples: int = 500
    seed: int = 20260915

    def __post_init__(self):
        import math
        object.__setattr__(self, "tickers", tuple(ticker(t) for t in self.tickers))
        if not self.tickers or len(set(self.tickers)) != len(self.tickers):
            raise ValueError("Unique non-empty universe required")
        if any(t in {"SPY", "QQQ"} for t in self.tickers):
            raise ValueError("SPY/QQQ are context, not candidate tickers")
        for name in ("top_k", "horizon", "min_samples", "min_dates", "train_sessions", "bootstrap_samples", "seed"):
            value = getattr(self, name)
            if type(value) is not int or value < 1:
                raise ValueError(f"Invalid integer config: {name}")
        for f in fields(self):
            value = getattr(self, f.name)
            if isinstance(value, (int, float)) and not math.isfinite(value):
                raise ValueError(f"Non-finite config: {f.name}")
        if self.horizon not in (1, 3, 5, 10, 20) or not 0 <= self.min_score <= 100:
            raise ValueError("Invalid horizon or score")
        if min(self.commission_bps, self.slippage_bps, self.min_price, self.min_dollar_volume, self.min_edge) < 0:
            raise ValueError("Costs, edge and filters must be nonnegative")
        if self.min_dates < 2 or self.min_samples < self.min_dates or self.bootstrap_samples < 100:
            raise ValueError("Insufficient statistical configuration")

    @property
    def cost(self):
        return (self.commission_bps + self.slippage_bps) / 10000

    def payload(self):
        return asdict(self)

    @property
    def model_id(self):
        return "baseline-v1-" + digest({"config": self.payload(), "code": code_hash()})[:16]

    @classmethod
    def load(cls, path):
        with Path(path).open("rb") as f:
            return cls(**tomllib.load(f))
