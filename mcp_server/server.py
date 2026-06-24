"""mmm-search-mcp: a read-only MCP server over the Arencia search-demand cache.

This server NEVER calls SerpApi. It only reads the cached `data/data.json` that
the collector (run by cron) produces. Consequences:

- No side-effect tools  -> nothing for prompt injection to trigger.
- No cost channel        -> tool calls cannot spend SerpApi quota.
- No exfiltration channel -> there is no tool that sends data outward.
- No private data        -> the cache holds public aggregate search stats only.

Together these mean the "lethal trifecta" (private data + untrusted content +
exfiltration) cannot form here. Keep it that way: do not add an outbound/send
tool, and do not add a tool that calls SerpApi directly.

Run:
    python -m mcp.mcp_server
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastmcp import FastMCP

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "data.json"

mcp = FastMCP("mmm-search-mcp")


# --------------------------------------------------------------------------
# Internal helpers
# --------------------------------------------------------------------------
def _load_cache() -> dict[str, Any] | None:
    if not DATA_FILE.exists():
        return None
    try:
        with DATA_FILE.open(encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


# Whitelist of fields we expose to the LLM. Restricting to structured,
# machine-typed fields (codes, ints) is the injection-isolation boundary:
# no free-text field from an external source reaches the model's reasoning.
_SAFE_FIELDS = ("country_code", "continent", "interest", "prev_interest", "change_pct")


def _sanitize_country(row: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k in _SAFE_FIELDS:
        v = row.get(k)
        # Country code is the only string; constrain it hard to A-Z, len<=3.
        if k == "country_code":
            v = str(v or "")[:3].upper()
            if not v.isalpha():
                v = ""
        out[k] = v
    return out


def _staleness_hours(updated_at: str) -> float | None:
    try:
        ts = datetime.fromisoformat(updated_at)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return round((datetime.now(timezone.utc) - ts).total_seconds() / 3600, 1)
    except (ValueError, TypeError):
        return None


# --------------------------------------------------------------------------
# Tools (all read-only)
# --------------------------------------------------------------------------
@mcp.tool()
def config_doctor() -> dict[str, Any]:
    """Check whether the search-demand cache is present, readable, and fresh.

    Returns a readiness summary. Run this first when onboarding or debugging.
    Does not call any external API.
    """
    cache = _load_cache()
    if cache is None:
        return {
            "ready": False,
            "cache_present": DATA_FILE.exists(),
            "hint": (
                "No readable cache. Run `python -m collector.fetch_data` "
                "(needs SERPAPI_KEY in .env), or check data/data.json."
            ),
        }
    meta = cache.get("meta", {})
    stale = _staleness_hours(meta.get("updated_at", ""))
    return {
        "ready": True,
        "keyword": meta.get("keyword"),
        "geo": meta.get("geo"),
        "source": meta.get("source"),
        "country_count": meta.get("country_count"),
        "updated_at": meta.get("updated_at"),
        "staleness_hours": stale,
        "note": (
            "Read-only cache. Refresh cadence is controlled by cron, not by "
            "this server."
        ),
    }


@mcp.tool()
def get_search_data() -> dict[str, Any]:
    """Return the full cached per-country search interest for the tracked keyword.

    Fields per country: country_code, continent, interest (0-100),
    prev_interest, change_pct. All values are structured/sanitized; no
    free-text from external sources is included.
    """
    cache = _load_cache()
    if cache is None:
        return {"error": "cache_unavailable", "countries": []}
    meta = cache.get("meta", {})
    return {
        "keyword": meta.get("keyword"),
        "geo": meta.get("geo"),
        "updated_at": meta.get("updated_at"),
        "staleness_hours": _staleness_hours(meta.get("updated_at", "")),
        "countries": [_sanitize_country(r) for r in cache.get("countries", [])],
    }


@mcp.tool()
def get_top_markets(n: int = 5) -> dict[str, Any]:
    """Return the top N countries by current search interest (target shortlist).

    Useful for: "which markets should we prioritize for Arencia?" The cache is
    already sorted by interest; this trims to N.
    """
    n = max(1, min(int(n), 50))
    cache = _load_cache()
    if cache is None:
        return {"error": "cache_unavailable", "markets": []}
    rows = [_sanitize_country(r) for r in cache.get("countries", [])][:n]
    return {
        "keyword": cache.get("meta", {}).get("keyword"),
        "count": len(rows),
        "markets": rows,
    }


@mcp.tool()
def get_continent_summary() -> dict[str, Any]:
    """Aggregate current interest by continent.

    Returns total and average interest per continent, plus how many tracked
    countries fall in each. Good for a quick "where is demand concentrated?"
    """
    cache = _load_cache()
    if cache is None:
        return {"error": "cache_unavailable", "continents": {}}
    buckets: dict[str, list[int]] = {}
    for r in cache.get("countries", []):
        cont = r.get("continent") or "Unknown"
        buckets.setdefault(cont, []).append(int(r.get("interest") or 0))
    summary = {
        cont: {
            "country_count": len(vals),
            "total_interest": sum(vals),
            "avg_interest": round(sum(vals) / len(vals)) if vals else 0,
        }
        for cont, vals in buckets.items()
    }
    ranked = dict(
        sorted(summary.items(), key=lambda kv: kv[1]["total_interest"], reverse=True)
    )
    return {"keyword": cache.get("meta", {}).get("keyword"), "continents": ranked}


if __name__ == "__main__":
    mcp.run()
