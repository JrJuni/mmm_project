# mmm-search-mcp

A small, read-only data product that turns Google Trends per-country search
demand into a target-market view for marketing-mix modeling (MMM). Built for
small/medium businesses with little or no dev/tracking infrastructure.

One cost-bearing collector, two read surfaces (a static grid + an MCP server),
and a single cached JSON file between them.

## What it does

- Collects per-country search interest for your tracked keyword (set via the
  `MMM_KEYWORD` env var) from Google Trends via SerpApi.
- Caches it to `data/data.json` with current vs previous-week values and a
  week-over-week change.
- Renders a 4-column country grid (`web/index.html`) colored by **continent**,
  **search interest**, or **WoW change** — like a stock-ticker board, minus the
  size-by-value tile (deliberately dropped for readability).
- Exposes read-only MCP tools so you can ask questions in your existing chat
  client ("which markets lead?", "summarize by continent").

## What it is not

- Not absolute search volume. Google Trends gives a 0-100 relative index. For
  absolute per-country volume (better for picking target markets and for MMM
  regression inputs), swap the data source to Keyword Planner or Glimpse — the
  code has a single adapter seam for this.
- Not a real-time feed. Refresh cadence matches how fast the data changes
  (Trends is weekly-ish), set by cron.
- Not a write/automation system. The MCP surface is read-only by design.

## Architecture at a glance

```
cron ─▶ collector/fetch_data.py ─▶ data/data.json ─┬─▶ web/index.html (grid)
        (only SerpApi caller)        (cache)         └─▶ mcp_server/server.py (read-only tools)
```

Invariant: **only the collector calls SerpApi.** The grid and the MCP server
read the cache, so their usage is free and unbounded; billable usage is fixed by
how often cron runs. See [`docs/architecture.md`](docs/architecture.md).

## Why this shape

This grew out of a few hard constraints common to SMBs:

- `pytrends` is unmaintained (archived April 2025) and can return silently
  altered data when flagged as a bot — unsafe for an MMM regression input.
- The official Google Trends API is alpha and invite-only with tight quotas.
- Direct scraping is bot-blocked; paid APIs (SerpApi, Glimpse) exist to solve
  exactly that, with a free tier sufficient for one keyword.

So the design keeps the data source behind one swappable function, caches
aggressively to bound cost, and stays read-only to keep the security surface
minimal. See [`docs/security.md`](docs/security.md).

## Install

### Prerequisites

