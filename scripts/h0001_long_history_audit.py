"""Explicit, bounded provider audit. No ingestion, strategy or outcome execution.

Network probes and pure grid diagnostics are deliberately separate. Snapshots
are evidence of current access, never certificates of historical PIT delivery.
"""

from collections import Counter
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import sys

from richping.research_v2.real_data import expected_slots, request
from richping.research_v2.sessions import NY, segment


CREDENTIAL_NAMES = {
    "alpaca": ("APCA_API_KEY_ID", "APCA_API_SECRET_KEY", "ALPACA_API_KEY", "ALPACA_SECRET_KEY"),
    "massive": ("MASSIVE_API_KEY", "POLYGON_API_KEY"),
    "databento": ("DATABENTO_API_KEY",),
    "twelvedata": ("TWELVEDATA_API_KEY", "TWELVE_DATA_API_KEY"),
    "tiingo": ("TIINGO_API_KEY", "TIINGO_TOKEN"),
    "alphavantage": ("ALPHA_VANTAGE_API_KEY", "ALPHAVANTAGE_API_KEY"),
    "eodhd": ("EODHD_API_KEY",),
}

DOCUMENTS = {
    "alpaca-plans": "https://docs.alpaca.markets/us/docs/about-market-data-api.md",
    "alpaca-bars": "https://docs.alpaca.markets/us/reference/stockbars.md",
    "alpaca-faq": "https://docs.alpaca.markets/us/docs/market-data-faq.md",
    "alpaca-actions": "https://docs.alpaca.markets/us/reference/corporateactions-1.md",
    "massive-bars": "https://massive.com/docs/rest/stocks/aggregates/custom-bars.md",
    "massive-splits": "https://massive.com/docs/rest/stocks/corporate-actions/splits.md",
    "massive-units": "https://massive.com/knowledge-base/article/is-massives-stock-data-adjusted-for-splits-or-dividends",
    "massive-plans": "https://massive.com/pricing?product=stocks",
    "databento-mini": "https://databento.com/docs/venues-and-datasets/equs-mini",
    "databento-schemas": "https://databento.com/docs/knowledge-base",
    "databento-actions": "https://databento.com/docs/schemas-and-data-formats/corporate-actions",
    "databento-plans": "https://databento.com/pricing/",
    "twelve-extended": "https://support.twelvedata.com/en/articles/5195429-pre-post-market-data",
    "twelve-volume": "https://support.twelvedata.com/en/articles/9935903-us-equities-market-data",
    "twelve-pagination": "https://support.twelvedata.com/en/articles/5214728-getting-historical-data",
}


def credential_inventory(environ):
    """Persist only booleans for recognized names; never values or hashes."""
    return {provider: {name: bool(environ.get(name)) for name in names}
            for provider, names in CREDENTIAL_NAMES.items()}


