# Backlog

English is the source language for this document. Keep it compact; put long
history in dated notes under `docs/`. When this file conflicts with code or the
contract docs, prefer: (1) source code, (2) `docs/architecture.md` and
`docs/security.md`, (3) this backlog.

## Reading note

Read the current streams first. This project is a working MVP: the collector,
read-only MCP server, and static grid all exist and share `data/data.json`.
The backlog tracks operational hardening, docs/release maturation, and future
extension — not the core build, which is done.

## Current state (2026-06-24)

- **Implemented:** `collector/fetch_data.py` (only SerpApi caller, atomic
  write), `collector/config.py` (quota math), `collector/countries.py`,
  `mcp_server/server.py` (read-only: `config_doctor`, `get_search_data`,
  `get_top_markets`, `get_continent_summary`), `web/index.html` (4-col grid,
  refresh = reread), `smoke_test.py`, sample cache.
- **Invariants holding:** only the collector calls SerpApi; MCP + UI read the
  cache; no write/refresh/send tools; field-whitelist sanitization;
  secrets from env only. See `docs/architecture.md`, `docs/security.md`.
- **Quota policy encoded in `config.py`:** budget = 250 searches/month
  (SerpApi free plan, confirmed on the live pricing page + a real account
  dashboard 2026-06-24; 50/hour throughput. The earlier "100" was stale data);
  1 keyword x 2 periods x 1 refresh/day x 30 = ~60/month, within budget with
  ~190 headroom. Cadence = **1/day (24h cron)**, not 12h.
- **Git:** connected to `github.com/JrJuni/mmm_project` (public, MIT),
  `main` pushed. `.env` and `data/data.json` gitignored;
  `data/data.sample.json` shipped.

## Verified end-to-end (2026-06-24)

P1 runtime verification ran against the real SerpApi free tier (per plan
`env-playful-falcon.md`). Results:

- `.env` loader added to `collector/config.py` — a key placed in `.env` is now
  picked up automatically; a real environment variable still wins. Closes the
  "docs promised `.env` but code only read `os.environ`" gap.
- **Bug found & fixed:** `previous_timeframe = "now 14-d"` was rejected by
  SerpApi (HTTP 400 "Invalid date format" — `now N-d` only supports N in 1/7).
  The collector could never complete a live run. Replaced with explicit
  `YYYY-MM-DD YYYY-MM-DD` date ranges via `config.window_days` + `timeframes()`.
- Live collect wrote 12 countries (2 SerpApi calls); smoke test PASS; all four
  read-only MCP tools return; cache-preservation-on-error confirmed (the HTTP
  400 left the old cache untouched); no 64-hex key leaked into any tracked file.
- **New data-quality item (not a blocker):** 6/12 returned countries map to
  `continent: "Unknown"` (e.g. TN=Tunisia, MU=Mauritius missing from
  `collector/countries.py`). Widen the mapping — see Stream B.

## Current active streams

### Stream A — SerpApi free-tier policy (confirmed, low risk)

Goal: lock in cost/legal assumptions so cadence and release messaging are honest.

- [x] Free tier = 250 searches/month, 50/hour throughput (confirmed on live
      pricing page + account dashboard 2026-06-24; earlier "100/20" was stale).
      `config.monthly_quota_budget` set to 250.
- [x] Commercial use: no clause restricts the free plan to non-commercial use
      (only free-tier exclusion is the Legal Shield). Internal/product use of the
      data is permitted; reselling raw SERP data to third parties is not
      (Terms Section 2).
- [x] Caching / storing results in `data.json` is allowed (no storage-duration
      clause; SerpApi itself caches identical requests for ~1h). No raw-data
      redistribution.
- [x] U.S. Legal Shield NOT on free/starter/developer (covers lawful collection
      only, up to $2M, not data use). Documented in README free-tier terms.
      Internal use of public stats = low risk; revisit if scaling/external.
- [x] 100-vs-250 resolved: 250/month recurring per the live pricing page and a
      real dashboard. README + README_ko + CLAUDE/AGENTS/AI_START_HERE updated.

### Stream B — Operational setup

Goal: make the daily collection runnable and observably within budget.

