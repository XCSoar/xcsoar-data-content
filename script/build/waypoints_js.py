#!/bin/env python3
"""
Auto-generate these files from directory listing xcsoar-data-content/waypoints:

xcsoar-data-repository/data/waypoints-by-country.json
xcsoar-data-content/waypoints/waypoints.js
xcsoar-data-content/waypoints/waypoints_compact.js
(partially) http://download.xcsoar.org/repository
"""

import datetime
import json
from pathlib import Path
import subprocess
import sys

from aerofiles.seeyou.reader import Reader as CupReader
from iso3166 import countries


def file_length(in_file: Path) -> int:
    """Return in_file's line count."""
    with open(in_file) as fp:
        x = len(fp.readlines())
    return x


def git_commit_datetime(filename: Path) -> datetime.datetime:
    """Return naive UTC datetime of filename's last git commit."""
    cmd = ["git", "log", "-1", "--format=%ct", "--", filename]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    out, _ = p.communicate()
    return datetime.datetime.utcfromtimestamp(int(out))


def waypoint_mean(filename: Path) -> tuple:
    """Return the (latitude, longitude) tuple mean of waypoint filename."""

    try:
        waypoints = CupReader().read(open(filename))["waypoints"]
    except:
        print("Failing file: " + str(filename))
        sys.exit()

    cum_lat, cum_lon, count = 0.0, 0.0, 0
    for wp in waypoints:
        count += 1
        cum_lat += wp["latitude"]
        cum_lon += wp["longitude"]

    return cum_lat / count, cum_lon / count


def gen_waypoints_js(in_dir: Path, out_path: Path) -> None:
    """Generate http://download.xcsoar.org/waypoints/waypoints.js"""
    rv = {}
    for p in sorted(in_dir.glob("*.cup")):
        rv[p.stem] = {
            "size": file_length(p),
            "average": waypoint_mean(p),
        }

    with open(out_path, "w") as f:
        f.write("var WAYPOINTS = ")  # TODO: Use json rather than js.
        json.dump(
            rv,
            f,
            indent=2,
        )
    print(f"Created: {out_path}")


def gen_waypoints_compact_js(in_dir: Path, out_path: Path) -> None:
    """Generate http://download.xcsoar.org/waypoints/waypoints_compact.js"""
    rv = {}
    for p in sorted(in_dir.glob("*.cup")):
        rv[p.stem] = file_length(p)

    with open(out_path, "w") as f:
        f.write("var WAYPOINTS = ")  # TODO: Use json rather than js.
        json.dump(
            rv,
            f,
            indent=2,
        )
    print(f"Created: {out_path}")


def guess_area(name: str) -> str:
    """From name (e.g. USA_PG_REG1-4), try to guess and return the ISO3166.1-alpha2 code, else empty string."""
    area = ""
    prefix = name.split(".")[0].split("_")[0]
    try:
        area = countries.get(prefix).alpha2.lower()
    except KeyError:
        print(f"Could not guess the country code (ISO 3166 alpha2 ) for: {name}")
    return area


if __name__ == "__main__":
    wp_dir = Path(sys.argv[1])
    gen_dir = Path(sys.argv[2])
    gen_dir.mkdir(parents=True, exist_ok=True)

    gen_waypoints_js(wp_dir, gen_dir / Path("waypoints.js"))
    gen_waypoints_compact_js(wp_dir, gen_dir / Path("waypoints_compact.js"))
