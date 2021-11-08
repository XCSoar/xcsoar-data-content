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


def file_length(in_file: Path) -> int:
    """Return in_file's line count."""
    with open(in_file, 'r') as fp:
        x = len(fp.readlines())
    return x


def git_commit_datetime(filename: Path) -> datetime.datetime:
    """Return naive UTC datetime of filename's last git commit."""
    cmd = ['git', 'log', '-1', '--format=%ct', '--', filename]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    out, err = p.communicate()
    return datetime.datetime.utcfromtimestamp(int(out))


def gen_waypoints_by_country_json(in_dir: Path, out_path: Path) -> None:
    """
    Generate a JSON manifest of the wp_dir's contents. e.g.
    https://github.com/XCSoar/xcsoar-data-repository/blob/master/data/waypoints-by-country.json
    """

    url = "http://download.xcsoar.org/waypoints/"
    rv = {"title": "Waypoints-by-Country", "records": []}

    for p in sorted(in_dir.glob('*.cup')):
        i = {'name': p.name,
             'uri': url + p.name,
             'type': 'waypoint',
             'area': p.stem.lower(),
             'update': git_commit_datetime(p).date().isoformat()}
        rv['records'].append(i)

    with open(out_path, 'w') as f:
        json.dump(rv, f, indent=2, )
    print(f"Created: {out_path}")
    return


def waypoint_mean(filename: Path) -> tuple:
    """Return the (latitude, longitude) tuple mean of waypoint filename."""

    waypoints = CupReader().read(open(filename))['waypoints']

    cum_lat, cum_lon, count = 0.0, 0.0, 0
    for wp in waypoints:
        count += 1
        cum_lat += wp['latitude']
        cum_lon += wp['longitude']

    return cum_lat / count, cum_lon / count


def gen_waypoints_js(in_dir: Path, out_path: Path) -> None:
    """Generate http://download.xcsoar.org/waypoints/waypoints.js"""
    rv = {}
    for p in sorted(in_dir.glob('*.cup')):
        rv[p.stem] = {
            'size': file_length(p),
            'average': waypoint_mean(p),
        }

    with open(out_path, 'w') as f:
        f.write('var WAYPOINTS = ')    # TODO: Use json rather than js.
        json.dump(rv, f, indent=2,)
    print(f'Created: {out_path}')


def gen_waypoints_compact_js(in_dir: Path, out_path: Path) -> None:
    """Generate http://download.xcsoar.org/waypoints/waypoints_compact.js"""
    rv = {}
    for p in sorted(in_dir.glob('*.cup')):
        rv[p.stem] = file_length(p)

    with open(out_path, 'w') as f:
        f.write('var WAYPOINTS = ')    # TODO: Use json rather than js.
        json.dump(rv, f, indent=2,)
    print(f'Created: {out_path}')

def gen_waypoints_by_country_repository(in_dir: Path, out_path: Path):
    """Generate section of http://download.xcsoar.org/repository."""
    rv = '# Waypoints-by-Country\n'

    for p in sorted(in_dir.glob('*.cup')):
        rv += f'''
name={p.name}
uri=http://download.xcsoar.org/waypoints/{p.name}
type=waypoint
area={p.stem.lower()}
update={git_commit_datetime(p).date().isoformat()}
'''
    with open(out_path, 'w') as f:
        f.write(rv)
    print(f'Created: {out_path}')
    return


if __name__ == '__main__':
    wp_dir = Path(sys.argv[1])
    gen_dir = Path(sys.argv[2])
    gen_dir.mkdir(parents=True, exist_ok=True)

    gen_waypoints_by_country_json(wp_dir, gen_dir / Path('waypoints-by-country.json'))
    gen_waypoints_js(wp_dir, gen_dir / Path('waypoints.js'))
    gen_waypoints_compact_js(wp_dir, gen_dir / Path('waypoints_compact.js'))
    gen_waypoints_by_country_repository(wp_dir, gen_dir / Path('waypoints-by-country.repository'))
