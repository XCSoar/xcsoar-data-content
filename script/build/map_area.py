"""Country-area inference shared by map manifest generators.

Map file names conventionally start with an ISO country identifier, followed
by an underscore (for example ``AUS_ADELAIDE``).  A small number of historic
names do not follow that convention; keep their meanings explicit here so
every generated map manifest uses the same safe result.
"""

from iso3166 import countries


# Map stems whose country cannot be inferred safely from their prefix.
# An empty value deliberately leaves a multi-country or ambiguous map
# ungrouped in the repository.
AREA_OVERRIDES = {
    "ALPS": "",
    "BEN_WGER": "",
    "BUL": "bg",
    "UK": "gb",
    "GER": "de",
    "IRE": "ie",
    "POR": "pt",
    "TURKEY": "tr",
}


def guess_area(name: str) -> str:
    """Return a lowercase ISO-3166 alpha-2 area for a map stem, if known.

    The complete stem is considered first, preserving country names that
    contain hyphens. The remaining candidates remove underscore- or
    hyphen-separated suffixes from right to left. ``iso3166`` accepts alpha-2,
    alpha-3, and supported country names. Unknown identifiers produce no area.
    """
    stem = name.rsplit(".", 1)[0]
    override = AREA_OVERRIDES.get(stem.upper())
    if override is not None:
        return override

    candidate = stem
    while candidate:
        try:
            return countries.get(candidate).alpha2.lower()
        except KeyError:
            separator = max(candidate.rfind("_"), candidate.rfind("-"))
            if separator < 0:
                break
            candidate = candidate[:separator]
    return ""
