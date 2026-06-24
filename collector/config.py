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

    # Conservative free-tier ceiling. SerpApi advertises a forever-free plan;
    # recent sources cite 100 searches/month. We budget against 100.
    monthly_quota_budget: int = 100

    # Refresh cadence target. Daily (1/day) keeps 1 keyword * 2 periods within
    # the 100/month budget (~60/month). Do NOT lower below the rate the data
    # actually changes (Trends is weekly-ish; Keyword Planner is monthly).
    refreshes_per_day: int = 1

    # --- Timeframes ------------------------------------------------------
    # SerpApi google_trends accepts relative timeframes. We use rolling 7-day
    # windows for current vs previous.
    current_timeframe: str = "now 7-d"
    previous_timeframe: str = "now 14-d"  # caller derives prior-week delta

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


def serpapi_key() -> str | None:
    """Read the SerpApi key from the environment. Never hard-code it."""
    return os.environ.get("SERPAPI_KEY")


DEFAULT_CONFIG = CollectorConfig()
