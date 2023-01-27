#!/bin/env python3
# -*- coding: utf-8 -*-
"""Ensure that waypoints/countries are named correctly, and pass an Aerofiles check."""

from pathlib import Path
import sys

from aerofiles.seeyou.reader import Reader as CupReader
from aerofiles import errors

from iso3166 import countries


def is_valid_cup(filename: Path) -> bool:
    """Return True if filename is in a valid SeeYou .cup format, else false."""
    cup = CupReader()
    try:
        cup.read(open(filename))
    except errors.ParserError:
        print(f"INVALID SeeYou .cup format: {filename}")
        return False
    print(f"Valid .cup format: {filename}")
    return True


def is_name_country_code(filename: Path) -> bool:
    """Return True if filename.stem is a valid two-letter country code (ISO 3166-1 alpha-2), else return False."""
    name = filename.stem

    try:
        country = countries.get(name)
    except KeyError:
        print(f"INVALID ISO 3166-1 alpha-2 country code: {name} ({filename})")
        return False

    if country.alpha2.lower() != name.lower():
        # Valid country/code, but not alpha2.
        print(
            f"INVALID two-letter ISO 3166-1 alpha-2 country code: {name} ({filename})"
        )
        return False
    print(f"Valid two-letter country code: {name} ({filename})")
    return True


def main(in_dir: Path) -> int:
    """Check all the .cup files in the in_dir."""
    ok = True
    for p in sorted(in_dir.glob("*.cup")):
        ok = is_name_country_code(p) and ok
        ok = is_valid_cup(p) and ok
    return ok


if __name__ == "__main__":
    wp_dir = Path(sys.argv[1])

    if main(wp_dir):
        sys.exit(0)
    sys.exit(1)