def grid_diagnostic(capture):
    req = capture["request"]
    chart = capture["response"].get("chart", {})
    if chart.get("error") or not chart.get("result"):
        return {"status": "PROVIDER_ERROR_NOT_GRID_EVIDENCE", "error": chart.get("error")}
    result = chart["result"][0]
    times = result.get("timestamp", [])
    quotes = result.get("indicators", {}).get("quote", [])
    if len(quotes) != 1 or any(len(quotes[0].get(k, [])) != len(times)
                              for k in ("open", "high", "low", "close", "volume")):
        return {"status": "MALFORMED_ARRAYS"}
    expected, unsupported = expected_slots(req)
    expected = set(expected)
    seen = set()
    counts, zeros = Counter(), Counter()
    duplicates = unaligned = null_ohlc = null_volume = incomplete = 0
    captured = datetime.fromisoformat(capture["captured_at"])
    for i, epoch in enumerate(times):
        start = datetime.fromtimestamp(epoch, timezone.utc)
        end = start + timedelta(minutes=15)
        duplicates += start in seen
        seen.add(start)
        unaligned += start not in expected
        incomplete += end > captured
        null_ohlc += any(quotes[0][k][i] is None for k in ("open", "high", "low", "close"))
        null_volume += quotes[0]["volume"][i] is None
        # Early-close/out-of-grid rows remain reported, never normalized away.
        part = segment(start, end) if start in expected else "OUTSIDE_SUPPORTED_GRID"
        counts[part] += 1
        if quotes[0]["volume"][i] == 0:
            zeros[part] += 1
    missing = sorted(expected - seen)
    good = not (missing or unsupported or duplicates or unaligned or null_ohlc or null_volume or incomplete)
    return {"status": "COMPLETE_GRID_ONLY_NOT_ADMISSION" if good else "UNAVAILABLE",
            "expected_slots": len(expected), "observed_rows": len(times),
            "missing_count": len(missing), "missing_slots": [t.isoformat() for t in missing],
            "unsupported_sessions": unsupported, "duplicates": duplicates,
            "outside_supported_grid": unaligned, "null_ohlc_rows": null_ohlc,
            "null_volume_rows": null_volume, "incomplete_rows": incomplete,
            "segments": dict(counts), "zero_volume_by_segment": dict(zeros),
            "first_start": datetime.fromtimestamp(times[0], timezone.utc).isoformat() if times else None,
            "last_start": datetime.fromtimestamp(times[-1], timezone.utc).isoformat() if times else None,
            "actual_sessions": sorted({datetime.fromtimestamp(t, timezone.utc).astimezone(NY).date().isoformat()
                                       for t in times}),
            "zero_volume_interpretation": "PROVIDER_REPORTED_ZERO_NOT_PROOF_OF_NO_TRADING",
            "missing_interpretation": "UNKNOWN_NOT_ZERO_VOLUME_OR_PROVEN_MARKET_UNAVAILABLE"}


def write_new(path, data):
    """Immutable bytes: repeat identical write allowed, collision fails closed."""
    if path.exists():
        if path.read_bytes() != data:
            raise ValueError("Evidence collision")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as handle:
            handle.write(data)


def probe(root, identity, url, params=None, yahoo=False):
    from curl_cffi import requests
    started = datetime.now(timezone.utc).isoformat()
    try:
        if yahoo:
            from yfinance.data import YfData
            response = YfData().get(url=url, params=params, timeout=30)
        else:
            response = requests.get(url, params=params, timeout=30, impersonate="chrome")
        body = response.content
        status = response.status_code
        transport = "HTTP_RESPONSE"
    except Exception as exc:
        # Exception messages/URLs may contain secrets in other transports.
        body = json.dumps({"exception_type": type(exc).__name__}).encode()
        status, transport = None, "TRANSPORT_FAILURE_CAPABILITY_UNKNOWN"
    body_hash = sha256(body).hexdigest()
    path = root / "raw" / (body_hash + ".bin")
    write_new(path, body)
    record = {"id": identity, "requested_at": started,
              "captured_at": datetime.now(timezone.utc).isoformat(),
              "url": url, "params": params or {}, "authenticated": False,
              "http_status": status, "transport": transport,
              "path": path.as_posix(), "sha256": body_hash, "bytes": len(body)}
    try:
        payload = json.loads(body)
    except (ValueError, UnicodeDecodeError):
        payload = None
    if yahoo and payload is not None:
        record["provider_error"] = payload.get("chart", {}).get("error")
    return record, payload


