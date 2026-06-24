"""Collector configuration.

All tunable knobs for the data collection layer live here so that changing the
tracked keyword, the refresh cadence, or the free-tier quota budget never
requires touching fetch logic.

Secrets (the SerpApi key) are NEVER stored here. They are read from the
environment at runtime. See `.env.example`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path


@dataclass(frozen=True)
class CollectorConfig:
    # --- What to track ---------------------------------------------------
    # Keep this list short on the free tier. Each keyword costs
    # (periods_per_keyword) successful SerpApi searches per refresh.
    keywords: list[str] = field(default_factory=lambda: ["Arencia"])

    # Geo scope. "" = worldwide. SerpApi returns per-country breakdown when
    # data_type=GEO_MAP_0 and region=COUNTRY.
    geo: str = ""

    # Include low-search-volume regions. Important for small/new brands whose
    # signal would otherwise collapse to zero in most countries.
    include_low_search_volume: bool = True

    # How many top countries to keep in the cache / show in the grid.
    top_n: int = 12

    # --- Cost control ----------------------------------------------------
    # Two periods (current 7d + previous 7d) are needed to compute change.
    # Set to 1 to track current interest only and halve quota usage.
    periods_per_keyword: int = 2

    # Free-tier ceiling. SerpApi's pricing page lists the free plan at 250
    # searches/month (recurring) with 50/hour throughput, confirmed against the
    # live pricing page and a real account dashboard on 2026-06-24. Usage stays
    # far under this (~60/month), leaving room to add keywords later.
    monthly_quota_budget: int = 250

    # Refresh cadence target. Daily (1/day) keeps 1 keyword * 2 periods within
    # the 250/month budget (~60/month). Do NOT lower below the rate the data
    # actually changes (Trends is weekly-ish; Keyword Planner is monthly).
    refreshes_per_day: int = 1

    # --- Timeframes ------------------------------------------------------
    # Length (days) of each comparison window. The current window is the last
    # `window_days`; the previous window is the `window_days` immediately
    # before it. See `timeframes()` for why we use explicit date ranges.
    window_days: int = 7

    def projected_monthly_calls(self) -> int:
        """Estimate monthly successful searches for the current settings."""
        return (
            len(self.keywords)
            * self.periods_per_keyword
            * self.refreshes_per_day
            * 30
        )

    def within_budget(self) -> bool:
        return self.projected_monthly_calls() <= self.monthly_quota_budget

    def timeframes(self, today: date | None = None) -> tuple[str, str]:
        """Return (current, previous) SerpApi google_trends `date` ranges.

        Each value is an explicit ``"YYYY-MM-DD YYYY-MM-DD"`` range. SerpApi's
        relative ``now N-d`` tokens only support N in {1, 7} (plus hour units),
        so ``"now 14-d"`` is rejected with HTTP 400 "Invalid date format".
        Explicit ranges avoid that and keep both windows the same length and
        granularity, which makes the week-over-week delta meaningful.
        """
        if today is None:
            today = date.today()
        w = self.window_days
        cur_start = today - timedelta(days=w - 1)
        prev_end = today - timedelta(days=w)
        prev_start = today - timedelta(days=2 * w - 1)
        fmt = lambda a, b: f"{a.isoformat()} {b.isoformat()}"
        return fmt(cur_start, today), fmt(prev_start, prev_end)


def _load_dotenv(env_path: Path | None = None) -> None:
    """Populate ``os.environ`` from ``<repo-root>/.env`` if the file exists.

    Minimal stdlib parser (no third-party dependency): full-line ``#`` comments
    and blank lines are skipped; each remaining line is split on the *first*
    ``=`` into ``KEY=VALUE``; surrounding whitespace and a single matching pair
    of quotes are stripped from the value. Pairs are applied with
    ``setdefault`` so a real environment variable always wins (standard dotenv
    precedence). Values are never logged or printed (secrets stay secret). A
    missing or unreadable ``.env`` is harmless.

    Intentionally NOT supported: ``export KEY=``, multiline values, variable
    interpolation, escape sequences, inline comments.
    """
    if env_path is None:
        env_path = Path(__file__).resolve().parent.parent / ".env"
    try:
        with env_path.open("r", encoding="utf-8") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip()
                if (
                    len(value) >= 2
                    and value[0] == value[-1]
                    and value[0] in ("'", '"')
                ):
                    value = value[1:-1]
                if key:
                    os.environ.setdefault(key, value)
    except (FileNotFoundError, OSError):
        return


def serpapi_key() -> str | None:
    """Read the SerpApi key from the environment. Never hard-code it."""
    return os.environ.get("SERPAPI_KEY")


# Load .env at import so a key placed there is available to the collector
# without any manual export. A real environment variable still takes priority.
_load_dotenv()

DEFAULT_CONFIG = CollectorConfig()
