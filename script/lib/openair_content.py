#!/usr/bin/env python3
"""Decide whether a payload really is an OpenAir airspace file.

An HTTP 200 does not promise airspace.  daec.de answers a missing file with a
short TYPO3 error body rather than a 404, and a moved download can answer with
an HTML error page; both reach a pilot as an airspace file holding nothing.
Only the content can tell those apart.

aerofiles decides.  XCSoar accepts more than the format allows -- it takes a
lowercase hemisphere, and it reads latitude in degrees/minutes/seconds beside a
longitude in degrees and decimal minutes, which the format specification
forbids outright ("Do not mix DMS and DDM notations.  Stick to one definition
throughout the file.").  Passing such a file because XCSoar copes would hide a
defect rather than get it fixed, and XCSoar has previously dropped airspace it
could not read without saying so.

Counting class lines separately is what makes the report useful: "4 airspace
blocks, aerofiles read 0" names the file and the size of the problem, where a
bare failure would not.
"""

from __future__ import annotations

import re
from io import StringIO

from aerofiles.openair.reader import Reader as OpenAirReader

# A single-area file is legitimate (data/content/airspace/country/
# DE-ASP-Military-Low-Flying.txt holds exactly one), so one airspace is the
# honest minimum.  Anything serving an error page yields none.
MIN_AIRSPACE_RECORDS = 1

# "AC <class>" opens an airspace.  Counted without parsing, to say how much of
# a file aerofiles could not reach.
_CLASS_RE = re.compile(r"^AC\s+\S", re.MULTILINE)


def count_airspace_blocks(text: str) -> int:
    """Return the number of airspace class lines in OpenAir text."""
    return len(_CLASS_RE.findall(text))


def count_airspaces(text: str) -> tuple[int, int]:
    """Return (airspaces aerofiles parsed, parse errors) for OpenAir text."""
    airspaces = errors = 0
    for record, error in OpenAirReader(StringIO(text)):
        if error:
            errors += 1
        elif record and record.get("type") == "airspace":
            airspaces += 1
    return airspaces, errors


def looks_like_openair(text: str, minimum: int = MIN_AIRSPACE_RECORDS) -> bool:
    """Whether aerofiles reads at least minimum airspaces out of text.

    The lenient test, for files this repository only links to.  A URI that has
    started serving an error page must be caught, but a third-party file with a
    damaged record cannot be repaired here, so it is reported instead.
    """
    try:
        airspaces, _ = count_airspaces(text)
    except (ValueError, TypeError):
        return False
    return airspaces >= minimum


def is_clean_openair(text: str, minimum: int = MIN_AIRSPACE_RECORDS) -> bool:
    """Whether aerofiles reads text without a single parse error.

    The strict test, for files this repository ships.  A damaged record costs
    the airspace it belongs to and the file's bbox, and here it can simply be
    repaired, so tolerating it gains nothing.
    """
    try:
        airspaces, errors = count_airspaces(text)
    except (ValueError, TypeError):
        return False
    return airspaces >= minimum and errors == 0


def describe(text: str) -> str:
    """Short human-readable verdict for logs."""
    blocks = count_airspace_blocks(text)
    try:
        airspaces, errors = count_airspaces(text)
    except (ValueError, TypeError) as e:
        return f"{blocks} airspace blocks, aerofiles failed ({type(e).__name__})"

    if airspaces == blocks and not errors:
        return f"{blocks} airspaces"
    return (f"{blocks} airspace blocks, aerofiles read {airspaces} "
            f"({errors} parse errors, no bbox)")