def main():
    root = Path(sys.argv[1])
    root.mkdir(parents=True, exist_ok=True)
    if "--docs" in sys.argv[2:]:
        records = []
        for identity, url in DOCUMENTS.items():
            record, _ = probe(root, identity, url)
            records.append(record)
            print(json.dumps({"id": identity, "http_status": record["http_status"], "bytes": record["bytes"]}))
        data = (json.dumps({"scope": "PUBLIC_PRIMARY_DOCUMENTATION_NOT_ENTITLEMENT_EVIDENCE",
                            "sources": records}, indent=2, sort_keys=True) + "\n").encode()
        write_new(root / ("documentation-" + sha256(data).hexdigest() + ".json"), data)
        return
    inventory = credential_inventory(os.environ)
    if any(any(names.values()) for names in inventory.values()):
        raise ValueError("Recognized credential found: audit authorized feed explicitly; do not silently use unauthenticated probes")
    records = []
    # Boundaries and sparse historical spot checks only, never a bulk dataset.
    cases = [
        ("yahoo-earliest-15m", "2026-08-05", "2026-08-06", "15m"),
        ("yahoo-before-retention-15m", "2026-08-03", "2026-08-04", "15m"),
        ("yahoo-old-15m", "2025-03-10", "2025-03-11", "15m"),
        ("yahoo-completed-15m", "2026-10-01", "2026-10-02", "15m"),
        ("yahoo-latest-15m", "2026-10-02", "2026-10-03", "15m"),
        ("yahoo-old-1h", "2025-03-10", "2025-03-11", "60m"),
        ("yahoo-early-close-15m", "2025-11-28", "2025-11-29", "15m"),
        ("yahoo-split-daily-unit-spot", "2024-03-06", "2024-03-09", "1d"),
    ]
    from richping.research_v2.real_data import _midnight
    for identity, start, end, interval in cases:
        params = {"period1": int(_midnight(start).timestamp()), "period2": int(_midnight(end).timestamp()),
                  "interval": interval, "includePrePost": True, "events": "div,splits,capitalGains"}
        record, payload = probe(root, identity, "https://query1.finance.yahoo.com/v8/finance/chart/SOXX", params, True)
        record["requested_interval"] = [start, end]
        record["bar_interval"] = interval
        if payload and interval == "15m":
            record["grid"] = grid_diagnostic({"request": request("SOXX", start, end),
                                             "response": payload, "captured_at": record["captured_at"]})
        records.append(record)
        print(json.dumps({"id": identity, "http_status": record["http_status"], "error": record.get("provider_error"),
                          "grid": record.get("grid", {}).get("status")}))
    endpoints = [
        ("alpaca-sip-bars", "https://data.alpaca.markets/v2/stocks/SOXX/bars", {"timeframe": "15Min", "start": "2025-03-10T08:00:00Z", "end": "2025-03-11T00:00:00Z", "feed": "sip", "adjustment": "raw", "limit": 100}),
        ("alpaca-actions", "https://data.alpaca.markets/v1/corporate-actions", {"symbols": "SOXX", "start": "2024-01-01", "end": "2026-10-03", "limit": 1000}),
        ("massive-bars", "https://api.massive.com/v2/aggs/ticker/SOXX/range/15/minute/2025-03-10/2025-03-10", {"adjusted": "false", "sort": "asc", "limit": 100}),
        ("databento-access", "https://hist.databento.com/v0/metadata.list_datasets", {}),
        ("twelvedata-bars", "https://api.twelvedata.com/time_series", {"symbol": "SOXX", "interval": "15min", "start_date": "2025-03-10 04:00:00", "end_date": "2025-03-10 20:00:00", "timezone": "America/New_York", "prepost": "true", "adjust": "none", "outputsize": 100}),
    ]
    for identity, url, params in endpoints:
        record, payload = probe(root, identity, url, params)
        if isinstance(payload, dict):
            record["response_error"] = {key: payload[key] for key in ("code", "message", "status", "error") if key in payload}
        records.append(record)
        print(json.dumps({"id": identity, "http_status": record["http_status"], "transport": record["transport"]}))
    import yfinance
    report = {"schema": "h0001_long_history_network_probe_v1", "captured_at": datetime.now(timezone.utc).isoformat(),
              "credential_presence_process_environment": inventory, "yfinance_version": yfinance.__version__,
              "scope": "BOUNDED_READ_ONLY_CAPABILITY_PROBES_NOT_DATASET_CAPTURE", "probes": records,
              "strategy_execution": False, "outcomes": "NOT_RUN", "profitability": "NOT_RUN"}
    data = (json.dumps(report, sort_keys=True, indent=2) + "\n").encode()
    write_new(root / ("network-probes-" + sha256(data).hexdigest() + ".json"), data)


if __name__ == "__main__":
    main()
