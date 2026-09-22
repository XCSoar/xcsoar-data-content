#!/usr/bin/env python3
"""Check that local airspace files parse as OpenAir, without a single error.

These are the files this repository ships, so a damaged record is ours to fix
and tolerating one gains nothing: it costs the airspace it belongs to, and it
costs the file its bbox, which repository.py derives from the same parser.
Third-party files reached over a URI are judged leniently by check_urls.py
instead, since a defect there cannot be repaired here.

Takes files or directories; directories are searched for *.txt. check.sh passes
a directory, so both have to work.

Files are read as bytes and decoded leniently, because an encoding quirk in a
comment header should not read as missing airspace.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))

from openair_content import describe, is_clean_openair  # noqa: E402


def iter_airspace_files(args: list[str]) -> list[Path]:
    """Expand command line arguments into airspace files."""
    paths: list[Path] = []
    for arg in args:
        path = Path(arg)
        if path.is_dir():
            paths.extend(sorted(path.rglob("*.txt")))
        else:
            paths.append(path)
    return paths


def check_file(path: Path) -> tuple[bool, str]:
    """Returns (ok, message) for one airspace file."""
    try:
        raw = path.read_bytes()
    except OSError as e:
        return False, f"ERROR cannot read: {e}"

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")

    verdict = describe(text)
    if not is_clean_openair(text):
        return False, f"FAIL {verdict}"
    return True, f"pass {verdict}"


def main(args: list[str]) -> int:
    paths = iter_airspace_files(args)
    if not paths:
        print("No airspace files given.", file=sys.stderr)
        return 1

    failures = []
    for path in paths:
        ok, message = check_file(path)
        print(f"{message}\t{path}")
        if not ok:
            failures.append(path)

    if failures:
        print("\nFAIL: airspace files that do not parse cleanly:", file=sys.stderr)
        for path in failures:
            print(path, file=sys.stderr)
        return 1

    print(f"PASS: {len(paths)} airspace files parsed without errors.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
