"""Authorized Basic SIP admission probes; never orders, outcomes or fallback feeds.

Live requests are explicitly invoked from main. Offline validators have no network.
Only the two named credentials are read, never serialized or hashed.
"""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import sys

from scripts.h0001_long_history_audit import write_new
from richping.research_v2.real_data import expected_slots, request
from richping.research_v2.sessions import NY, RTH, session_bounds

ROOT = Path("research/data_evidence/h0001-alpaca-basic-20261004")
HOST = "https://data.alpaca.markets"


def encode(value):
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def credentials(path=Path(".env.local"), environ=None):
    environ = os.environ if environ is None else environ
    names = ("APCA_API_KEY_ID", "APCA_API_SECRET_KEY")
    values = {n: environ.get(n, "") for n in names}
    if path.exists():
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            name, sep, value = line.strip().removeprefix("export ").partition("=")
            if sep and name in names and not values[name]:
                values[name] = value.strip().strip("\"'")
    if not all(values.values()):
        raise ValueError("Both named Alpaca credentials are required")
    return {"APCA-API-KEY-ID": values[names[0]], "APCA-API-SECRET-KEY": values[names[1]]}


class ProviderFailure(ValueError):
    pass


class Client:
    def __init__(self, root=ROOT, headers=None):
        self.root = root
        self.headers = credentials() if headers is None else headers
        self.records = []

    def get(self, identity, endpoint, params):
        from curl_cffi import requests
        if endpoint not in {"/v2/stocks/SOXX/bars", "/v1/corporate-actions", "/v2/stocks/SOXX/trades"}:
            raise ValueError("Read-only endpoint allowlist")
        started = datetime.now(timezone.utc).isoformat()
        try:
            response = requests.get(HOST + endpoint, params=params, headers=self.headers,
                                    timeout=40, impersonate="chrome")
            body, status = response.content, response.status_code
        except Exception as exc:
            record = {"id": identity, "endpoint": endpoint, "params": params,
                      "requested_at": started, "http_status": None,
                      "transport": "TRANSPORT_FAILURE_CAPABILITY_UNKNOWN",
                      "exception_type": type(exc).__name__}
            self.records.append(record)
            raise ProviderFailure("Transport failure; capability unknown") from None
        # Providers must not echo authentication into any persisted response.
        if any(value.encode() in body for value in self.headers.values()):
            raise ProviderFailure("Unsafe response; not persisted")
        hashed = sha256(body).hexdigest()
        write_new(self.root / "raw" / (hashed + ".json"), body)
        record = {"id": identity, "endpoint": endpoint, "params": dict(params),
                  "requested_at": started, "captured_at": datetime.now(timezone.utc).isoformat(),
                  "http_status": status, "transport": "HTTP_RESPONSE", "authenticated": True,
                  "sha256": hashed, "bytes": len(body)}
        self.records.append(record)
        print(json.dumps({"id": identity, "http_status": status, "bytes": len(body)}), flush=True)
        if status != 200:
            raise ProviderFailure(f"Provider HTTP {status}; not empty market data")
        try:
            payload = json.loads(body)
        except (ValueError, UnicodeDecodeError):
            raise ProviderFailure("Malformed provider JSON") from None
        if not isinstance(payload, dict) or any(k in payload for k in ("error", "message", "code")):
            raise ProviderFailure("Provider error payload; not empty data")
        return payload

    def bars(self, identity, start, end, timeframe="15Min", adjustment="raw", limit=10000):
        params = {"start": start, "end": end, "timeframe": timeframe, "feed": "sip",
                  "adjustment": adjustment, "sort": "asc", "limit": limit,
                  "asof": "-", "currency": "USD"}
        return paginate(lambda p: self.get(identity, "/v2/stocks/SOXX/bars", p), params)


def paginate(fetch, params):
    if params.get("feed") != "sip" or params.get("sort") != "asc":
        raise ValueError("Explicit SIP ascending feed required")
    rows, tokens, pages = [], set(), 0
    current = dict(params)
    while True:
        payload = fetch(current)
        if any(k in payload for k in ("error", "message", "code")):
            raise ProviderFailure("Provider error payload; not empty data")
        if payload.get("symbol") != "SOXX" or not isinstance(payload.get("bars"), list):
            raise ProviderFailure("Wrong symbol/malformed bars; not empty data")
        page = payload["bars"]
        for row in page:
            validate_bar(row)
            instant = datetime.fromisoformat(row["t"].replace("Z", "+00:00"))
            if rows and instant <= datetime.fromisoformat(rows[-1]["t"].replace("Z", "+00:00")):
                raise ProviderFailure("Duplicate/reversed pagination timestamp")
            if not datetime.fromisoformat(params["start"].replace("Z", "+00:00")) <= instant <= datetime.fromisoformat(params["end"].replace("Z", "+00:00")):
                raise ProviderFailure("Provider row outside inclusive request")
            rows.append(row)
        pages += 1
        if "next_page_token" not in payload:
            raise ProviderFailure("Pagination completion marker absent")
        token = payload["next_page_token"]
        if token is None:
            return {"rows": rows, "pages": pages, "terminal_token": None}
        if not isinstance(token, str) or not token or token in tokens or not page:
            raise ProviderFailure("Pagination cycle/empty nonterminal page")
        tokens.add(token)
        current = {**params, "page_token": token}


