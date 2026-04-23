"""Webseed (BEP-19) liveness checker.

For every torrent we track, issues an HTTP HEAD on each webseed URL and
persists the status in the meta hash as ``webseed_status`` (JSON map of
``url → {online, code, rtt_ms, size, ts}``). Onion URLs go through Tor
SOCKS5, clearnet URLs go direct.

Threaded via ``concurrent.futures`` so 500 swarms × 10 mirrors completes
in a few minutes even with Tor latency.
"""
from __future__ import annotations

import concurrent.futures
import json
import logging
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import requests  # type: ignore[import-untyped]

from ransomlook.default import get_config
from ransomlook.torrent_health import _redis, list_infohashes, get_meta

logger = logging.getLogger(__name__)

TOR_PROXY = "socks5h://127.0.0.1:9050"
USER_AGENT = "RansomLook/2 webseed liveness"
DEFAULT_TIMEOUT = 30
DEFAULT_WORKERS = 16


def _cfg(key: str, default: Any = None) -> Any:
    try:
        section = get_config("generic", "torrent_webseed_check") or {}
        if isinstance(section, dict):
            return section.get(key, default)
    except Exception:
        pass
    return default


def _iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _is_onion(url: str) -> bool:
    try:
        return (urlparse(url).hostname or "").endswith(".onion")
    except Exception:
        return False


def check_webseed(url: str, timeout: int = DEFAULT_TIMEOUT) -> dict[str, Any]:
    """HEAD one webseed URL and return a compact status dict.

    Falls back to ``GET`` with a 1-byte ``Range`` header if HEAD is not
    supported (some tor-hosted nginx installs return 405 on HEAD).
    """
    proxies = {"http": TOR_PROXY, "https": TOR_PROXY} if _is_onion(url) else None
    start = time.monotonic()
    try:
        r = requests.head(url, timeout=timeout, proxies=proxies,
                          allow_redirects=True,
                          headers={"User-Agent": USER_AGENT})
        if r.status_code == 405:  # HEAD not allowed — try a cheap range GET
            r = requests.get(url, timeout=timeout, proxies=proxies,
                             allow_redirects=True, stream=True,
                             headers={"User-Agent": USER_AGENT, "Range": "bytes=0-0"})
            r.close()
        rtt = int((time.monotonic() - start) * 1000)
        size = int(r.headers.get("Content-Length") or 0)
        # Some servers return 206 (partial) to range probes — still "alive".
        return {
            "online": 200 <= r.status_code < 400,
            "code": r.status_code,
            "rtt_ms": rtt,
            "size": size,
            "ts": _iso(),
        }
    except requests.exceptions.RequestException as e:
        rtt = int((time.monotonic() - start) * 1000)
        return {
            "online": False,
            "code": 0,
            "rtt_ms": rtt,
            "size": 0,
            "ts": _iso(),
            "error": type(e).__name__,
        }


def run_once(*, limit: int | None = None, workers: int = DEFAULT_WORKERS,
             onion_only: bool | None = None) -> dict[str, int]:
    """Check every webseed across all tracked torrents.

    Unique URLs are checked once and the result fanned out to every
    infohash that advertises it — a sensible optimisation because the
    same LockBit (or similar) mirror hosts many leaks.

    Args:
        limit: cap on unique URLs to probe.
        workers: concurrent threads (each holds a Tor circuit briefly).
        onion_only: skip clearnet webseeds. Defaults to config flag.
    """
    if onion_only is None:
        onion_only = bool(_cfg("onion_only", False))

    # Collect webseeds per infohash + build unique URL set.
    url_to_ihs: dict[str, list[str]] = defaultdict(list)
    for ih in list_infohashes():
        meta = get_meta(ih) or {}
        for w in (meta.get("webseeds") or []):
            if onion_only and not _is_onion(w):
                continue
            url_to_ihs[w].append(ih)

    urls = list(url_to_ihs.keys())
    if limit is not None:
        urls = urls[:limit]

    logger.info("webseed check: %d unique URLs across %d torrents (workers=%d)",
                len(urls), sum(len(v) for v in url_to_ihs.values()), workers)

    url_results: dict[str, dict[str, Any]] = {}
    start = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {pool.submit(check_webseed, u): u for u in urls}
        for fut in concurrent.futures.as_completed(futs):
            u = futs[fut]
            try:
                url_results[u] = fut.result()
            except Exception as e:
                url_results[u] = {"online": False, "code": 0, "rtt_ms": 0,
                                  "size": 0, "ts": _iso(),
                                  "error": type(e).__name__}
            res = url_results[u]
            logger.info("  %s %s (code=%s rtt=%dms)",
                        "UP  " if res["online"] else "DOWN",
                        u[:70], res["code"], res["rtt_ms"])

    # Fan out per-infohash and persist.
    r = _redis()
    by_ih: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for url, res in url_results.items():
        for ih in url_to_ihs[url]:
            by_ih[ih][url] = res

    now = _iso()
    for ih, status_map in by_ih.items():
        meta_key = f"torrent_health:meta:{ih}"
        # Merge into any prior status so URLs skipped this run (over limit)
        # keep their last-known value instead of disappearing.
        raw = r.hget(meta_key, "webseed_status")
        prior: dict[str, Any] = {}
        if raw:
            try:
                prior = json.loads(raw.decode() if isinstance(raw, bytes) else raw)
            except Exception:
                prior = {}
        prior.update(status_map)
        r.hset(meta_key, mapping={
            "webseed_status": json.dumps(prior),
            "webseed_last_check": now,
        })

    up = sum(1 for v in url_results.values() if v["online"])
    elapsed = int(time.time() - start)
    logger.info("done: %d UP / %d DOWN / %d torrents updated (%ds)",
                up, len(url_results) - up, len(by_ih), elapsed)
    return {
        "checked": len(url_results),
        "up": up,
        "down": len(url_results) - up,
        "torrents": len(by_ih),
        "elapsed": elapsed,
    }
