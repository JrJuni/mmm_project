"""ISO 3166-1 alpha-2 country code -> continent mapping.

Used to group Google Trends per-country interest into continent buckets for the
treemap-style grid. Kept deliberately small and dependency-free.

This module is pure data + lookup. It performs no I/O, no network, and is safe
to import from both the collector and the MCP read path.
"""

from __future__ import annotations

# Broad ISO alpha-2 -> continent mapping. Aims to cover every country Google
# Trends realistically returns so the grid's continent mode and
# `get_continent_summary` rarely fall back to "Unknown". Continent labels are
# kept short to match the UI legend. Middle East is a separate bucket; North
# African countries stay in Africa.
_COUNTRY_TO_CONTINENT: dict[str, str] = {
    # North America (incl. Central America + Caribbean)
    "US": "N. America", "CA": "N. America", "MX": "N. America",
    "GT": "N. America", "BZ": "N. America", "SV": "N. America",
    "HN": "N. America", "NI": "N. America", "CR": "N. America",
    "PA": "N. America", "CU": "N. America", "DO": "N. America",
    "HT": "N. America", "JM": "N. America", "TT": "N. America",
    "BS": "N. America", "BB": "N. America", "PR": "N. America",
    # South America
    "BR": "S. America", "AR": "S. America", "CL": "S. America",
    "CO": "S. America", "PE": "S. America", "VE": "S. America",
    "EC": "S. America", "BO": "S. America", "PY": "S. America",
    "UY": "S. America", "GY": "S. America", "SR": "S. America",
    # Europe
    "GB": "Europe", "IE": "Europe", "FR": "Europe", "DE": "Europe",
    "IT": "Europe", "ES": "Europe", "PT": "Europe", "NL": "Europe",
    "BE": "Europe", "LU": "Europe", "CH": "Europe", "AT": "Europe",
    "SE": "Europe", "NO": "Europe", "DK": "Europe", "FI": "Europe",
    "IS": "Europe", "PL": "Europe", "CZ": "Europe", "SK": "Europe",
    "HU": "Europe", "RO": "Europe", "BG": "Europe", "GR": "Europe",
    "HR": "Europe", "SI": "Europe", "RS": "Europe", "BA": "Europe",
    "ME": "Europe", "MK": "Europe", "AL": "Europe", "EE": "Europe",
    "LV": "Europe", "LT": "Europe", "UA": "Europe", "BY": "Europe",
    "MD": "Europe", "RU": "Europe", "MT": "Europe", "CY": "Europe",
    "LI": "Europe", "MC": "Europe", "AD": "Europe", "SM": "Europe",
    "XK": "Europe",
    # Asia (East/South/Southeast + Central Asia + Caucasus)
    "JP": "Asia", "KR": "Asia", "CN": "Asia", "IN": "Asia",
    "SG": "Asia", "HK": "Asia", "TW": "Asia", "TH": "Asia",
    "VN": "Asia", "ID": "Asia", "MY": "Asia", "PH": "Asia",
    "MM": "Asia", "KH": "Asia", "LA": "Asia", "BD": "Asia",
    "LK": "Asia", "NP": "Asia", "PK": "Asia", "MN": "Asia",
    "BN": "Asia", "MO": "Asia", "BT": "Asia", "MV": "Asia",
    "KZ": "Asia", "UZ": "Asia", "TM": "Asia", "KG": "Asia",
    "TJ": "Asia", "AF": "Asia", "GE": "Asia", "AM": "Asia",
    "AZ": "Asia",
    # Middle East
    "AE": "M. East", "SA": "M. East", "QA": "M. East", "KW": "M. East",
    "BH": "M. East", "OM": "M. East", "YE": "M. East", "IL": "M. East",
    "JO": "M. East", "LB": "M. East", "SY": "M. East", "IQ": "M. East",
    "IR": "M. East", "TR": "M. East", "PS": "M. East",
    # Oceania
    "AU": "Oceania", "NZ": "Oceania", "PG": "Oceania", "FJ": "Oceania",
    "NC": "Oceania", "PF": "Oceania", "SB": "Oceania", "VU": "Oceania",
    "WS": "Oceania", "TO": "Oceania", "GU": "Oceania",
    # Africa
    "ZA": "Africa", "EG": "Africa", "NG": "Africa", "KE": "Africa",
    "MA": "Africa", "DZ": "Africa", "TN": "Africa", "LY": "Africa",
    "SD": "Africa", "ET": "Africa", "GH": "Africa", "CI": "Africa",
    "SN": "Africa", "CM": "Africa", "UG": "Africa", "TZ": "Africa",
    "ZW": "Africa", "ZM": "Africa", "MZ": "Africa", "AO": "Africa",
    "BW": "Africa", "NA": "Africa", "MU": "Africa", "MG": "Africa",
    "RW": "Africa", "ML": "Africa", "BF": "Africa", "BJ": "Africa",
    "NE": "Africa", "TG": "Africa", "GA": "Africa", "CG": "Africa",
    "CD": "Africa", "MW": "Africa", "SO": "Africa", "LR": "Africa",
    "SL": "Africa", "GN": "Africa", "GM": "Africa", "MR": "Africa",
    "GQ": "Africa", "DJ": "Africa", "SC": "Africa", "CV": "Africa",
    "SZ": "Africa", "LS": "Africa", "BI": "Africa", "ER": "Africa",
    "TD": "Africa", "CF": "Africa", "ST": "Africa",
    "SH": "Africa", "RE": "Africa", "YT": "Africa",
    # Common dependent territories Google Trends may return
    "GI": "Europe", "JE": "Europe", "GG": "Europe", "IM": "Europe",
    "FO": "Europe", "GL": "N. America", "BM": "N. America",
    "KY": "N. America", "AW": "N. America", "CW": "N. America",
    "GF": "S. America",
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
