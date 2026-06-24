# CLAUDE.md

Short operating guide for Claude Code and Claude Desktop sessions working in this
repository. Keep it current and compact. Put long history in `docs/`.

## Project north star

`mmm-search-mcp` turns Google Trends per-country search demand into a small,
read-only data product for marketing-mix-modeling (MMM) target-market analysis.
It has one cost-bearing component (the collector) and two read components (a
static grid and an MCP server) that share a cached JSON file.

The guiding invariant: **only the collector calls SerpApi.** Everything else
reads `data/data.json`. This is the cost firewall and a large part of the
security posture.

## Read first

1. `CLAUDE.md` or `AGENTS.md` for agent rules.
2. `AI_START_HERE.md` when onboarding a user or first-run agent.
3. `docs/architecture.md` for the module map and data contracts.
4. `docs/security.md` for the threat model and the boundaries to preserve.

## Dev environment

The collector uses only the standard library. The MCP server needs `fastmcp`.

```bash
python -m pip install -r requirements.txt
python -m collector.fetch_data        # needs SERPAPI_KEY in env/.env
python -m mcp_server.server           # runs the read-only MCP server
```

Useful checks:

```bash
python -c "from collector.config import DEFAULT_CONFIG as c; print(c.projected_monthly_calls(), c.within_budget())"
python -c "from collector.fetch_data import build_records; print('ok')"
```

## Current MCP tool surface

Source of truth: `mcp_server/server.py`. All tools are read-only.

- Readiness: `config_doctor`
- Read: `get_search_data`, `get_top_markets`, `get_continent_summary`

There are intentionally NO write, refresh, or send tools. See Architecture rules.

## Architecture rules

- Only `collector/fetch_data.py` may call SerpApi. The MCP server and UI read
  `data/data.json` only.
- The data source lives behind one adapter function:
  `fetch_interest_by_country()`. Swap data providers there, nowhere else.
- Cache writes are atomic (`os.replace`). On any fetch error, the collector
  leaves the existing cache unchanged — a stale-but-valid cache beats a broken
  one.
- The MCP server exposes a whitelist of structured fields only
  (`_sanitize_country`). No free-text field from an external source reaches the
  model. Do not widen this to pass related-queries or other free text into tool
  output without re-sanitizing.
- Do not add a side-effect tool (refresh, send, write). Keeping the MCP surface
  read-only is what removes the cost channel and the exfiltration channel.
- Secrets (SERPAPI_KEY) come from the environment only. Never hard-code,
  never log, never write them into `data/` or `docs/`.

## Cost rules

- Free-tier budget: 250 successful searches/month (SerpApi free plan, confirmed
  2026-06-24; 50/hour throughput).
- Projected usage = keywords x periods x refreshes_per_day x 30. Keep it under
  budget in `collector/config.py`.
- The collector warns (does not hard-fail) when over budget; the real ceiling is
  cron cadence. Do not add UI/MCP code paths that call the collector.

## Do not

- Do not call SerpApi from the MCP server or the browser.
- Do not add outbound/send tools.
- Do not print or persist secrets.
- Do not pass unsanitized external free-text into MCP tool output.
- Do not over-refresh: match cadence to how fast the data actually changes.
- Do not name a Python package `mcp` (it shadows the upstream `mcp` package).
  This repo uses `mcp_server/`.

## Customization & license

MIT-licensed. Prefer small explicit changes. Record meaningful local
modifications in `docs/` so future agents understand what changed. The most
common customization is swapping the data source at the adapter seam or adding
keywords in `collector/config.py` (mind the quota math).

See `docs/extending.md` for the adapter seam and customization paths, and
`docs/tool-surfaces.md` for the read-only MCP surface vs the hidden dev admin
CLI (`collector/admin.py`).
