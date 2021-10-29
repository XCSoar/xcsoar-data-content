#!/bin/env python3
"""
'../../ext/xcsoar-data-repository/data/waypoints-by-country.json'
../../ext/xcsoar-data-content/waypoints/
"""
import datetime
import json
from pathlib import Path
import sys

import pytz
from iso3166 import countries, Country

ISO3166_COUNTRIES = {c.name.lower(): c for c in countries}
PYTZ_COUNTRIES = {v.lower(): k for k, v in pytz.country_names.items()}


def sub_get(partial_name: str) -> Country or None:
    """
    Get the unambiguous matching Country from a partial name.
    partial_name:  The country name, or sub-string thereof, to find.
    Return:  None, or the fuzzy matching country name.
    """
    name = partial_name.lower()
    country = None
    for key in ISO3166_COUNTRIES:
        if name in key:    ###   Crux   ###
            if country is not None:
                # Ambiguous partial_name
                raise KeyError
            country = ISO3166_COUNTRIES[key]

    if country is None:
        # No match
        raise KeyError
    return country


def file_length(in_file: Path) -> int:
    """Return the number of lines in file"""
    with open(in_file, 'r') as fp:
        x = len(fp.readlines())
    return x


def alpha2_from_country_name(name: str):
    """
    1: Failed iso3166.get: "bolivia"
    2: Failed iso3166.sub_get: "czech republic".
    1: Failed iso3166.get: "iran"
    1: Failed iso3166.get: "macedonia"
    1: Failed iso3166.get: "moldova"
    1: Failed iso3166.get: "united kingdom"
    1: Failed iso3166.get: "united states"
    """
    area = '??'
    try:
        area = countries.get(name).alpha2
    except KeyError as ke:
        print(f'1: Failed iso3166.get: "{name}"')

        try:
            area = sub_get(name).alpha2
        except KeyError as ke:
            print(f'2: Failed iso3166.sub_get: "{name}".')

            try:
                area = PYTZ_COUNTRIES[name]
            except KeyError as ke:
                print(f'3:  Failed PYTZ: "{name}".  =========')
    return area


def gen_waypoints_by_country_json(in_dir: Path, out_filename=Path("waypoints-by-country.json")) -> None:
    """
    Generate a JSON manifest of the in_dir's contents. e.g.
    https://github.com/XCSoar/xcsoar-data-repository/blob/master/data/waypoints-by-country.json
{
  "title": "Waypoints-by-Country",
  "records": [
    {
      "name": "Afghanistan.cup",
      "uri": "http://download.xcsoar.org/waypoints/Afghanistan.cup",
      "type": "waypoint",
      "area": "af",
      "update": "2015-11-17"
    },
    """

    # Swap key and value:
    url = "http://download.xcsoar.org/waypoints/"
    rv = {"title": "Waypoints-by-Country", "records": []}

    for p in sorted(in_dir.glob('*.cup')):
        name = p.stem.lower().replace("_", ' ')
        area = alpha2_from_country_name(name)
        i = {'name': p.name,
             'uri': url + p.name,
             'type': 'waypoint',
             'area': area.lower(),
             'update': datetime.date.today().isoformat()}
        rv['records'].append(i)

    with open(out_filename, 'w') as f:
        json.dump(rv, f, indent=2, )
    print(f"Created: {out_filename}")
    return


def gen_waypoints_js(in_dir: Path, out_filename=Path("waypoints.js")):
    """
    TODO: JSON -> JS
    var WAYPOINTS = {"Canada": {"average": [48.36559389389391, -96.12881841841843], "size": 333}, "Brazil":
    """
    rv = {}
    for p in sorted(in_dir.glob('*.cup')):
        name = p.stem.replace("_", ' ')
        rv[name] = {'size': file_length(p), }

    with open(out_filename, 'w') as f:
        json.dump(rv, f, indent=2, )
    print(f"Created: {out_filename}")
    return


def gen_waypoints_compact_js(in_dir: Path, out_filename=Path("waypoints_compact.js")):
    """
    TODO: JSON -> JS
    var WAYPOINTS = {
      "Canada": 333,
      "Brazil": 312,
    """
    rv = {}
    for p in sorted(in_dir.glob('*.cup')):
        name = p.stem.replace("_", ' ')
        rv[name] = file_length(p)

    with open(out_filename, 'w') as f:
        json.dump(rv, f, indent=2, )
    print(f"Created: {out_filename}")
    return


if __name__ == '__main__':
    in_dir = Path(sys.argv[1])
    # out_dir = Path(sys.argv[2])

    gen_waypoints_by_country_json(in_dir)
    gen_waypoints_js(in_dir)
    gen_waypoints_compact_js(in_dir)
