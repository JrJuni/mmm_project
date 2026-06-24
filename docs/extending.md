# Extending mmm-search-mcp

This project is small on purpose: one collector, one read-only MCP server, one
static grid, sharing a cached `data/data.json`. Most customization happens at a
single seam — the data-source adapter — without touching anything downstream.

Read `docs/architecture.md` (module map + data contract) and `docs/security.md`
(the invariants you must preserve) before changing anything. If a doc conflicts
with the code, prefer the source.

## Extension principles

- **Change the seam, not the pipeline.** Swap data providers at
  `fetch_interest_by_country()` only. The cache schema, grid, and MCP tools do
  not change for an index-based swap.
- **Keep the MCP surface read-only.** No write, refresh, or send tool. That is
  what removes the cost channel and the exfiltration channel (`docs/security.md`).
  Collection and config changes go through the dev admin CLI, never MCP.
- **Display is not collection.** Choosing which countries to show
  (`selected_countries`, `display_n`) filters the cached pool and costs no
  SerpApi quota. Only keyword/geo/cadence changes re-collect.
- **Sanitize external data into the model.** Only whitelisted, typed fields
  reach tool output (`_sanitize_country`). Never pass external free text through.
- **Secrets stay in the environment.** Never hard-code, log, or write
  `SERPAPI_KEY` into `data/`, `docs/`, tool output, or tests.

## Common customization paths

| Goal | Start here | Contract to keep | Validate with |
|---|---|---|---|
| Swap the data provider (Trends → Glimpse / Keyword Planner / DataForSEO / Trends alpha API) | `fetch_interest_by_country()` in `collector/fetch_data.py` | Return `{ISO_alpha2: int}`; raise `FetchError` on any failure (cache is preserved) | `smoke_test.py`, then a live `python -m collector.admin refresh` |
| Change the tracked keyword / geo / cadence | `collector/config.py`, or `python -m collector.admin set-keyword/set-geo` | Mind the quota math (`projected_monthly_calls`, `within_budget`) | `collector.admin show`, `config_doctor` |
| Change which countries are shown | `config.selected_countries` / `display_n`, or `admin select`/`clear-select` | Display filter only — never triggers SerpApi | grid footer, `get_search_data` |
| Widen the cache pool | `config.top_n` (`None` = keep all returned) | One call returns all countries; a bigger pool costs no extra quota | `country_count` in `data.json` meta |
| Change continent grouping / colors | `collector/countries.py` (`_COUNTRY_TO_CONTINENT`, `CONTINENT_RAMP`) | Keep labels matching the UI legend in `web/index.html` | `get_continent_summary`, grid continent mode |
| Add a read-only MCP tool | `mcp_server/server.py` | Must be read-only + sanitized; see checklist below and `docs/tool-surfaces.md` | `smoke_test.py`, manual tool call |
| Add a dev/admin operation | `collector/admin.py` | CLI only — never expose over MCP | `collector.admin <cmd>` |

## The adapter seam

```python
fetch_interest_by_country(keyword, timeframe, cfg, api_key) -> dict[str, int]
#   -> {country_code: interest_0_100}
```

This is the single point of coupling to the data source. A provider swap only
needs to honor this contract:

- Return ISO alpha-2 codes mapped to an integer. For a 0–100 relative index
  (Google Trends), nothing downstream changes. For absolute search volume
  (Glimpse / Keyword Planner), change the field *semantics* and the UI legend,
  not the structure.
- Raise `FetchError` on any failure (HTTP error, timeout, bad payload). The
  collector then leaves the existing cache untouched — a stale-but-valid cache
  beats a broken one.
- Do not widen what reaches the model. If a provider returns free-text fields
  (e.g. related queries), keep them out of the cache or sanitize them the same
  way `_sanitize_country` does.

## Read-only MCP tool checklist

When adding an MCP tool to `mcp_server/server.py`:

1. It reads `data/data.json` only. It must not call SerpApi or any network.
2. It returns only whitelisted, typed fields. Route any per-country data through
   `_sanitize_country`; never emit external free text.
3. It has no side effect — no write, no refresh, no send. If you need one, it
   belongs in the dev admin CLI, not here (`docs/tool-surfaces.md`).
4. Add a check to `smoke_test.py` for the new behavior.
5. Update `docs/tool-surfaces.md` and the README tool guide.

Do not add a tool just because an internal helper exists. Add it when it maps to
a user intent a read-only client should be able to choose (e.g. a future
`find_market(name)` lookup over the cached pool).

## Fork positioning

Good fork targets: solo or AI-assisted marketers doing MMM target-market
analysis; anyone who wants per-country search demand as a small, cached,
read-only data product without a heavy analytics stack.

MIT-licensed — use, modify, and redistribute freely; keep the license and
attribution. Record meaningful local changes in `docs/` so the next agent
understands what diverged.
