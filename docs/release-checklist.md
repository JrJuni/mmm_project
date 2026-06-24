# Release gate & publish checklist

The gate that must pass before tagging a public release of `mmm-search-mcp`.
Adapted from the sibling `deal-intel-mcp` release process, stripped to this
project's much smaller surface. Principle unchanged: **validate before publish,
update docs after publish.**

First release target is a **GitHub release of the source repo** (MIT, public).
There is no npm/PyPI/MCPB distribution yet — users clone and run. Revisit
packaging only if Stream D justifies it.

Status legend: `[x]` confirmed in repo today · `[ ]` to verify at release time.

---

## Gate 1 — Correctness & smoke

- [ ] `python smoke_test.py` passes (no network; uses sample cache).
- [ ] Collector dry path: with a real `SERPAPI_KEY`, `python -m collector.fetch_data`
      writes a valid `data/data.json` (atomic replace), and on a forced fetch
      error the **existing cache is left unchanged** (stale-but-valid wins).
- [ ] MCP server starts (`python -m mcp_server.server`) and every read tool
      returns: `config_doctor`, `get_search_data`, `get_top_markets`,
      `get_continent_summary`.
- [ ] `web/index.html` renders the grid purely from `data/data.json`
      (refresh = reread, never calls SerpApi).
- [ ] Quick contract checks pass:
      `python -c "from collector.config import DEFAULT_CONFIG as c; print(c.projected_monthly_calls(), c.within_budget())"`
      and `python -c "from collector.fetch_data import build_records; print('ok')"`.

## Gate 2 — Cost / quota (the cost firewall)

- [x] `config.py`: budget = 250/month; 1 kw x 2 periods x 1 refresh/day x 30
      = ~60/month; `within_budget()` is True with ~190 headroom.
- [ ] `within_budget()` is True for the shipped default config.
- [ ] Cadence is **1/day (24h)**, not 12h. `crontab.example` reflects this
      (Stream B — may ship in this release or the next).
- [ ] No code path in the MCP server or web UI calls the collector or SerpApi
      (grep for `serpapi`/`fetch_interest_by_country` outside `collector/`).

## Gate 3 — Security posture (re-affirm, don't assume)

- [ ] MCP surface is read-only: **no write / refresh / send tool** exists.
- [ ] `_sanitize_country` whitelist still the only path external data takes to
      the model; no free-text (related-queries) field exposed.
- [ ] Secrets: `SERPAPI_KEY` from env only; not hard-coded, logged, or written
      into `data/` or `docs/`. `.env` gitignored; `.env.example` is a sentinel.
- [ ] No secret or real `data/data.json` is staged for commit
      (`git status` clean of both; only `data/data.sample.json` ships).
- [ ] `docs/security.md` still matches the code (trifecta legs all absent).

## Gate 4 — Docs honesty

- [x] README states the free-tier reality plainly: 250 searches/month cap
      (50/hour), commercial/internal use allowed, **no reselling raw SERP
      data**, caching allowed, and **no U.S. Legal Shield on free/starter/
      developer**. "Free-tier terms (SerpApi)" section added to README +
      README_ko, with the quota-math formula.
- [ ] `.env` per-user key alias recommendation present (blast-radius limiting).
- [ ] `AI_START_HERE.md`, `docs/architecture.md`, `docs/security.md`,
      `docs/backlog.md` reflect the shipped state.
- [x] 100-vs-250 resolved: free plan is 250/month recurring (live pricing page +
      account dashboard, 2026-06-24). `config.monthly_quota_budget` = 250.

## Gate 5 — Repo hygiene

- [ ] `LICENSE` (MIT) present; year/owner correct.
- [ ] `.gitignore` excludes `.env`, `__pycache__/`, `*.pyc`, `data/data.json`.
- [ ] `requirements.txt` minimal (collector stdlib-only; `fastmcp` for server).
- [ ] Working tree clean; branch is `main`, pushed to
      `github.com/JrJuni/mmm_project`.

---

## Publish order

1. Pass all gates above on a clean checkout.
2. Final docs pass (README + AI_START_HERE accurate for a first-time user).
3. Tag the release: `git tag -a vX.Y.Z -m "..."` then `git push origin vX.Y.Z`.
4. Create the GitHub release from the tag; attach a short changelog
   (what it does, free-tier limits, how to run the collector + MCP server).

## Post-publish

- [ ] Append a `docs/lesson-learned.md` entry for anything that bit during the
      release (rate limits, Windows path quoting, cron cadence, secret hygiene).
- [ ] Update `docs/backlog.md`: mark released items done; move "Future /
      extension points" forward as the next stream.
- [ ] Watch the SerpApi dashboard for the first week to confirm real usage
      tracks the ~60/month projection.

## Out of scope for first release

- npm / PyPI / MCPB packaging (clone-and-run only for now).
- Keyword expansion, absolute-volume provider swap, MMM regression integration,
  Haiku summary — all Stream D, post-release.
