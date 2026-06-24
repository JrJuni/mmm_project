# Security model

This project is deliberately shaped so that the most common MCP attack paths
cannot form. This doc records the threat model and the boundaries to preserve.

## The lethal trifecta — and why it does not form here

Indirect prompt injection becomes dangerous when an agent has all three of:

1. access to private/sensitive data,
2. exposure to untrusted external content,
3. an exfiltration channel (a way to send data outward).

In this project:

- **No private data.** The cache holds public, aggregate search-interest
  statistics. There is nothing sensitive to steal.
- **Limited untrusted content.** Data comes from Google Trends aggregate stats
  via SerpApi — mostly country codes and integers, not attacker-authored free
  text. (The one theoretical vector is related-queries text; we do not expose
  it. See "Injection isolation.")
- **No exfiltration channel.** The MCP server has no tool that sends data
  anywhere. It only returns cached reads to the user's own client.

With any one leg missing, the trifecta cannot complete. Keep it that way:
**do not add an outbound/send tool, and do not add private data.**

## Injection isolation

Even though our data source is low-risk, the MCP server applies a whitelist so
no external free-text reaches the model's reasoning:

- `_sanitize_country()` copies only `country_code`, `continent`, `interest`,
  `prev_interest`, `change_pct`.
- `country_code` is hard-constrained to alphabetic, length <= 3. A poisoned
  value like `US; ignore previous instructions` collapses to `""`.
- Any extra field on a cache row (e.g. an injected `evil` key) is dropped.

If you ever expose related queries or any free-text field, sanitize/escape it
the same way, or keep it out of tool output and use it only for UI rendering.

## Cost-channel isolation

The collector is the only SerpApi caller. The MCP server and the UI read the
cache. Therefore:

- An injection that makes the assistant call MCP tools 1000 times costs zero
  SerpApi quota.
- A user mashing the UI refresh button costs zero SerpApi quota.
- Billable usage is bounded by cron cadence, not by call patterns.

Do not add a refresh/collect tool to the MCP surface. On-demand refresh and all
configuration changes (keyword, geo, cache pool, country selection) are private
admin actions, exposed only through the developer CLI `collector/admin.py` (run
directly in a terminal; it writes a gitignored `dev_overrides.json`). That CLI
is the project's *hidden* control surface: it can mutate everything and trigger
collection, but because it is a plain CLI it is structurally unreachable by the
model or by untrusted content. Keep it that way — never expose `admin.py`'s
operations over MCP, and never wire them to untrusted input. Doing so would add
back the write/refresh channel this design removes.

Note on display vs collection: choosing which countries to *show*
(`selected_countries`, `display_n`) filters the already-cached pool and triggers
no SerpApi call, so a read-only selection capability (UI or a future read-only
lookup tool) does not reopen the cost channel. Only *collection* changes
(keyword/geo/cadence) are admin-gated.

## Secrets

- `SERPAPI_KEY` is read from the environment only. It is never hard-coded,
  logged, or written into `data/` or `docs/`.
- `.env` is gitignored. `.env.example` ships a sentinel placeholder.
- In the SerpApi dashboard, alias the key per user so usage is monitorable and
  blast radius on leak is limited to that key.

## If the model changes (future)

The safety properties above depend on the read-only, no-private-data shape. Any
of these changes reopens the threat model and requires re-review:

- adding a tool that sends/emails/posts data (adds exfiltration leg),
- ingesting private deal/customer data into the cache (adds private-data leg),
- exposing free-text search fields to the model (widens untrusted content),
- letting the MCP server or browser call SerpApi (adds cost channel).
