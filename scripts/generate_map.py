#!/bin/env python3
"""Auto-generate https://github.com/XCSoar/xcsoar-data-repository/blob/master/data/maps.json."""

import datetime
import json
from pathlib import Path
import subprocess
import sys

from iso3166 import countries


def git_commit_datetime(filename: Path) -> datetime.datetime:
    """Return naive UTC datetime of filename's last git commit."""
    cmd = ['git', 'log', '-1', '--format=%ct', '--', filename]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    out, _ = p.communicate()
    return datetime.datetime.utcfromtimestamp(int(out))


def guess_area(name: str) -> str:
    """From name (e.g. USA_PG_REG1-4), try to guess and return the ISO3166.1-alpha2 code, else empty string."""
    area = ''
    prefix = name.split('_')[0]
    try:
        area = countries.get(prefix).alpha2.lower()
    except KeyError:
        print(f'Could not guess the country code (ISO 3166 alpha2 ) for: {name}')
    return area


def gen_map_json(in_dir: Path, out_path: Path) -> None:
    """Generate a JSON manifest of the out_dir's contents."""
    url = "http://download.xcsoar.org/maps/"
    rv = {"title": "Maps", "records": []}

    for p in sorted(in_dir.glob('*.json')):
        i = {'name': p.stem+'_HighRes.xcm',
             'uri': url + p.stem+'_HighRes.xcm',
             'type': 'map',
             'area': guess_area(p.stem),
             'update': git_commit_datetime(p).date().isoformat()}
        rv['records'].append(i)

        i = {'name': p.stem+'.xcm',
             'uri': url + p.stem+'.xcm',
             'type': 'map',
             'area': guess_area(p.stem),
             'update': git_commit_datetime(p).date().isoformat()}
        rv['records'].append(i)

    with open(out_path, 'w') as f:
        json.dump(rv, f, indent=2, )
    print(f"Created: {out_path}")
    return


def gen_map_repository(in_dir: Path, out_path: Path):
    """Generate section of http://download.xcsoar.org/repository."""
    rv = '# Maps\n'

    for p in sorted(in_dir.glob('*.json')):
        rv += f'''
name={p.stem}_HighRes.xcm
uri=http://download.xcsoar.org/maps/{p.stem}_HighRes.xcm
type=map
area={guess_area(p.stem)}
update={git_commit_datetime(p).date().isoformat()}

name={p.stem}.xcm
uri=http://download.xcsoar.org/maps/{p.stem}.xcm
type=map
area={guess_area(p.stem)}
update={git_commit_datetime(p).date().isoformat()}

'''
    with open(out_path, 'w') as f:
        f.write(rv)
    print(f'Created: {out_path}')
    return


if __name__ == '__main__':
    out_dir = Path(sys.argv[1])
    out_dir.mkdir(parents=True, exist_ok=True)

    map_dir = Path('map')
    gen_map_json(map_dir, out_dir / Path('maps.json'))
    gen_map_repository(map_dir, out_dir / Path('maps.repository'))
