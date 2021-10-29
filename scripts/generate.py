#!/bin/env python3

"""
Auto-generate these files from directory listing xcsoar-data-content/waypoints:

xcsoar-data-repository/data/waypoints-by-country.json
xcsoar-data-content/waypoints/waypoints.js
xcsoar-data-content/waypoints/waypoints_compact.js
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

    TODO: Remove, after converting all *.cup files to ISO3166.alpha2 names.
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
    """Return the number of lines in file."""
    with open(in_file, 'r') as fp:
        x = len(fp.readlines())
    return x


def alpha2_from_country_name(name: str) -> str:
    """
    Try various methods to work out ISO3166.alpha2 code from file name (ostensibly a country name).
    """
    area = '??'
    try:
        area = countries.get(name).alpha2
    except KeyError:
        print(f'1: Failed iso3166.get: "{name}"')

        try:
            area = sub_get(name).alpha2
        except KeyError:
            print(f'2: Failed iso3166.sub_get: "{name}".')

            try:
                area = PYTZ_COUNTRIES[name]
            except KeyError:
                print(f'3:  Failed PYTZ: "{name}".  =========')
    return area


def gen_waypoints_by_country_json(in_dir: Path, out_path: Path) -> None:
    """
    Generate a JSON manifest of the wp_dir's contents. e.g.
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

    with open(out_path, 'w') as f:
        json.dump(rv, f, indent=2, )
    print(f"Created: {out_path}")
    return


def gen_waypoints_js(in_dir: Path, out_path: Path):
    """
    Generate https://github.com/XCSoar/xcsoar-data-content/blob/master/waypoints/waypoints.js
    """
    rv = {}
    for p in sorted(in_dir.glob('*.cup')):
        name = p.stem.replace("_", ' ')
        rv[name] = {
            'size': file_length(p),
            'average': (0.0, 0.0),    # TODO: Properly replace average with country centroid.
        }

    with open(out_path, 'w') as f:
        f.write('var WAYPOINTS = ')    # TODO: Use json rather than js.
        json.dump(rv, f, indent=2,)    # indent = None)
    print(f"Created: {out_path}")
    return


def gen_waypoints_compact_js(in_dir: Path, out_path: Path):
    """
    Generate https://github.com/XCSoar/xcsoar-data-content/blob/master/waypoints/waypoints_compact.js
    """
    rv = {}
    for p in sorted(in_dir.glob('*.cup')):
        name = p.stem.replace("_", ' ')
        rv[name] = file_length(p)

    with open(out_path, 'w') as f:
        f.write('var WAYPOINTS = ')    # TODO: Use json rather than js.
        json.dump(rv, f, indent=2,)   # indent = None)
    print(f"Created: {out_path}")
    return


def gen_repository_wp_by_country(in_dir: Path, out_path: Path):
    """
    Generate section of http://download.xcsoar.org/repository .
    """
    rv = '# Waypoints-by-Country\n'

    for p in sorted(in_dir.glob('*.cup')):
        name = p.stem.replace("_", ' ')
        area = alpha2_from_country_name(name).lower()

        filename = p.name.replace("_", ' ')
        rv += f"""
name={filename}
uri=http://download.xcsoar.org/waypoints/{filename}
type=waypoint
area={area}
update={datetime.date.today().isoformat()}
        """
    with open(out_path, 'w') as f:
        f.write(rv)


if __name__ == '__main__':
    wp_dir = Path(sys.argv[1])
    gen_dir = Path(sys.argv[2])
    gen_dir.mkdir(parents=True, exist_ok=True)

    gen_waypoints_by_country_json(wp_dir, gen_dir / Path("waypoints-by-country.json"))
    gen_waypoints_js(wp_dir, gen_dir / Path("waypoints.js"))
    gen_waypoints_compact_js(wp_dir, gen_dir / Path("waypoints_compact.js"))
    gen_repository_wp_by_country(wp_dir, gen_dir / Path("wp_by_country.repository"))


