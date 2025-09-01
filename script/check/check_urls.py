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


def check_urls(urls: List[str]) -> (bool, List[str]):
    """Check (by an HTTP HEAD request) the URLs in urls."""
    rv = True
    failed_urls = []

    for i, url in enumerate(urls):
        try:
            req = requests.head(url, allow_redirects=True)
            if req.status_code == requests.codes.ok:
                print(f"{i}\tpass {req.status_code} {url}")
            else:
                print(f"{i}\tFAIL {req.status_code} {url}\t!!!")
                failed_urls.append(url)
                rv = False
        except requests.RequestException as e:
            print(f"{i}\tERROR {url}\t{e}\t!!!")
            failed_urls.append(url)
            rv = False

    return rv, failed_urls


if __name__ == "__main__":
    # allow to specify the repository as argument
    if len(sys.argv) > 1:
        repo_url = sys.argv[1]
    else:
        repo_url = "http://download.xcsoar.org/repository"

    url_list = get_urls_from_www(repo_url)
    all_passed, failed_urls = check_urls(urls=url_list)

    if all_passed:
        print("PASS: All URIs downloaded successfully.")
    else:
        print("FAIL: Some/all URIs could not be downloaded.")
        print("Failed URLs:")
        for url in failed_urls:
            print(url)

    sys.exit(0 if all_passed else 1)
