#!/bin/env python3
"""Convert maps.config.js to individual files. TODO: Remove this script when the dust settles."""

from pathlib import Path
import json
import sys


def main(mapfile_config_js: Path, out_dir: Path) -> None:
    """Convert mapfile_config_js to individual JSON files in out_dir."""
    with open(mapfile_config_js) as mf:
        js = mf.read()
    # Remove the 'var MAPS = ' and trailing ';'
    the_json = js[js.find("{") : js.rfind("}") + 1]
    mjson = json.loads(the_json)

    out_dir.mkdir(parents=True, exist_ok=True)
    for k, v in sorted(mjson.items()):
        with open(out_dir / Path(k + ".json"), "w") as out_file:
            the_json = {"bounding_box": v}
            json.dump(
                the_json,
                out_file,
                indent=None,
            )
        print(f"Created: {out_file.name}")


if __name__ == "__main__":
    main(mapfile_config_js=Path(sys.argv[1]), out_dir=Path(sys.argv[2]))