- [ ] `crontab.example` — daily 24h schedule
      (`0 6 * * * cd .../collector && python -m collector.fetch_data`).
- [ ] Document a private admin manual-refresh path (run the collector
      directly). MUST NOT be exposed as an MCP/UI tool (cost-channel rule).
- [ ] Confirm `config_doctor` surfaces quota projection + `within_budget` and
      last-`updated_at` staleness clearly.
- [ ] Decide staleness policy: how old is `data.json` allowed to get before the
      grid/MCP flag it (Trends is weekly-ish, so ~2-3 days is fine).
- [ ] Widen `collector/countries.py` continent mapping — live run showed 6/12
      countries as `Unknown` (TN, MU, etc.). Affects `get_continent_summary`
      and the grid's continent color mode.

### Stream C — Docs & release maturation

Goal: port the useful structure from the sibling `deal-intel-mcp/docs/` and get
release-ready. (Reuse assessment in progress; see "Docs to port" below.)

- [ ] Port a tailored `release-publish-checklist.md` (gate before any tag).
- [ ] Port a tailored `mvp-readiness.md` gate (what "good enough to share" means
      for a read-only data product).
- [ ] Port a `tool-surfaces.md` documenting the read-only MCP surface and the
      explicit NO-write/refresh/send rule.
- [ ] Port an `extending.md` centered on the `fetch_interest_by_country`
      adapter seam (provider swaps).
- [ ] Start a `lesson-learned.md` for this repo.
- [ ] README: add quota-math section + keyword-add recalculation guidance +
      `.env` per-user key alias recommendation.

### Stream D — Future / extension points (not now)

Goal: capture so they are not re-derived later. Mind the quota math on each.

- [ ] Keyword expansion (brand + category) — recompute quota; if >250/mo,
      consider $25 Starter or drop a period. Each keyword x periods x cadence.
- [ ] Absolute-volume swap at the adapter seam (Glimpse / Keyword Planner /
      DataForSEO) — changes field semantics from 0-100 index to volume; better
      MMM regression input; update UI legend. Structure unchanged.
- [ ] Official Google Trends alpha API — swap only the adapter when access
      opens; still a 0-100 index, consistently scaled.
- [ ] MMM regression integration — cache is already long-format-friendly
      (date via meta, keyword, country_code, interest). Feed per-country demand
      as a regression input downstream.
- [ ] Optional one-paragraph data summary via Haiku API — separate process,
      reads `data.json`, NOT an MCP tool (keeps the surface read-only and
      cost-bounded).

## Docs to port from `deal-intel-mcp/docs/`

Reuse assessment complete (24 source docs reviewed). Adapt, do not copy —
strip all deal-intel domain content (MongoDB/Atlas, MEDDPICC, distribution).

**Port soon (REUSE-HIGH):**

1. `release-publish-checklist.md` — keep the "validate before publish" + "update
   docs after publish" structure; replace npm/PyPI steps with a simple GitHub
   release. Gate before any tag.
2. `lesson-learned.md` — adopt the append-only entry format
   (Date / Tried / Result / Lesson / Related). Start capturing now.
3. `extending.md` — rebuild around the single `fetch_interest_by_country()`
   seam; a "Common customization paths" table mapping goal -> start point
   (provider swap -> `collector/fetch_data.py`).
4. `tool-surfaces.md` — document the read-only MCP surface as one registry, one
   exposed surface, and the explicit gating rule for any future tool.

**Borrow format only when needed (REUSE-LOW):** `backlog.md` (streams/reading-
order convention — already applied here), `mvp-readiness.md` (Green/Yellow/Not-
blocking gate buckets), `customization-recipes.md` (Start-with / Steps /
Validate / Gotchas recipe shape), `architecture.md` (module-responsibilities
table if complexity grows), `metrics.md`+`reports.md` (contract-writing method,
only if a reporting surface is added).

**Skip (domain/infra-specific, no value):** status.md, qualification-framework-
v2.md, baseline.md, config-profiles.md, mongodb-atlas-pro.md, atlas-charts.md,
query-audit.md, storage-backends.md, bootstrapper-contract.md, bootstrapper-
fresh-smoke.md, distribution-plan.md, public-demo-script.md, pro-fallback-
errors.md.