def validate_bar(row):
    import math
    if not isinstance(row, dict) or not {"t", "o", "h", "l", "c", "v", "n", "vw"} <= row.keys():
        raise ProviderFailure("Partial OHLCV")
    instant = datetime.fromisoformat(row["t"].replace("Z", "+00:00"))
    if instant.tzinfo is None:
        raise ProviderFailure("Missing UTC clock")
    if any(type(row[k]) not in (int, float) or not math.isfinite(row[k]) for k in ("o", "h", "l", "c", "v", "n", "vw")):
        raise ProviderFailure("Null/nonfinite OHLCV")
    if row["l"] <= 0 or not row["l"] <= min(row["o"], row["c"]) <= max(row["o"], row["c"]) <= row["h"] or row["v"] < 0 or row["n"] < 0:
        raise ProviderFailure("Invalid OHLCV units")


def grid(rows, start, end):
    from collections import Counter
    expected, unsupported = expected_slots(request("SOXX", start, end))
    present, counts, zeros, offgrid = set(), Counter(), Counter(), []
    for row in rows:
        validate_bar(row)
        instant = datetime.fromisoformat(row["t"].replace("Z", "+00:00"))
        if instant in present:
            raise ProviderFailure("Duplicate grid timestamp")
        present.add(instant)
        local = instant.astimezone(NY)
        minutes = local.hour * 60 + local.minute
        _, official_close = session_bounds(local.date().isoformat(), RTH)
        close_minutes = official_close.astimezone(NY).hour * 60 + official_close.astimezone(NY).minute
        part = "PREMARKET" if 240 <= minutes < 570 else "RTH" if 570 <= minutes < close_minutes else "AFTER_HOURS" if close_minutes <= minutes < 1200 else "OUTSIDE_EXTENDED"
        counts[part] += 1
        zeros[part] += row["v"] == 0
        if minutes % 15 or instant.second or instant.microsecond or not 240 <= minutes < 1200:
            offgrid.append(row["t"])
    missing = sorted(set(expected) - present)
    return {"expected_supported_slots": len(expected), "observed": len(rows),
            "missing_count": len(missing), "missing_slots": [t.isoformat() for t in missing],
            "unsupported_sessions": unsupported, "offgrid": offgrid,
            "segments": dict(counts), "zero_volume_by_segment": dict(zeros),
            "first": rows[0]["t"] if rows else None, "last": rows[-1]["t"] if rows else None,
            "missing_semantics": "UNKNOWN_UNAVAILABLE_NEVER_FILLED",
            "zero_semantics": "PRESENT_REPORTED_ZERO_NOT_MISSING_OR_NO_TRADE_PROOF"}


