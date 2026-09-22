#!/usr/bin/env python3
"""Decide whether a payload really is an OpenAir airspace file.

An HTTP 200 does not promise airspace.  daec.de answers a missing file with a
short TYPO3 error body rather than a 404, and a moved download can answer with
an HTML error page; both reach a pilot as an airspace file holding nothing.
Only the content can tell those apart, so it is parsed.

aerofiles is the parser the rest of this repository already uses, so whatever
passes here is also readable by the build.
"""

from __future__ import annotations

from io import StringIO

from aerofiles.openair.reader import Reader as OpenAirReader

# A single-area file is legitimate (data/content/airspace/country/
# DE-ASP-Military-Low-Flying.txt holds exactly one), so one parsed record is the
# honest minimum.  Anything that serves an error page parses as none.
MIN_AIRSPACE_RECORDS = 1


def count_airspaces(text: str) -> tuple[int, int]:
    """Return (parsed airspaces, parse errors) for OpenAir text."""
    airspaces = errors = 0
    for record, error in OpenAirReader(StringIO(text)):
        if error:
            errors += 1
        elif record and record.get("type") == "airspace":
            airspaces += 1
    return airspaces, errors


def looks_like_openair(text: str, minimum: int = MIN_AIRSPACE_RECORDS) -> bool:
    """Whether text parses as at least minimum airspaces.

    Parse errors alone do not reject: several files in the wild mix in records
    aerofiles does not know while still describing usable airspace.
    """
    try:
        airspaces, _ = count_airspaces(text)
    except (ValueError, TypeError):
        return False
    return airspaces >= minimum


def describe(text: str) -> str:
    """Short human-readable verdict for logs."""
    try:
        airspaces, errors = count_airspaces(text)
    except (ValueError, TypeError) as e:
        return f"unparseable ({type(e).__name__}: {e})"
    return f"{airspaces} airspaces, {errors} parse errors"
