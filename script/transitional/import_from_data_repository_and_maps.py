#!/bin/env python3
"""Import data from https://github.com/XCSoar/xcsoar-data-repository and https://github.com/XCSoar/xcsoar-data-maps."""

import json
import requests
from pathlib import Path

DATA_BASE_URL = (
    "https://raw.githubusercontent.com/XCSoar/xcsoar-data-repository/master/data/"
)

MAP_URL = "https://raw.githubusercontent.com/XCSoar/xcsoar-data-maps/master/data/maps.config.js"

OUTD = Path("data")

# URL location
EXT = OUTD / Path("remote")
INT = OUTD / Path("content")
SRC = OUTD / Path("source")

# Type
WP = Path("waypoint")
WD = Path("waypoint-detail")
AS = Path("airspace")
MP = Path("map")
FN = Path("flarmnet")

# Geography
R = Path("region")
C = Path("country")
G = Path("globe")

FILES = {
    "airspace.json": {"path": EXT / AS / C},  ## Contains internal files!!!
    "flarmnet.json": {"path": EXT / FN / G},
    # "index.js":{"path": Path()},
    "openaip.json": {"path": EXT / WP / G},
    # "waypoints-by-country.json": {"path": INT / WP / C},
    # "airspace-special.json": {"path": INT / AS / R}, ## Repo contains many more files (possibly from airspace.json)!!!
    "gliding-hotspots.json": {"path": EXT / AS / R},
    # Not used. Instead using https://raw.githubusercontent.com/XCSoar/xcsoar-data-maps/master/data/maps.config.js
    # "maps.json": {"path": INT / MP / R},
    "travel-by-glider.json": {"path": EXT / WP / R},
    # "waypoints-special.json": {"path": INT / WP / R},
}


def get_remote_data():
    """Extract the remote data from https://github.com/XCSoar/xcsoar-data-repository ."""
    for filename, d in FILES.items():
        d["path"].mkdir(parents=True, exist_ok=True)

        url = DATA_BASE_URL + filename
        repo_req = requests.get(url)
        in_json = json.loads(repo_req.text)
        for entry in in_json["records"]:
            out_json = {"uri": entry["uri"]}
            outfile = d["path"] / Path(entry["name"] + ".json")

            with outfile.open("w") as f:
                f.write(json.dumps(out_json, indent=None))
                print(f"created: {outfile}")

    # This file contains waypoints and waypoint details:
    wp_details = FILES["travel-by-glider.json"]["path"]
    for name in sorted(wp_details.glob("*Details*.json")):
        out_dir = name.parent.parent.parent / WD / R
        out_dir.mkdir(parents=True, exist_ok=True)
        outfile = name.rename(out_dir / name.name)
        print(f"created: {outfile}")


def get_map_source_data():
    """Extract mapping data from https://github.com/XCSoar/xcsoar-data-maps."""
    js = requests.get(MAP_URL).text

    # Remove the 'var MAPS = ' and trailing ';'
    the_json = js[js.find("{") : js.rfind("}") + 1]
    mjson = json.loads(the_json)

    out_dir = SRC / MP / R
    out_dir.mkdir(parents=True, exist_ok=True)
    for k, v in sorted(mjson.items()):
        with open(out_dir / Path(k + ".xcm.json"), "w") as out_fp:
            the_json = {"bounding_box": v}
            json.dump(
                the_json,
                out_fp,
                indent=None,
            )
        print(f"created: {out_fp.name}")


if __name__ == "__main__":
    get_remote_data()
    get_map_source_data()
