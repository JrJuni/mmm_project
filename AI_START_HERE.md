# AI Start Here

This is the first-run guide for an AI agent helping a user set up and operate
`mmm-search-mcp` — a read-only MCP server that surfaces Google Trends per-country
search demand for a tracked keyword (default: Arencia), for marketing-mix
modeling (MMM) target-market analysis.

Read this before deeper docs. For architecture detail see
[`docs/architecture.md`](docs/architecture.md). For agent operating rules see
[`AGENTS.md`](AGENTS.md) / [`CLAUDE.md`](CLAUDE.md).

## What this is

A three-layer pipeline with a strict cost/security boundary:

1. **Collector** (`collector/fetch_data.py`) — the ONLY component that calls
   SerpApi. Run on a schedule (cron). Writes `data/data.json`.
2. **Static grid** (`web/index.html`) — reads the cache, renders a 4-column
   country grid colored by continent / interest / week-over-week change.
   Refresh button re-reads the cache; it never calls SerpApi.
3. **MCP server** (`mcp_server/server.py`) — read-only tools over the cache so
   the user can ask questions in their existing chat client.

The key invariant: **only the collector spends SerpApi quota.** The UI and MCP
read the cache, so their call volume is free and unbounded. Billable usage is
fixed by cron cadence.

## Default decision

Start the user in **read-only operation**:

- The MCP server exposes no side-effect tools. Nothing for prompt injection to
  trigger, no cost channel, no exfiltration channel.
- Data refresh is a scheduled job, not a chat-triggered action. If the user
  wants on-demand refresh, that is a private admin path (run the collector
  directly), not an MCP tool.

Do not add an outbound/send tool or a tool that calls SerpApi directly. Doing so
would create the cost and exfiltration channels this design deliberately avoids.

## First run for a user

Explain the pieces in plain language before any commands:

- A SerpApi account and free-tier API key (1 keyword / daily refresh fits the
  250 searches/month free budget).
- Python 3.11+ to run the collector and the MCP server.
- An MCP client (Claude Desktop, Codex/ChatGPT) to use the read tools.

Use this prompt if the user asks what to prepare:

```text
For the normal setup, prepare three things:
1. a SerpApi account and free API key,
2. Python 3.11+ on your machine,
3. an MCP client such as Claude Desktop.

The free SerpApi tier covers one keyword refreshed once a day. You only pay if
you track more keywords or refresh more often.
```

### Secrets

Do not ask the user to paste the SerpApi key into chat. It goes in a local
`.env` file (see `.env.example`) or the MCP client's config form. In the SerpApi
dashboard, name/alias the key so usage is monitorable per key.

### Install

```bash
# 1. get the code
git clone https://github.com/JrJuni/mmm_project
cd mmm_project

# 2. install (collector needs no third-party deps; MCP needs fastmcp)
python -m pip install -r requirements.txt

# 3. configure the key locally
cp .env.example .env
# edit .env, set SERPAPI_KEY

# 4. first collection (.env is loaded automatically; a real env var still wins)
python -m collector.fetch_data

# 5. open the grid
#    serve the repo root over http so the grid can fetch ../data/data.json, e.g.:
python -m http.server 8000
# then open http://localhost:8000/web/index.html
```

Without a key, the UI still renders from `data/data.sample.json` if you copy it
to `data/data.json` — useful for a no-cost product-shape check.

### Schedule collection

Daily refresh keeps 1 keyword within the free budget. Example cron (see
`crontab.example` for the full version with Windows Task Scheduler + manual
refresh notes):

```cron
0 6 * * * cd /path/to/mmm_project && /usr/bin/python -m collector.fetch_data >> collect.log 2>&1
```

### Connect the MCP server

Point your MCP client at:

```bash
python -m mcp_server.server
```

After connecting, ask the assistant to run `config_doctor` first.

### Changing the keyword or which countries show (dev/admin)

These are developer actions via the CLI `collector/admin.py` — never MCP:

```bash
python -m collector.admin set-keyword "YourBrand"   # then run: refresh
python -m collector.admin select US KR JP           # show exactly these
python -m collector.admin clear-select              # back to the default view
```

The grid defaults to the 12 largest economies. Collection changes (keyword/geo)
re-fetch; selection changes are display-only and cost no quota. See
`docs/tool-surfaces.md`.

## First useful questions

Once the cache exists:

```text
Run config_doctor and tell me if the search-demand cache is ready and fresh.
Which countries have the highest Arencia search interest right now?
Summarize search demand by continent.
Which markets are growing the fastest week over week?
```

## Tool selection defaults

All tools are read-only. Prefer the most specific:

- Readiness / freshness check -> `config_doctor`
- Full per-country table -> `get_search_data`
- Target-market shortlist (top N) -> `get_top_markets`
- Demand concentration by region -> `get_continent_summary`

## Cost & quota notes

- Free tier budget: 250 successful searches/month (SerpApi free plan, confirmed
  2026-06-24; 50/hour throughput).
- 1 keyword x 2 periods (current/previous week) x 1 refresh/day x 30 = ~60/month.
- Raising keyword count or refresh frequency is what pushes past the free tier.
  See `collector/config.py` (`projected_monthly_calls`, `within_budget`).
- The UI refresh button and every MCP call cost zero SerpApi quota.

## Do not

- Do not add an MCP tool that calls SerpApi or sends data outward.
- Do not paste the SerpApi key into chat or commit `.env`.
- Do not pass free-text fields from search results into the model unsanitized;
  the MCP server already whitelists structured fields only (see
  `_sanitize_country`). Keep that boundary.
- Do not refresh more often than the data actually changes (Trends is weekly-ish;
  Keyword Planner is monthly). Over-refreshing burns quota for no new signal.

## Customization & license

MIT-licensed. The data source is behind a single adapter seam
(`fetch_interest_by_country` in `collector/fetch_data.py`): swap it to use the
official Google Trends API (alpha), Glimpse (absolute volume), or Keyword
Planner without touching the UI or MCP layers. Keep license/attribution on
redistribution.
