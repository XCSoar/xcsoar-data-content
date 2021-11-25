#!/bin/env python3
"""
Check if all the repository URIs are working.

Either provide a filename as the commandline argument, or nothing to HTTP request the live online repository file.
"""

import os
from pathlib import Path
import random
import sys
import time
from typing import List

import requests


def get_urls_from_www(repo_url: str) -> List[str]:
    """Extract all the URLs after "uri=" at repo_url."""
    repo_req = requests.get(repo_url)

    urls = []
    for line in repo_req.iter_lines():
        decoded_line = line.decode("utf-8")
        if decoded_line.startswith("uri="):
            urls.append(decoded_line[4:])
    return urls


def get_urls_from_file(repo_file: Path) -> List[str]:
    """Extract all the URLs after "uri=" in repo_file."""
    urls = []
    with repo_file.open() as in_file:
        for line in in_file:
            single_line = line.strip()
            if single_line.startswith("uri="):
                urls.append(single_line[4:].strip())
    return urls


def check_urls(urls: List[str]) -> bool:
    """Check (by an HTTP HEAD request) the URLs in urls."""
    rv = True
    for i, url in enumerate(urls):
        req = requests.head(url, allow_redirects=True)
        if req.status_code != requests.codes.ok:
            print(f"{i}\tFAIL {req.status_code} {url}")
            rv = False
    return rv


if __name__ == "__main__":

    if len(sys.argv) > 1:
        url_list = get_urls_from_file(repo_file=Path(sys.argv[1]))
    else:
        if os.getenv("CI") == "true" and os.getenv("GITHUB_EVENT_NAME") == "schedule":
            # Stop all the fork's crontab stampede.
            pause = round(random.random() * 240)
            print(f"Scheduled CI run: sleeping for a random {pause} seconds...")
            time.sleep(pause)

        repository = "http://download.xcsoar.org/repository"
        url_list = get_urls_from_www(repo_url=repository)

    if check_urls(urls=url_list):
        # PASS: All URIs downloaded successfully."
        sys.exit(0)

    print("FAIL: some/all URIs could not be downloaded.")
    sys.exit(1)
