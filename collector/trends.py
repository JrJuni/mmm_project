"""Trend-index time series (interest over time) for the tracked keyword(s).

Separate from the GEO_MAP collector (`fetch_data.py`) on purpose: this fetches
`data_type=TIMESERIES` at several horizons and has its own (slower) cadence.

Multi-keyword: SerpApi google_trends compares up to 5 comma-separated queries in
ONE call, co-normalized to a shared 0-100 scale — perfect for comparing
companies. So the worldwide series for N keywords is still 1 call per horizon.

Cost note: the *global* (worldwide) series at 5 horizons is 5 calls regardless of
keyword count. Per-country series for every horizon would be quota-prohibitive on
the free tier, so for now per-country series are SYNTHETIC placeholders derived
from the global shape. They are clearly flagged and must NEVER be treated as real
data or exposed via MCP.

Writes `data/trends.json`:
    {
      "meta": {"keywords": [...], "updated_at", "horizons", "note"},
      "global":     {"3m": {"source", "start_ts", "end_ts",
                            "series": {kw: [points]}}, ...},   # REAL, co-normalized
      "by_country": {"US": {"synthetic": true,
                            "3m": {kw: [points]}, ...}, ...}    # SYNTHETIC
    }
"""

from __future__ import annotations

import json
import os
import random
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from .config import DEFAULT_CONFIG, serpapi_key
from .fetch_data import FetchError

SERPAPI_ENDPOINT = "https://serpapi.com/search.json"
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
TRENDS_FILE = DATA_DIR / "trends.json"
DATA_FILE = DATA_DIR / "data.json"

# Horizon label -> SerpApi google_trends `date` value (verified against the API).
HORIZONS: dict[str, str] = {
    "1d": "now 1-d",
    "1w": "now 7-d",
    "1m": "today 1-m",
    "3m": "today 3-m",
    "1y": "today 12-m",
}

MAX_KEYWORDS = 5  # SerpApi google_trends comparison cap


def _ts(pt: dict) -> int | None:
    try:
        return int(pt.get("timestamp"))
    except (TypeError, ValueError):
        return None


def fetch_timeseries(
    keywords: list[str], api_key: str, geo: str = ""
) -> dict[str, dict]:
    """Return {horizon: {"start_ts", "end_ts", "series": {kw: [0-100, ...]}}}.

    One SerpApi call per horizon compares all keywords, co-normalized. Real data.
    """
    q = ",".join(keywords)
    out: dict[str, dict] = {}
    for label, date in HORIZONS.items():
        params = {
            "engine": "google_trends",
            "q": q,
            "data_type": "TIMESERIES",
            "date": date,
            "api_key": api_key,
        }
        if geo:
            params["geo"] = geo
        url = f"{SERPAPI_ENDPOINT}?{urlencode(params)}"
        try:
            with urlopen(url, timeout=30) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except HTTPError as exc:
            raise FetchError(f"SerpApi HTTP {exc.code} for TIMESERIES '{label}'") from exc
        except (URLError, TimeoutError) as exc:
            raise FetchError(f"SerpApi network error for '{label}': {exc}") from exc
        if "error" in payload:
            raise FetchError(f"SerpApi error for '{label}': {payload['error']}")
        timeline = payload.get("interest_over_time", {}).get("timeline_data", [])
        series: dict[str, list[int]] = {kw: [] for kw in keywords}
        for pt in timeline:
            vals = pt.get("values") or []
            for i, kw in enumerate(keywords):
                v = vals[i].get("extracted_value") if i < len(vals) else 0
                series[kw].append(int(v or 0))
        out[label] = {
            "start_ts": _ts(timeline[0]) if timeline else None,
            "end_ts": _ts(timeline[-1]) if timeline else None,
            "series": series,
        }
    return out


def synthesize_country_series(
    global_series: dict[str, dict], countries: list[dict]
) -> dict[str, dict]:
    """Derive PLACEHOLDER per-country series (per keyword) from the global shape.

    NOT real data. A deterministic per-country scale + shift is applied to ALL
    keywords of that country together, so the keywords stay comparable within the
    tile (co-normalized). Flagged `synthetic: true`.
    """
    result: dict[str, dict] = {}
    for c in countries:
        code = c["country_code"]
        rnd = random.Random(sum(ord(ch) for ch in code))  # stable per code
        scale = 0.55 + 0.9 * rnd.random()
        shift = rnd.randint(-12, 12)
        entry: dict = {"synthetic": True}
        for horizon, kwseries in global_series.items():
            entry[horizon] = {
                kw: [max(0, min(100, round(v * scale + shift + rnd.randint(-7, 7))))
                     for v in pts]
                for kw, pts in kwseries.items()
            }
        result[code] = entry
    return result


def _write_atomic(doc: dict, path: Path = TRENDS_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def build(cfg=DEFAULT_CONFIG) -> dict:
    api_key = serpapi_key()
    if not api_key:
        raise FetchError("SERPAPI_KEY is not set. Put it in .env or the environment.")
    keywords = list(cfg.keywords)[:MAX_KEYWORDS]

    # Real worldwide series, co-normalized across keywords (5 calls).
    global_raw = fetch_timeseries(keywords, api_key, geo=cfg.geo)
    global_block = {
        h: {"source": "serpapi:google_trends:TIMESERIES", **b}
        for h, b in global_raw.items()
    }
    global_series = {h: b["series"] for h, b in global_raw.items()}

    # Synthetic per-country placeholders for the displayed countries.
    selected = cfg.selected_countries or []
    countries: list[dict] = []
    if DATA_FILE.exists():
        try:
            pool = json.loads(DATA_FILE.read_text("utf-8")).get("countries", [])
            by = {r["country_code"]: r for r in pool}
            countries = [by[c] for c in selected if c in by]
        except (json.JSONDecodeError, OSError):
            countries = [{"country_code": c, "interest": 50} for c in selected]
    else:
        countries = [{"country_code": c, "interest": 50} for c in selected]

    return {
        "meta": {
            "keywords": keywords,
            "geo": cfg.geo or "worldwide",
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "horizons": list(HORIZONS.keys()),
            "note": "global series are REAL and co-normalized across keywords; "
                    "by_country series are SYNTHETIC placeholder data (tester "
                    "only) — never treat as real or expose via MCP.",
        },
        "global": global_block,
        "by_country": synthesize_country_series(global_series, countries),
    }


def main() -> int:
    cfg = DEFAULT_CONFIG
    try:
        doc = build(cfg)
    except FetchError as exc:
        print(f"[error] trends collection aborted: {exc}", file=sys.stderr)
        print("[info] existing trends.json left unchanged.", file=sys.stderr)
        return 1
    _write_atomic(doc)
    print(
        f"[ok] wrote trends for {doc['meta']['keywords']}: "
        f"{len(doc['global'])} real global horizons, "
        f"{len(doc['by_country'])} synthetic country series"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
