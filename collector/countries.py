"""ISO 3166-1 alpha-2 country code -> continent mapping.

Used to group Google Trends per-country interest into continent buckets for the
treemap-style grid. Kept deliberately small and dependency-free.

This module is pure data + lookup. It performs no I/O, no network, and is safe
to import from both the collector and the MCP read path.
"""

from __future__ import annotations

# Minimal but practical mapping. Extend as target markets grow.
# Continent labels are kept short to match the UI legend.
_COUNTRY_TO_CONTINENT: dict[str, str] = {
    # North America
    "US": "N. America", "CA": "N. America", "MX": "N. America",
    # South America
    "BR": "S. America", "AR": "S. America", "CL": "S. America",
    "CO": "S. America", "PE": "S. America",
    # Europe
    "GB": "Europe", "DE": "Europe", "FR": "Europe", "IT": "Europe",
    "ES": "Europe", "NL": "Europe", "SE": "Europe", "PL": "Europe",
    "CH": "Europe", "BE": "Europe", "AT": "Europe", "NO": "Europe",
    "DK": "Europe", "FI": "Europe", "IE": "Europe", "PT": "Europe",
    # Asia
    "JP": "Asia", "KR": "Asia", "CN": "Asia", "IN": "Asia",
    "SG": "Asia", "HK": "Asia", "TW": "Asia", "TH": "Asia",
    "VN": "Asia", "ID": "Asia", "MY": "Asia", "PH": "Asia",
    # Middle East
    "AE": "M. East", "SA": "M. East", "IL": "M. East", "TR": "M. East",
    "QA": "M. East", "KW": "M. East",
    # Oceania
    "AU": "Oceania", "NZ": "Oceania",
    # Africa
    "ZA": "Africa", "EG": "Africa", "NG": "Africa", "KE": "Africa",
    "MA": "Africa",
}

# Continent -> color ramp class used by the UI (see web/index.html).
CONTINENT_RAMP: dict[str, str] = {
    "N. America": "c-blue",
    "Asia": "c-purple",
    "Europe": "c-teal",
    "Oceania": "c-amber",
    "S. America": "c-coral",
    "M. East": "c-pink",
    "Africa": "c-green",
    "Unknown": "c-gray",
}


def continent_for(country_code: str) -> str:
    """Return the continent label for an ISO alpha-2 code, or 'Unknown'."""
    if not country_code:
        return "Unknown"
    return _COUNTRY_TO_CONTINENT.get(country_code.upper(), "Unknown")