def main():
    client = Client()
    report = {"schema": "alpaca_basic_actual_admission_probes_v1", "feed": "sip",
              "scope": "BOUNDED_PROVIDER_ADMISSION_NOT_DATASET", "outcomes": "NOT_RUN", "cases": {}}
    cases = [
        ("earliest", "2010-01-01T00:00:00Z", "2016-01-06T01:00:00Z", 10000),
        ("old-2016", "2016-01-04T09:00:00Z", "2016-01-05T01:00:00Z", 10000),
        ("winter-dst", "2025-03-07T09:00:00Z", "2025-03-08T01:00:00Z", 10000),
        ("summer-dst", "2025-03-10T08:00:00Z", "2025-03-11T00:00:00Z", 7),
        ("early-close", "2025-11-28T09:00:00Z", "2025-11-29T01:00:00Z", 10000),
        ("recent-complete", "2026-10-01T08:00:00Z", "2026-10-02T00:00:00Z", 10000),
    ]
    try:
        if "--depth" in sys.argv[1:]:
            for identity, start, end in [("2026-Q2", "2026-04-01", "2026-07-01"), ("2026-Q3-plus", "2026-07-01", "2026-10-03")]:
                result = client.bars(identity, start + "T04:00:00Z", end + "T03:59:59Z")
                report["cases"][identity] = {**result, "grid": grid(result["rows"], start, end)}
            return
        if "--supplement" in sys.argv[1:]:
            supplement(client, report)
            return
        for identity, start, end, limit in cases:
            result = client.bars(identity, start, end, limit=limit)
            day = start[:10] if identity != "earliest" else "2016-01-04"
            next_day = (datetime.fromisoformat(day) + timedelta(days=1)).date().isoformat()
            report["cases"][identity] = {**result, "grid": grid(result["rows"], day, "2016-01-06" if identity == "earliest" else next_day)}
        repeated = client.bars("summer-repeat", cases[3][1], cases[3][2])
        report["pagination_repeat_equal"] = repeated["rows"] == report["cases"]["summer-dst"]["rows"]
        for timeframe in ("15Min", "1Day"):
            for adj in ("raw", "split"):
                identity = "split-" + timeframe + "-" + adj
                report["cases"][identity] = client.bars(identity, "2024-03-06T09:00:00Z", "2024-03-09T01:00:00Z", timeframe, adj)
        report["actions"] = client.get("corporate-actions", "/v1/corporate-actions", {"symbols": "SOXX", "start": "2016-01-01", "end": "2026-10-03", "limit": 1000})
    except ProviderFailure as exc:
        report["failure"] = str(exc)
    finally:
        report["requests"] = client.records
        data = encode(report)
        write_new(ROOT / ("probes-" + sha256(data).hexdigest() + ".json"), data)
    print(json.dumps({"cases": list(report["cases"]), "failure": report.get("failure"),
                      "pagination_repeat_equal": report.get("pagination_repeat_equal")}), flush=True)
    if any(r["transport"].startswith("TRANSPORT_FAILURE") for r in client.records):
        raise SystemExit(2)


def supplement(client, report):
    """Predeclared price/coverage probes only; no candidate or outcome selection."""
    windows = [("2024-01", "2024-01-02", "2024-02-03"),
               ("2025-07", "2025-07-01", "2025-08-02"),
               ("2026-01", "2026-01-02", "2026-02-03"),
               ("2026-07", "2026-07-01", "2026-08-02")]
    report["predeclared_windows"] = windows
    for identity, start, end in windows:
        result = client.bars(identity, start + "T05:00:00Z", end + "T04:00:00Z")
        report["cases"][identity] = {**result, "grid": grid(result["rows"], start, end)}
    for timeframe in ("15Min", "1Day"):
        for adj in ("raw", "split"):
            identity = "unit-full-" + timeframe + "-" + adj
            report["cases"][identity] = client.bars(identity, "2024-03-06T05:00:00Z", "2024-03-09T04:59:59Z", timeframe, adj)
    for timeframe in ("1Min", "15Min", "1Day"):
        identity = "volume-" + timeframe
        report["cases"][identity] = client.bars(identity, "2025-03-10T04:00:00Z", "2025-03-11T03:59:59Z", timeframe)
    # An absent15m slot can contain odd-lot/ineligible trades; it is not volume0.
    report["missing-slot-trades"] = client.get("missing-slot-trades", "/v2/stocks/SOXX/trades", {
        "start": "2025-03-10T23:45:00Z", "end": "2025-03-10T23:59:59Z", "feed": "sip", "limit": 10000, "sort": "asc"})
    report["actions-small-pages"] = action_pages(client)


def action_pages(client):
    params = {"symbols": "SOXX", "start": "2016-01-01", "end": "2026-10-03", "limit": 7}
    groups, seen, current, pages = {}, set(), dict(params), 0
    while True:
        payload = client.get("actions-pagination", "/v1/corporate-actions", current)
        if not isinstance(payload.get("corporate_actions"), dict) or "next_page_token" not in payload:
            raise ProviderFailure("Malformed action pagination")
        for kind, rows in payload["corporate_actions"].items():
            if not isinstance(rows, list):
                raise ProviderFailure("Malformed action group")
            for row in rows:
                if row.get("symbol") != "SOXX" or row.get("id") in seen:
                    raise ProviderFailure("Wrong symbol/duplicate action")
                seen.add(row["id"])
                groups.setdefault(kind, []).append(row)
        pages += 1
        token = payload["next_page_token"]
        if token is None:
            return {"corporate_actions": groups, "pages": pages, "next_page_token": None}
        if not isinstance(token, str) or not token or token in seen:
            raise ProviderFailure("Action pagination cycle")
        seen.add(token)
        current = {**params, "page_token": token}


if __name__ == "__main__":
    main()
