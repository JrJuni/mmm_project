# Tool surfaces

How capability is split between the read-only MCP surface (what a model/host can
call) and the hidden developer surface (what a human runs in a terminal). This
split is the core of the security posture — see `docs/security.md`.

## Goal

Keep the model-facing surface incapable of spending money or leaking data, while
still letting a developer change everything. One registry would blur that line,
so the two surfaces are physically different programs.

## Mental model

- **Production MCP surface** (`mcp_server/server.py`) — read-only. Exposed to the
  model / MCP host. Reads `data/data.json` only. Never calls SerpApi, never
  mutates anything, never sends data outward.
- **Developer surface** (`collector/admin.py`) — a terminal CLI, **not an MCP
  tool**. Can change everything (keyword, geo, pool size, selection) and trigger
  a live collection. Because it is a CLI, it is structurally unreachable by the
  model or by untrusted content.

A model can ask the read-only tools anything a thousand times and spend zero
quota and exfiltrate nothing. Changing what is collected is a deliberate human
action at a terminal.

## Surface contract

| Surface | Where | Exposed to | Tool policy |
|---|---|---|---|
| MCP (production) | `mcp_server/server.py` | model / MCP host | Read-only reads of the cache. No write / refresh / send. |
| Dev admin (hidden) | `collector/admin.py` | a developer in a terminal | Full mutation + live refresh. Never wired to MCP or untrusted input. |

## MCP surface (read-only)

Exactly four tools, all reads of `data/data.json`:

- `config_doctor` — readiness, freshness (`stale`/`staleness_hours` vs
  `staleness_max_hours`), and the quota projection. Run first.
- `get_search_data` — the per-country table (sanitized, structured fields only).
- `get_top_markets(n)` — top N countries by interest.
- `get_continent_summary` — totals/averages per continent.

The rule: **do not add a write, refresh, or send tool here.** Each absent leg
keeps the lethal trifecta from forming (`docs/security.md`). External data
reaches the model only through `_sanitize_country` (whitelisted, typed fields;
country codes hard-constrained); no free text passes through.

A future `find_market(name)` lookup would belong here **only** if it stays
read-only: resolve a name to an ISO code and return that row from the cached
pool. It must not mutate config or trigger collection.

## Developer surface (hidden CLI)

`collector/admin.py` is the project's hidden control surface. It writes a
gitignored `dev_overrides.json` that `config.load_config()` merges over the
shipped defaults, and can run a collection.

```
python -m collector.admin show
python -m collector.admin set-keyword "YourBrand"
python -m collector.admin set-geo ""            # "" = worldwide
python -m collector.admin set-topn 50           # or: all
python -m collector.admin set-display-n 12
python -m collector.admin select US KR JP AE    # display filter only
python -m collector.admin clear-select
python -m collector.admin refresh               # live collection (SerpApi)
python -m collector.admin reset                 # drop all overrides
```

Why it is a CLI and not a gated MCP tool: a CLI cannot be reached by the model
at all, so it carries zero trifecta risk. A gated dev MCP server could be left
on or wired to untrusted input by mistake. If one is ever added, it must be off
by default, never shipped enabled, and documented as reopening the threat model.

## Adding to a surface

- **New read?** Add a read-only tool to `mcp_server/server.py` and follow the
  checklist in `docs/extending.md`. Keep it sanitized and side-effect-free.
- **New mutation / operation?** Add a subcommand to `collector/admin.py`. Never
  expose it over MCP.

If you are unsure which surface something belongs on, ask: *can the model trigger
it?* If yes, it must be read-only. If it changes collection or config, it is dev
admin only.
