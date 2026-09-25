#!/usr/bin/env python3
"""Check that all the repository URIs work, and that airspace files hold airspace.

A HEAD request only proves that something answered.  An airspace URI that has
started serving an error page or an HTML redirect still passes that test, and
the file reaches the pilot as an airspace file describing nothing -- daec.de in
particular answers a missing file with HTTP 200 and a short error body.  Entries
of type airspace pointing at a .txt are therefore downloaded and parsed.
"""

from __future__ import annotations

import sys
from collections.abc import Iterable, Iterator
from pathlib import Path
from urllib.parse import urlparse

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))

from openair_content import describe, looks_like_openair  # noqa: E402

# Downloading airspace costs a response body rather than a header, so give it room.
_AIRSPACE_TIMEOUT = 120

# A host that refuses the runner says nothing about the file.  gliding.co.nz
# answers 403 to every path including / and /robots.txt from a data centre, so
# treating that as a dead link would fail the check on a file that pilots can
# download perfectly well.  Reported separately instead of failing the run.
_BLOCKED_STATUS = frozenset({403, 429, 451})


def iter_records(lines: Iterable[str]) -> Iterator[dict[str, str]]:
    """Yield the repository manifest's records as key/value dicts.

    A record starts at its "name=" line and runs to the next one; comments and
    blank lines are ignored.
    """
    record: dict[str, str] = {}
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        key, sep, value = line.partition("=")
        if not sep:
            continue
        if key == "name" and record:
            yield record
            record = {}
        record[key] = value
    if record:
        yield record


def get_records_from_www(repo_url: str) -> list[dict[str, str]]:
    """Read the manifest at repo_url."""
    repo_req = requests.get(repo_url, timeout=60)
    repo_req.raise_for_status()
    return list(iter_records(repo_req.text.splitlines()))


def get_records_from_file(repo_file: Path) -> list[dict[str, str]]:
    """Read the manifest at repo_file."""
    with repo_file.open(encoding="utf-8") as in_file:
        return list(iter_records(in_file))


def is_airspace_text(record: dict[str, str]) -> bool:
    """Whether record is an airspace entry served as OpenAir text."""
    if record.get("type") != "airspace":
        return False
    return urlparse(record.get("uri", "")).path.lower().endswith(".txt")


def check_record(record: dict[str, str], session: requests.Session) -> tuple[str, str]:
    """Returns (outcome, message) for one manifest record.

    outcome is "pass", "blocked" or "fail".
    """
    url = record["uri"]

    if not is_airspace_text(record):
        req = session.head(url, allow_redirects=True, timeout=60)
        if req.status_code == requests.codes.ok:
            return "pass", f"pass {req.status_code} {url}"
        if req.status_code in _BLOCKED_STATUS:
            return "blocked", f"BLOCKED {req.status_code} {url}\thost refused this client"
        return "fail", f"FAIL {req.status_code} {url}\t!!!"

    req = session.get(url, allow_redirects=True, timeout=_AIRSPACE_TIMEOUT)
    if req.status_code in _BLOCKED_STATUS:
        return "blocked", f"BLOCKED {req.status_code} {url}\thost refused this client"
    if req.status_code != requests.codes.ok:
        return "fail", f"FAIL {req.status_code} {url}\t!!!"

    # Airspace files are published in whatever encoding the source uses, and the
    # parse only needs the ASCII record keywords, so undecodable bytes are
    # replaced rather than counted as a failure.
    text = req.content.decode(req.encoding or "utf-8", errors="replace")
    verdict = describe(text)
    if not looks_like_openair(text):
        return "fail", f"FAIL {req.status_code} {url}\tno airspace ({verdict})\t!!!"
    return "pass", f"pass {req.status_code} {url}\t{verdict}"


def check_urls(records: list[dict[str, str]]) -> tuple[bool, list[str], list[str]]:
    """Check every record's URI. Returns (all_passed, failed_urls, blocked_urls)."""
    rv = True
    failed_urls = []
    blocked_urls = []
    session = requests.Session()

    for i, record in enumerate(records):
        url = record.get("uri")
        if not url:
            continue
        try:
            outcome, message = check_record(record, session)
        except requests.RequestException as e:
            print(f"{i}\tERROR {url}\t{e}\t!!!")
            failed_urls.append(url)
            rv = False
            continue

        print(f"{i}\t{message}")
        if outcome == "fail":
            failed_urls.append(url)
            rv = False
        elif outcome == "blocked":
            blocked_urls.append(url)

    return rv, failed_urls, blocked_urls


if __name__ == "__main__":
    # allow to specify the repository as argument, as a URL or as a local path
    if len(sys.argv) > 1:
        repo = sys.argv[1]
    else:
        repo = "http://download.xcsoar.org/repository"

    if urlparse(repo).scheme in ("http", "https"):
        record_list = get_records_from_www(repo)
    else:
        record_list = get_records_from_file(Path(repo))

    all_passed, failed, blocked = check_urls(records=record_list)

    if all_passed:
        print("PASS: All URIs downloaded successfully.")
    else:
        print("FAIL: Some/all URIs could not be downloaded.")
        print("Failed URLs:")
        for failed_url in failed:
            print(failed_url)

    if blocked:
        # Not a failure: the host refused this client, which says nothing about
        # the file.  Still worth a human look, because a removed file behind
        # such a host looks exactly the same.
        print("\nBlocked by the host, could not be checked:")
        for blocked_url in blocked:
            print(blocked_url)

    sys.exit(0 if all_passed else 1)
