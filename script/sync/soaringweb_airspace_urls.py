#!/usr/bin/env python3
"""Discover current SoaringWeb / silentflight OpenAir URLs and update remote JSON metadata.

Run locally with --dry-run to preview. CI uses this to open a PR when URIs change.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

import requests

REPO_ROOT = Path(__file__).resolve().parents[2]
AIRSPACE_COUNTRY = REPO_ROOT / "data" / "remote" / "airspace" / "country"
SILENTFLIGHT = "https://soaring.silentflight.ca"

# ---------------------------------------------------------------------------
# HTTP + HTML helpers
# ---------------------------------------------------------------------------


def fetch_html(url: str, session: requests.Session) -> str:
    r = session.get(url, timeout=60)
    r.raise_for_status()
    return r.text


def absolutize(page_url: str, href: str) -> str:
    return urljoin(page_url, href)


def normalize_host(uri: str) -> str:
    """Use silentflight as canonical host (mirrors soaringweb.org)."""
    p = urlparse(uri)
    if p.netloc in ("soaringweb.org", "www.soaringweb.org"):
        p2 = p._replace(scheme="https", netloc="soaring.silentflight.ca")
        return p2.geturl()
    return uri


def head_ok(session: requests.Session, uri: str) -> bool:
    try:
        r = session.head(uri, allow_redirects=True, timeout=30)
        if r.status_code == 200:
            return True
        r = session.get(uri, stream=True, timeout=30)
        return r.status_code == 200
    except requests.RequestException:
        return False


# ---------------------------------------------------------------------------
# Link extraction strategies (return first matching absolute URI or None)
# ---------------------------------------------------------------------------

LinkFn = Callable[[str, str, requests.Session], Optional[str]]


def links_openair_basic(html: str, page_url: str) -> list[tuple[str, str]]:
    """Pairs (absolute_uri, href) for typical <A HREF="x.txt">OpenAir format</a>."""
    out: list[tuple[str, str]] = []
    for m in re.finditer(
        r'<A\s+HREF="([^"]+\.txt)"[^>]*>\s*OpenAir\s+format',
        html,
        flags=re.IGNORECASE,
    ):
        href = m.group(1)
        if href.startswith(("http://", "https://")) and "silentflight" not in href and "soaringweb" not in href:
            continue
        out.append((absolutize(page_url, href), href))
    # Lowercase <a> (ES, etc.)
    for m in re.finditer(
        r'<a\s+href="([^"]+\.txt)"[^>]*>\s*OpenAir\s+format',
        html,
        flags=re.IGNORECASE,
    ):
        href = m.group(1)
        if href.startswith(("http://", "https://")) and "silentflight" not in href and "soaringweb" not in href:
            continue
        pair = (absolutize(page_url, href), href)
        if pair not in out:
            out.append(pair)
    return out


def pick_sweden(html: str, page_url: str, _session: requests.Session) -> str | None:
    for abs_u, href in links_openair_basic(html, page_url):
        if re.search(r"Sweden-Airspace-.+\.txt$", href, re.I):
            return normalize_host(abs_u)
    return None


def pick_first_openair(html: str, page_url: str, _session: requests.Session) -> str | None:
    for abs_u, _ in links_openair_basic(html, page_url):
        return normalize_host(abs_u)
    return None


def pick_es_full(html: str, page_url: str, _session: requests.Session) -> str | None:
    for abs_u, href in links_openair_basic(html, page_url):
        if ".full.txt" in href.lower():
            return normalize_host(abs_u)
    return pick_first_openair(html, page_url, _session)


def pick_nl_main(html: str, page_url: str, _session: requests.Session) -> str | None:
    for abs_u, href in links_openair_basic(html, page_url):
        if "PJE" in href.upper():
            continue
        if re.match(r"NL-ASP_.+\.txt$", href, re.I):
            return normalize_host(abs_u)
    return None


def pick_dk_combined(html: str, page_url: str, _session: requests.Session) -> str | None:
    for abs_u, href in links_openair_basic(html, page_url):
        if re.match(r"DK-Airspace-\d{8}\.txt$", href, re.I):
            return normalize_host(abs_u)
    return None


def pick_na_can_all(html: str, page_url: str, _session: requests.Session) -> str | None:
    best: tuple[int, str] | None = None
    for m in re.finditer(r'<A\s+HREF="(CanAirspace(\d+)all\.txt)"', html, flags=re.I):
        href, num = m.group(1), int(m.group(2))
        u = normalize_host(absolutize(page_url, href))
        if best is None or num > best[0]:
            best = (num, u)
    return best[1] if best else None


def pick_na_allusa(html: str, page_url: str, _session: requests.Session) -> str | None:
    for m in re.finditer(r'<A\s+HREF="(allusa[^"]+\.txt)"', html, flags=re.I):
        return normalize_host(absolutize(page_url, m.group(1)))
    return None


def pick_be_weekday(html: str, page_url: str, _session: requests.Session) -> str | None:
    m = re.search(r'<A\s+HREF="(BELLUX_WEEK[^"]*\.txt)"[^>]*>\s*Weekdays', html, flags=re.I)
    if m:
        return normalize_host(absolutize(page_url, m.group(1)))
    return None


def pick_be_weekend(html: str, page_url: str, _session: requests.Session) -> str | None:
    m = re.search(r'<A\s+HREF="(BELLUX_W-END[^"]*\.txt)"[^>]*>\s*Weekends', html, flags=re.I)
    if m:
        return normalize_host(absolutize(page_url, m.group(1)))
    return None


def pick_au_all_classes(html: str, page_url: str, _session: requests.Session) -> str | None:
    m = re.search(
        r'<STRONG>\s*All Classes\s*</strong>\s*:\s*<A\s+HREF="([^"]+\.txt)"',
        html,
        flags=re.IGNORECASE,
    )
    if m:
        return normalize_host(absolutize(page_url, m.group(1)))
    return None


def pick_il_listing(html: str, page_url: str, _session: requests.Session) -> str | None:
    m = re.search(r'<a\s+href="(israel[^"]+\.txt)"', html, flags=re.I)
    if m:
        return normalize_host(absolutize(page_url, m.group(1)))
    return pick_first_openair(html, page_url, _session)


def pick_za_sssa(html: str, page_url: str, _session: requests.Session) -> str | None:
    m = re.search(r'HREF="([^"]*SSSA[^"]*\.txt)"', html, flags=re.I)
    if m:
        return normalize_host(absolutize(page_url, m.group(1)))
    return None


def pick_it_primary(html: str, page_url: str, _session: requests.Session) -> str | None:
    for abs_u, href in links_openair_basic(html, page_url):
        if "ITA_ASP" in href.upper():
            return normalize_host(abs_u)
    return pick_first_openair(html, page_url, _session)


# (json_filename, page_url, picker)
SYNC_SPECS: list[tuple[str, str, LinkFn]] = [
    ("SE-ASP-National-SoaringWeb.txt.json", f"{SILENTFLIGHT}/Airspace/SE/", pick_sweden),
    ("AU-ASP-National-SoaringWeb.txt.json", f"{SILENTFLIGHT}/Airspace/AU.html", pick_au_all_classes),
    ("BE-ASP-NationalWeekend-SoaringWeb.txt.json", f"{SILENTFLIGHT}/Airspace/BE/HomePage.html", pick_be_weekend),
    ("BE-ASP-NationalWeek-SoaringWeg.txt.json", f"{SILENTFLIGHT}/Airspace/BE/HomePage.html", pick_be_weekday),
    ("BR-ASP-National-SoaringWeb.txt.json", f"{SILENTFLIGHT}/Airspace/BR/", pick_first_openair),
    ("CN-ASP-National-Soaringweb.txt.json", f"{SILENTFLIGHT}/Airspace/NA/HomePage.html", pick_na_can_all),
    ("DK-ASP-National-SoaringWeb.txt.json", f"{SILENTFLIGHT}/Airspace/DK/", pick_dk_combined),
    ("ES-ASP-National-SoaringWeb.txt.json", f"{SILENTFLIGHT}/Airspace/ES/", pick_es_full),
    ("FI-ASP-National-SoaringWeb.txt.json", f"{SILENTFLIGHT}/Airspace/FI/", pick_first_openair),
    ("GR-ASP-National-SoaringWeb.txt.json", f"{SILENTFLIGHT}/Airspace/GR/", pick_first_openair),
    ("HR-ASP-National-SoaringWeb.txt.json", f"{SILENTFLIGHT}/Airspace/HR/", pick_first_openair),
    ("HU-ASP-National-SoaringWeb.txt.json", f"{SILENTFLIGHT}/Airspace/HU/", pick_first_openair),
    ("IE-ASP-National-SoaringWeb.txt.json", f"{SILENTFLIGHT}/Airspace/EI/", pick_first_openair),
    ("IL-ASP-National-SoaringWeb.txt.json", f"{SILENTFLIGHT}/Airspace/IL/", pick_il_listing),
    ("IT-ASP-National-SoaringWeb.txt.json", f"{SILENTFLIGHT}/Airspace/IT/", pick_it_primary),
    ("JP-ASP-National-SoaringWeb.txt.json", f"{SILENTFLIGHT}/Airspace/JP/", pick_first_openair),
    ("LT-ASP-National-SoaringWeb.txt.json", f"{SILENTFLIGHT}/Airspace/LT/", pick_first_openair),
    ("LV-ASP-National-SoaringWeb.txt.json", f"{SILENTFLIGHT}/Airspace/LV/", pick_first_openair),
    ("NL-ASP-National-SoaringWeb.txt.json", f"{SILENTFLIGHT}/Airspace/NL/", pick_nl_main),
    ("PL-ASP-National-SoaringWeb.txt.json", f"{SILENTFLIGHT}/Airspace/PL/", pick_first_openair),
    ("RO-ASP-National-SoaringWeb.txt.json", f"{SILENTFLIGHT}/Airspace/RO/", pick_first_openair),
    ("SI-ASP-National-SoaringWeb.txt.json", f"{SILENTFLIGHT}/Airspace/SI/", pick_first_openair),
    ("UA-ASP-National-SoaringWeb.txt.json", f"{SILENTFLIGHT}/Airspace/UA/", pick_first_openair),
    ("US-ASP-National-SoaringWeb.txt.json", f"{SILENTFLIGHT}/Airspace/NA/HomePage.html", pick_na_allusa),
    ("ZA-ASP-National-SoaringWeb.txt.json", f"{SILENTFLIGHT}/Airspace/ZA/", pick_za_sssa),
]


def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: dict) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def sync_one(
    path: Path,
    page_url: str,
    picker: LinkFn,
    session: requests.Session,
    dry_run: bool,
) -> tuple[bool, str]:
    """Returns (changed, message)."""
    data = load_json(path)
    old_uri = data.get("uri", "")

    html = fetch_html(page_url, session)
    new_uri = picker(html, page_url, session)
    if not new_uri:
        return False, f"FAIL could not discover OpenAir URI from {page_url}"

    new_uri = normalize_host(new_uri)
    if new_uri == old_uri:
        return False, "unchanged"

    if not head_ok(session, new_uri):
        return False, f"FAIL new URI not retrievable: {new_uri}"

    today = datetime.now(timezone.utc).date().isoformat()

    data["uri"] = new_uri
    data["update"] = today
    if dry_run:
        return True, f"would update\n  old: {old_uri}\n  new: {new_uri}"
    save_json(path, data)
    return True, f"updated -> {new_uri}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Print actions without writing JSON")
    args = parser.parse_args()

    session = requests.Session()
    session.headers.update({"User-Agent": "xcsoar-data-content-soaringweb-sync/1.0"})

    changed_any = False
    failures: list[str] = []

    specs = sorted(SYNC_SPECS, key=lambda x: x[0])
    at_path = AIRSPACE_COUNTRY / "AT-ASP-National-SoaringWeb.txt.json"
    if at_path.exists():
        print("AT-ASP-National-SoaringWeb.txt.json: skip AT (Austro Control direct URL, not discoverable from SoaringWeb pages)")

    for name, page_url, picker in specs:
        path = AIRSPACE_COUNTRY / name
        if not path.exists():
            failures.append(f"missing file: {path}")
            continue
        try:
            changed, msg = sync_one(path, page_url, picker, session, args.dry_run)
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
