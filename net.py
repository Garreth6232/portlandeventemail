"""Shared HTTP session: one timeout, one User-Agent, and retries for the
transient failures (429s, 5xx) that would otherwise drop a source for a day.
"""
from __future__ import annotations

import threading
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

TIMEOUT = 15
USER_AGENT = "portland-events-digest/2.0 (personal newsletter)"

_local = threading.local()


def session() -> requests.Session:
    # Sources are fetched in parallel threads; each gets its own Session.
    if not hasattr(_local, "session"):
        retry = Retry(
            total=3,
            backoff_factor=1.0,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=("GET",),
        )
        s = requests.Session()
        s.headers["User-Agent"] = USER_AGENT
        s.mount("https://", HTTPAdapter(max_retries=retry))
        _local.session = s
    return _local.session


def get(url: str, **kwargs: Any) -> requests.Response:
    kwargs.setdefault("timeout", TIMEOUT)
    resp = session().get(url, **kwargs)
    resp.raise_for_status()
    return resp


def get_json(url: str, **kwargs: Any) -> Any:
    return get(url, **kwargs).json()
