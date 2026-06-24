# Architecture

## Layers

```
                 ┌───────────────────────────────────────────────┐
   cron (1/day)  │  collector/fetch_data.py                       │  ← only SerpApi caller
   ───────────▶  │  fetch_interest_by_country()  [adapter seam]   │     ~60 calls/month
                 │  build_records() -> atomic write               │     (1 kw, 2 periods)
                 └───────────────────────┬───────────────────────┘
                                         │ writes
                                ┌────────▼────────┐
                                │  data/data.json  │   cache = cost firewall
                                │  meta + countries │
                                └────────┬────────┘
                          reads ┌────────┴────────┐ reads
                                ▼                 ▼
                  ┌──────────────────┐   ┌────────────────────────┐
                  │  web/index.html   │   │  mcp_server/server.py   │
                  │  4-col grid       │   │  read-only FastMCP      │
                  │  refresh = reread │   │  config_doctor          │
                  │  (no SerpApi)     │   │  get_search_data        │
                  └──────────────────┘   │  get_top_markets        │
                                         │  get_continent_summary  │
                                         └────────────────────────┘
```

## Module responsibilities

| Module | Entry point | Input | Output | Side effects |
|---|---|---|---|---|
| `collector/config.py` | `DEFAULT_CONFIG` | env (`SERPAPI_KEY`) | typed config, quota math | none |
| `collector/countries.py` | `continent_for()` | country code | continent label | none |
| `collector/fetch_data.py` | `main()` | SerpApi | `data/data.json` (atomic) | network, file write |
| `web/index.html` | browser load | `data/data.json` | rendered grid | none |
| `mcp_server/server.py` | `mcp.run()` | `data/data.json` | tool results | none (read-only) |

## Data contract: `data/data.json`

```json
{
  "meta": {
    "keyword": "Arencia",
    "geo": "worldwide",
    "updated_at": "ISO-8601 UTC",
    "source": "serpapi:google_trends:GEO_MAP_0",
    "periods": 2,
    "country_count": 12
  },
  "countries": [
    {
      "country_code": "US",
      "continent": "N. America",
      "interest": 87,
      "prev_interest": 72,
      "change_pct": 21
    }
  ]
}
```

- `interest` / `prev_interest`: Google Trends 0-100 relative index (NOT absolute
  search volume). `change_pct` is computed from the two periods; `null` when
  `prev_interest` is 0 (avoids divide-by-zero, mirrors Trends "breakout").
- `countries` is pre-sorted by `interest` desc and trimmed to `top_n`.

## The adapter seam

`fetch_interest_by_country(keyword, timeframe, cfg, api_key) -> {code: interest}`
is the single point of coupling to the data source. To change providers, replace
only this function:

- **Google Trends API (alpha)** — when access opens, swap to the official
  endpoint. Still a 0-100 index, but consistently scaled across requests.
- **Glimpse** — returns absolute search volume; change the field semantics from
  index to volume and update the UI legend.
- **Keyword Planner / DataForSEO** — monthly absolute volume; better for the MMM
  regression input and for target-market ratios, at the cost of daily cadence.

Nothing downstream (cache schema, UI, MCP tools) needs to change for an index-
based swap. A volume-based swap only changes labels, not structure.

## Why the layering matters for MMM

The cache schema is intentionally long-format-friendly (`date` via `meta`,
`keyword`, `country_code`, `interest`). When this feeds an MMM later, per-country
search demand becomes a regression input. Keeping collection in this shape from
the start avoids reshaping work downstream. If you switch to absolute volume
(Keyword Planner / Glimpse), the regression input quality improves because you
escape the 0-100 relative-scale problem.