- Python 3.11+
- A SerpApi account + free API key (https://serpapi.com/manage-api-key)
- An MCP client (Claude Desktop, Codex/ChatGPT) for the read tools

### Steps

```bash
git clone https://github.com/JrJuni/mmm_project
cd mmm_project
python -m pip install -r requirements.txt

cp .env.example .env    # set SERPAPI_KEY and MMM_KEYWORD (your brand) — local only

python -m collector.fetch_data   # country grid + WoW  -> data/data.json   (2 calls)
python -m collector.trends       # Trend index series  -> data/trends.json (5 calls)
python -m collector.serve        # serve the grid + in-browser keyword editing
# open http://localhost:8000/web/index.html
```

`collector.serve` is a local dev server: it serves the static grid and lets the
"Companies" panel edit the compared keywords on demand (it is local/dev only and
never part of the shipped read-only surfaces). A plain `python -m http.server`
also works for viewing.

No key yet? The grid automatically falls back to the bundled `*.sample.json`, so
just serve and open it to preview with demo data.

### Schedule collection (cron, daily)

```cron
0 6 * * * cd /path/to/mmm_project && /usr/bin/python -m collector.fetch_data >> collect.log 2>&1
```

See [`crontab.example`](crontab.example) for the full version (Windows Task
Scheduler note + the manual-refresh path `python -m collector.admin refresh`).

### Connect the MCP server

```bash
python -m mcp_server.server
```

In your MCP client, point at that command. Then ask the assistant to run
`config_doctor` first.

## Tool guide

All tools are read-only and cost zero SerpApi quota.

### `config_doctor`
Checks that the cache exists, is readable, and how stale it is. Run first.

### `get_search_data`
Returns the full per-country table for the tracked keyword: `country_code`,
`continent`, `interest` (0-100), `prev_interest`, `change_pct`. Structured
fields only — no external free text reaches the model.

### `get_top_markets(n=5)`
Top N countries by current interest — a target-market shortlist.

### `get_continent_summary`
Total / average interest and country count per continent — "where is demand
concentrated?"

## Cost & free-tier math

```
monthly calls = keywords x periods x refreshes_per_day x 30
default       = 1        x 2       x 1                 x 30 = ~60
free budget   = 250 successful searches/month (SerpApi free plan)
```

What pushes you past the free tier: more keywords, or more frequent refresh.
The UI refresh button and all MCP calls are free. Tune in
`collector/config.py` (`projected_monthly_calls`, `within_budget`).

## Free-tier terms (SerpApi)

This project assumes SerpApi's free plan: **250 searches/month** (recurring) and
**50 searches/hour** throughput, per the [pricing page](https://serpapi.com/pricing)
(confirmed 2026-06-24). Always re-check the current terms yourself before relying
on them. See also [SerpApi's Terms](https://serpapi.com/legal).

- **Commercial use:** SerpApi's terms have no clause restricting the free plan
  to non-commercial use — the only free-tier-specific exclusion is the Legal
  Shield (below). Internal/product use of the returned data is permitted. If
  commercial certainty matters, confirm with `support@serpapi.com`.
- **No reselling raw data:** You may use the data inside your own product, but
  the terms (Section 2) prohibit reselling or redistributing the raw search
  results to third parties. This project never sends raw data outward — the MCP
  server is read-only and returns only sanitized, structured fields.
- **Caching is fine:** Storing results in `data/data.json` is allowed; the terms
  set no storage-duration limit. (Separately, SerpApi caches identical queries
  server-side for ~1h, billed as free.)
- **No Legal Shield on free/starter/developer:** SerpApi's up-to-$2M legal
  protection for lawful data *collection* (scraping/parsing of public data)
  applies only to higher paid plans, not the free tier, and never covers how the
  data is *used*. Low practical risk for internal use of public, aggregate
  search statistics; revisit before scaling or exposing data externally.

## Customization

Swap the data source at one function — `fetch_interest_by_country()` in
`collector/fetch_data.py`:

- Google Trends API (alpha) when access opens (free, consistently scaled index)
- Glimpse for absolute search volume (better MMM input; paid)
- Keyword Planner / DataForSEO for monthly absolute volume by country

Nothing downstream changes for an index-based swap.

## Which countries are shown

The collector stores **every** country Google Trends returns (~100+) as a pool
in `data/data.json`. The grid shows the top `display_n` (default 12) by interest,
or an explicit `selected_countries` list if set. Picking countries is a *display*
filter over the cached pool — it never calls SerpApi, so a rising market is
already in the cache and just needs to be shown.

Changing collection (the keyword, geo, cadence) or the selection is done with the
developer admin CLI — a terminal tool, deliberately **not** an MCP tool, so it
stays off the read-only surface:

```bash
python -m collector.admin show
python -m collector.admin select US KR JP AE   # show exactly these
python -m collector.admin clear-select         # back to top display_n
python -m collector.admin set-keyword "YourBrand"
python -m collector.admin refresh              # run a live collection now
```

It writes a gitignored `dev_overrides.json` that overrides the shipped defaults.

## FAQ

**Why is the tile size all the same?** Sizing tiles by a 0-100 relative index
misleads (it is not market cap). Color carries the signal instead; switch the
"Shade by" toggle for continent / interest / change.

**Can the assistant refresh the data?** No — by design. Refresh is a scheduled
job (or a private admin run of the collector), never an MCP tool. That keeps the
cost and exfiltration channels closed.

**Is the index good enough for MMM?** For monitoring and target selection, yes.
For regression inputs, absolute volume (Keyword Planner / Glimpse) is cleaner
because it avoids the relative-scale problem. The adapter seam makes that swap
local.

**Is my SerpApi key safe?** It lives in `.env` (gitignored) or your MCP client's
config form, never in chat or docs. Alias it in the SerpApi dashboard for
per-key monitoring.

## License

MIT. Keep license and attribution notices when redistributing modified versions.

---

한국어 안내는 [`README_ko.md`](README_ko.md)를 참고하세요.
