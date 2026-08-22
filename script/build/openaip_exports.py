#!/usr/bin/env python3
"""Access OpenAIP daily system exports (public S3-compatible bucket).

Docs: https://www.openaip.net/docs
Bucket: https://storage.openaip.net/openaip-system-exports/
Rate limits: 20 req/s, bursts up to 50 (see openAIP/openaip#469).
"""

from __future__ import annotations

import re
import threading
import time
from dataclasses import dataclass
from typing import Iterator

import requests

OPENAIP_EXPORTS_BASE_URL = "https://storage.openaip.net/openaip-system-exports/"

# Stay under the documented 20 req/s sustained limit.
_DEFAULT_RATE = 15.0


class _RateLimiter:
    def __init__(self, rate: float = _DEFAULT_RATE) -> None:
        self._min_interval = 1.0 / rate
        self._lock = threading.Lock()
        self._next = 0.0

    def wait(self) -> None:
        with self._lock:
            now = time.monotonic()
            if now < self._next:
                time.sleep(self._next - now)
                now = time.monotonic()
            self._next = now + self._min_interval


_limiter = _RateLimiter()
_session = requests.Session()


@dataclass(frozen=True)
class ExportObject:
    key: str
    size: int
    last_modified: str

    @property
    def url(self) -> str:
        return OPENAIP_EXPORTS_BASE_URL + self.key


def get(url: str, *, timeout: float = 60) -> requests.Response:
    """Rate-limited GET against the exports endpoint (or any URL)."""
    _limiter.wait()
    response = _session.get(url, timeout=timeout)
    response.raise_for_status()
    return response


def iter_exports() -> Iterator[ExportObject]:
    """Yield all objects via anonymous S3 ListObjectsV2 pagination."""
    params: dict[str, str] = {"list-type": "2"}
    while True:
        _limiter.wait()
        response = _session.get(OPENAIP_EXPORTS_BASE_URL, params=params, timeout=60)
        response.raise_for_status()
        xml = response.text

        for content in re.findall(r"<Contents>(.*?)</Contents>", xml, re.DOTALL):
            key = re.search(r"<Key>(.*?)</Key>", content)
            size = re.search(r"<Size>(.*?)</Size>", content)
            modified = re.search(r"<LastModified>(.*?)</LastModified>", content)
            if not (key and size and modified):
                continue
            yield ExportObject(
                key=key.group(1),
                size=int(size.group(1)),
                last_modified=modified.group(1),
            )

        truncated = re.search(r"<IsTruncated>(.*?)</IsTruncated>", xml)
        token = re.search(
            r"<NextContinuationToken>(.*?)</NextContinuationToken>", xml
        )
        if (
            not truncated
            or truncated.group(1).lower() != "true"
            or not token
        ):
            break
        params = {
            "list-type": "2",
            "continuation-token": token.group(1),
        }
