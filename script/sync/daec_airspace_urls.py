#!/usr/bin/env python3
"""Discover the current DAeC OpenAir URLs for Germany and update remote JSON metadata.

Run locally with --dry-run to preview. CI uses this to open a PR when URIs change.

The DAeC publishes a new national airspace file roughly every three months under a
name that carries its own year and month (``2026_09_Airspace_Germany_OA1.txt``), so
the URI in the repository goes stale on every release and has to be rediscovered.

Two traps make this different from the SoaringWeb sync:

1. The DAeC site answers a missing file with HTTP 200 and a short TYPO3 error body
   instead of a 404, so a status check accepts a dead link.  Every candidate is
   therefore downloaded and checked for actual OpenAir records.
2. The effective date is not the first of the month and not always the 15th (19th
   March 2026, 15th June 2026, 15th September 2026), so ``update`` is taken from
   the file header rather than derived from the file name.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))

from openair_content import looks_like_openair  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
AIRSPACE_COUNTRY = REPO_ROOT / "data" / "remote" / "airspace" / "country"

DAEC_PAGE = "https://www.daec.de/fachbereiche/luftraum-flugsicherheit-betrieb/luftraumdaten/"

# The DAeC site is TYPO3 and answers a plain non-browser Accept with an error page.
_HTML_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0 "
        "(xcsoar-data-content-daec-sync)"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.5",
}
_ANY_HEADERS = {
    "User-Agent": _HTML_HEADERS["User-Agent"],
    "Accept": "*/*",
}

# A national file carries year and month; OA1 today, but the digit is not promised.
_NATIONAL_RE = re.compile(
    r'href="([^"]*?(\d{4})_(\d{2})_Airspace_Germany_OA\d+\.txt)"',
    re.IGNORECASE,
)
_BORDER_RE = re.compile(r'href="([^"]*Grenze_Deutschland\.txt)"', re.IGNORECASE)

# "* effective from 15th September 2026"
_EFFECTIVE_RE = re.compile(
    r"effective\s+from\s+(\d{1,2})\s*(?:st|nd|rd|th)?\s+([A-Za-z]+)\s+(\d{4})",
    re.IGNORECASE,
)

# strptime("%B") follows the runner locale; a fixed table keeps CI and laptop equal.
_MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}

def fetch_html(url: str, session: requests.Session) -> str:
    r = session.get(url, timeout=60, headers=_HTML_HEADERS)
    r.raise_for_status()
    return r.text


def fetch_openair(uri: str, session: requests.Session) -> str | None:
    """Download uri and return its text, or None if it is not an OpenAir file."""
    try:
        r = session.get(uri, timeout=120, headers=_ANY_HEADERS)
    except requests.RequestException:
        return None
    if r.status_code != 200:
        return None

    return r.text if looks_like_openair(r.text) else None


def effective_date(text: str) -> str | None:
    """ISO date from the "effective from" line of an OpenAir file header."""
    m = _EFFECTIVE_RE.search(text)
    if not m:
        return None

    month = _MONTHS.get(m.group(2).lower())
    if month is None:
        return None

    day, year = int(m.group(1)), int(m.group(3))
    if not 1 <= day <= 31:
        return None
    return f"{year:04d}-{month:02d}-{day:02d}"


def pick_national(html: str, page_url: str) -> str | None:
    """Newest dated national OpenAir link on the page."""
    best: tuple[tuple[int, int], str] | None = None
    for m in _NATIONAL_RE.finditer(html):
        key = (int(m.group(2)), int(m.group(3)))
        if best is None or key > best[0]:
            best = (key, urljoin(page_url, m.group(1)))
    return best[1] if best else None


def pick_border(html: str, page_url: str) -> str | None:
    m = _BORDER_RE.search(html)
    return urljoin(page_url, m.group(1)) if m else None


def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: dict) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def sync_one(
    path: Path,
    new_uri: str | None,
    session: requests.Session,
    dry_run: bool,
    *,
    dated: bool,
) -> tuple[bool, str]:
    """Returns (changed, message).

    dated files also carry their effective date in ``update``; the border outline
    has no such field and must not grow one.
    """
    if not new_uri:
        return False, f"FAIL could not discover OpenAir URI from {DAEC_PAGE}"

    data = load_json(path)
    old_uri = data.get("uri", "")
    old_update = data.get("update")

    text = fetch_openair(new_uri, session)
    if text is None:
        return False, f"FAIL new URI is not an OpenAir file: {new_uri}"

    new_update = old_update
    if dated:
        new_update = effective_date(text)
        if new_update is None:
            # Writing today's date here would claim an effective date we did not read.
            return False, f"FAIL no 'effective from' date in {new_uri}"

    if new_uri == old_uri and new_update == old_update:
        return False, "unchanged"

    data["uri"] = new_uri
    if dated:
        data["update"] = new_update

    if dry_run:
        detail = f"\n  old: {old_uri}\n  new: {new_uri}"
        if dated and new_update != old_update:
            detail += f"\n  update: {old_update} -> {new_update}"
        return True, f"would update{detail}"

    save_json(path, data)
    suffix = f" (effective {new_update})" if dated else ""
    return True, f"updated -> {new_uri}{suffix}"


# (json_filename, picker, carries an "update" field)
SYNC_SPECS: list[tuple[str, str, bool]] = [
    ("DE-ASP-Border-DAEC.txt.json", "border", False),
    ("DE-ASP-National-DAEC.txt.json", "national", True),
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Print actions without writing JSON")
    args = parser.parse_args()

    session = requests.Session()

    try:
        html = fetch_html(DAEC_PAGE, session)
    except requests.RequestException as e:
        print(f"FAIL cannot read {DAEC_PAGE}: {e}", file=sys.stderr)
        return 1

    discovered = {
        "national": pick_national(html, DAEC_PAGE),
        "border": pick_border(html, DAEC_PAGE),
    }

    changed_any = False
    failures: list[str] = []

    for name, kind, dated in sorted(SYNC_SPECS):
        path = AIRSPACE_COUNTRY / name
        if not path.exists():
            failures.append(f"missing file: {path}")
            continue
        try:
            changed, msg = sync_one(path, discovered[kind], session, args.dry_run, dated=dated)
            print(f"{name}: {msg}")
            if "FAIL" in msg:
                failures.append(f"{name}: {msg}")
            if changed:
                changed_any = True
        except requests.RequestException as e:
            err = f"{name}: HTTP error {e}"
            print(err)
            failures.append(err)

    if failures:
        print("\nErrors:", file=sys.stderr)
        for f in failures:
            print(f, file=sys.stderr)
        return 1
    if args.dry_run and changed_any:
        print("\nDry run: changes above would be written.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
