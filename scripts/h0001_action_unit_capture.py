"""Capture public audit sources without assigning historical strategy clocks."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
import sys
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from richping.core import canonical

ROOT = Path("research/data_evidence/h0001-action-unit-20261003")
SOURCES = {
    "issuer-2024-release": "https://www.ishares.com/us/literature/press-release/stock-split-press-release-2023.pdf",
    "issuer-2024-tax": "https://www.ishares.com/us/literature/tax-information/form-8937-ishares-semiconductor-etf-3-6-2024.pdf",
    "issuer-2026-filing": "https://www.sec.gov/Archives/edgar/data/1100663/000119312526361162/d133118d497.htm",
    "issuer-product": "https://www.ishares.com/us/products/239705/ishares-phlx-semiconductor-etf",
    "issuer-history": "https://www.blackrock.com/varnish-api/blk-one01-product-data/product-data/api/v1/get-fund-document?appSubType=ISHARES&appType=PRODUCT_PAGE&component=fundDownload&locale=en_US&portfolioId=239705&targetSite=us-ishares&userType=individual",
    "nasdaq-history": "https://api.nasdaq.com/api/quote/SOXX/historical?assetclass=etf&fromdate=2024-10-04&todate=2026-10-02&limit=5000",
    "twelvedata-splits": "https://twelvedata.com/markets/256481/etf/nasdaq/soxx/historical-data/splits",
    "twelvedata-prices": "https://twelvedata.com/markets/256481/etf/nasdaq/soxx/historical-data",
    "shareprices-history": "https://shareprices.com/us/soxx/history/",
}


def capture(item):
    name, url = item
    started = datetime.now(timezone.utc).isoformat()
    try:
        with urlopen(Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "*/*"}), timeout=20) as r:
            status, body, content_type = r.status, r.read(), r.headers.get("Content-Type")
    except HTTPError as e:
        status, body, content_type = e.code, e.read(), e.headers.get("Content-Type")
    except Exception as e:
        return {"identity": name, "url": url, "started_at": started, "error": str(e)}
    h = sha256(body).hexdigest()
    path = ROOT / "sources" / (name + "-" + h + ".bin")
    if not path.exists():
        with path.open("xb") as f:
            f.write(body)
    return {"identity": name, "url": url, "started_at": started,
            "captured_at": datetime.now(timezone.utc).isoformat(), "http_status": status,
            "content_type": content_type, "sha256": h, "path": path.as_posix(), "bytes": len(body)}


def main():
    (ROOT / "sources").mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=9) as pool:
        selected = {k: v for k, v in SOURCES.items() if not sys.argv[1:] or k in sys.argv[1:]}
        results = list(pool.map(capture, selected.items()))
    body = canonical({"schema_version": "public_source_capture_v1", "sources": results})
    path = ROOT / ("source-capture-" + sha256(body.encode()).hexdigest() + ".json")
    with path.open("x", encoding="utf-8") as f:
        f.write(body)
    print(body)


if __name__ == "__main__":
    main()
