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
# Some sites turn away requests that don't look like they came from a
# browser-family client. This says plainly what it is, in the standard form.
USER_AGENT = "Mozilla/5.0 (compatible; PortlandEventsDigest/2.0; personal weekday newsletter)"
ACCEPT = "application/json, application/rss+xml, application/xml;q=0.9, text/calendar;q=0.9, text/html;q=0.8, */*;q=0.5"

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
        s.headers["Accept"] = ACCEPT
        s.headers["Accept-Language"] = "en-US,en;q=0.9"
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
