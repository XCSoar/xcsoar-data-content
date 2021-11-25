#!/bin/env python3
"""Check if all the repository URLs are working."""

import sys
import requests
from typing import List
from pathlib import Path


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
        if req.status_code == requests.codes.ok:
            print(f"{i}\tpass {req.status_code} {url}")
        else:
            print(f"{i}\tFAIL {req.status_code} {url}\t!!!")
            rv = False
    return rv


if __name__ == "__main__":

    repository = "http://download.xcsoar.org/repository"

    url_list = get_urls_from_www(repo_url=repository)
    # url_list = get_urls_from_file(repo_file=Path("repository"))
    if check_urls(urls=url_list):
        print("PASS: All URIs downloaded successfully.")
        sys.exit(0)

    print("FAIL: some/all URIs could not be downloaded.")
    sys.exit(1)
