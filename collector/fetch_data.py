"""Data collection layer for the Arencia search-demand monitor.

This is the ONLY component that calls SerpApi. Everything else (the static web
grid, the MCP server) reads the cached `data/data.json`. That separation is the
cost firewall: no matter how often the UI or the MCP tools are called, billable
SerpApi usage is fixed by how often THIS script runs (via cron).

Design notes
------------
- Adapter shape: `fetch_interest_by_country()` is the single seam. Today it
  calls SerpApi. When the official Google Trends API (alpha) opens up, or if you
  switch to Glimpse/Keyword Planner, replace only that function.
- Atomic writes: results are written to a temp file then os.replace()'d so a
  concurrent reader never sees a half-written file.
- Fail safe: on any fetch error (including 429), the existing cache is left
  intact. A stale-but-valid cache beats a broken one.
- No secrets in output: the cache stores data + meta only, never the API key.

Run:
    python -m collector.fetch_data
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import urlopen
from urllib.error import HTTPError, URLError

from .config import CollectorConfig, DEFAULT_CONFIG, serpapi_key
from .countries import continent_for

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_FILE = DATA_DIR / "data.json"
SERPAPI_ENDPOINT = "https://serpapi.com/search.json"


class FetchError(Exception):
    """Raised when a data source call fails in a way that should abort the run
    without overwriting the existing cache."""


# --------------------------------------------------------------------------
# Adapter seam: swap this function to change data source.
# --------------------------------------------------------------------------
def fetch_interest_by_country(
    keyword: str, timeframe: str, cfg: CollectorConfig, api_key: str
) -> dict[str, int]:
    """Return {country_code: interest_0_100} for one keyword + timeframe.

    Uses SerpApi's google_trends engine, GEO_MAP_0 (interest by region,
    single query), region=COUNTRY.
    """
    params = {
        "engine": "google_trends",
        "q": keyword,
        "data_type": "GEO_MAP_0",
        "region": "COUNTRY",
        "date": timeframe,
        "api_key": api_key,
    }
    if cfg.geo:
        params["geo"] = cfg.geo
    if cfg.include_low_search_volume:
        params["include_low_search_volume"] = "true"

    url = f"{SERPAPI_ENDPOINT}?{urlencode(params)}"
    try:
        with urlopen(url, timeout=30) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except HTTPError as exc:
        # 429 = rate limited / quota; treat as abort-without-overwrite.
        raise FetchError(f"SerpApi HTTP {exc.code} for '{keyword}'") from exc
    except (URLError, TimeoutError) as exc:
        raise FetchError(f"SerpApi network error for '{keyword}': {exc}") from exc

    if "error" in payload:
        raise FetchError(f"SerpApi error for '{keyword}': {payload['error']}")

    out: dict[str, int] = {}
    for row in payload.get("interest_by_region", []):
        code = (row.get("geo") or "").upper()
        # GEO_MAP_0 single-query rows expose extracted_value directly.
        val = row.get("extracted_value")
        if val is None:
            values = row.get("values") or []
            val = values[0].get("extracted_value") if values else 0
        if code:
            out[code] = int(val or 0)
    return out


# --------------------------------------------------------------------------
# Aggregation: build the cache document from raw per-period interest.
# --------------------------------------------------------------------------
def build_records(
    current: dict[str, int], previous: dict[str, int], cfg: CollectorConfig
) -> list[dict[str, Any]]:
    codes = set(current) | set(previous)
    records: list[dict[str, Any]] = []
    for code in codes:
        cur = current.get(code, 0)
        prev = previous.get(code, 0)
        if cur == 0 and prev == 0:
            continue
        change_pct = None
        if prev > 0:
            change_pct = round((cur - prev) / prev * 100)
        records.append(
            {
                "country_code": code,
                "continent": continent_for(code),
                "interest": cur,
                "prev_interest": prev,
                "change_pct": change_pct,
            }
        )
    records.sort(key=lambda r: r["interest"], reverse=True)
    return records[: cfg.top_n]


def collect(cfg: CollectorConfig = DEFAULT_CONFIG) -> dict[str, Any]:
    """Run one full collection pass and return the cache document.

    Does NOT write to disk; see write_cache(). Raises FetchError on any source
    failure so the caller can decide whether to preserve the old cache.
    """
    api_key = serpapi_key()
    if not api_key:
        raise FetchError(
            "SERPAPI_KEY is not set. Put it in .env or the environment. "
            "Never paste it into chat."
        )

    if not cfg.within_budget():
        # Soft guard: warn but proceed. The real ceiling is enforced by cron
        # cadence, not by this script.
        print(
            f"[warn] projected {cfg.projected_monthly_calls()} calls/month "
            f"exceeds budget {cfg.monthly_quota_budget}. Reduce keywords, "
            f"periods, or refreshes_per_day.",
            file=sys.stderr,
        )

    keyword = cfg.keywords[0]  # MVP tracks one primary keyword for the grid.
    current_tf, previous_tf = cfg.timeframes()
    current = fetch_interest_by_country(keyword, current_tf, cfg, api_key)
    previous: dict[str, int] = {}
    if cfg.periods_per_keyword >= 2:
        time.sleep(1)  # be polite between calls
        previous = fetch_interest_by_country(keyword, previous_tf, cfg, api_key)

    records = build_records(current, previous, cfg)
    return {
        "meta": {
            "keyword": keyword,
            "geo": cfg.geo or "worldwide",
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "source": "serpapi:google_trends:GEO_MAP_0",
            "periods": cfg.periods_per_keyword,
            "country_count": len(records),
        },
        "countries": records,
    }


def write_cache(doc: dict[str, Any], path: Path = DATA_FILE) -> None:
    """Atomically write the cache document to disk."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)  # atomic on POSIX and Windows
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def main() -> int:
    cfg = DEFAULT_CONFIG
    try:
        doc = collect(cfg)
    except FetchError as exc:
        # Preserve existing cache; do not overwrite with an error state.
        print(f"[error] collection aborted: {exc}", file=sys.stderr)
        print("[info] existing cache left unchanged.", file=sys.stderr)
        return 1
    write_cache(doc)
    print(
        f"[ok] wrote {doc['meta']['country_count']} countries for "
        f"'{doc['meta']['keyword']}' at {doc['meta']['updated_at']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
