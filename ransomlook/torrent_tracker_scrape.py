"""BEP-48 HTTP scrape on BT trackers (clearnet + Tor onion).

For every torrent we track, :func:`run_once` groups its announce URLs by
tracker, batches the infohashes, and issues a single ``/scrape`` HTTP GET
per batch. The response is a bencoded dict
``{files: {<ih_bin>: {complete, incomplete, downloaded}}}``.

This is much lighter than running libtorrent over Tor:
- No DHT/uTP (UDP doesn't pass SOCKS5 → no IP leak risk).
- 1 HTTP GET per tracker batch instead of 300s of peer gossip.
- Returns the same KPIs we care about (seeders/leechers) plus ``downloaded``
  (total historical completions) which libtorrent does not expose.

Peer enumeration is lost — but peers on LockBit-style private onion
trackers are themselves .onion addresses, so pivoting on IP/ASN is
impossible anyway. We keep only the numeric KPIs.
"""
from __future__ import annotations

import json
import logging
import os
import socket
import struct
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote, urlparse, urlunparse

import requests  # type: ignore[import-untyped]

from ransomlook.default import get_config
from ransomlook.torrent_health import _redis, list_infohashes, get_meta

logger = logging.getLogger(__name__)

TOR_PROXY = "socks5h://127.0.0.1:9050"
USER_AGENT = "RansomLook/2 BEP-48 tracker scraper"
BATCH_SIZE = 64
DEFAULT_TIMEOUT = 45


# ─── minimal bencode decoder ────────────────────────────────────────────
def _bdecode(data: bytes) -> Any:
    def _decode(i: int) -> tuple[Any, int]:
        c = data[i:i + 1]
        if c == b"i":
            end = data.index(b"e", i)
            return int(data[i + 1:end]), end + 1
        if c == b"l":
            lst: list[Any] = []
            i += 1
            while data[i:i + 1] != b"e":
                v, i = _decode(i)
                lst.append(v)
            return lst, i + 1
        if c == b"d":
            d: dict[Any, Any] = {}
            i += 1
            while data[i:i + 1] != b"e":
                k, i = _decode(i)
                v, i = _decode(i)
                d[k] = v
            return d, i + 1
        if c.isdigit():
            colon = data.index(b":", i)
            length = int(data[i:colon])
            start = colon + 1
            return data[start:start + length], start + length
        raise ValueError(f"bencode: unexpected char {c!r} at offset {i}")
    result, _ = _decode(0)
    return result


def _cfg(key: str, default: Any = None) -> Any:
    try:
        section = get_config("generic", "torrent_tracker_scrape") or {}
        if isinstance(section, dict):
            return section.get(key, default)
    except Exception:
        pass
    return default


# ─── URL helpers ────────────────────────────────────────────────────────
def _scrape_url_from_announce(announce_url: str) -> str | None:
    """BEP-48: replace the final ``announce`` in the path with ``scrape``.

    Returns ``None`` when the tracker advertises no scrape endpoint (the
    announce URL does not contain ``announce`` in its path). For UDP
    trackers (BEP-15) the announce URL IS the scrape endpoint — we keep
    it as-is and the caller branches on the ``udp://`` scheme.
    """
    try:
        p = urlparse(announce_url)
    except Exception:
        return None
    if p.scheme == "udp":
        # BEP-15: no /scrape path, the announce endpoint also handles scrape
        # via the action field in the binary protocol. Return as-is.
        return announce_url
    if not p.scheme.startswith("http"):
        return None  # ws/wss/other exotic schemes — skip
    idx = p.path.rfind("announce")
    if idx < 0:
        return None
    new_path = p.path[:idx] + "scrape" + p.path[idx + len("announce"):]
    return urlunparse(p._replace(path=new_path))


def _is_onion(url: str) -> bool:
    try:
        return urlparse(url).hostname.endswith(".onion")  # type: ignore[union-attr]
    except Exception:
        return False


def _encode_infohash(ih_hex: str) -> str:
    """20-byte binary infohash → percent-encoded string for the query."""
    return quote(bytes.fromhex(ih_hex), safe="")


# ─── scraping ───────────────────────────────────────────────────────────
# ─── BEP-15: UDP tracker scrape ─────────────────────────────────────────
# Two-phase protocol:
#   1. Connection request  (16B) → connection response (16B, connection_id)
#   2. Scrape request      (16 + 20*N B) → scrape response (8 + 12*N B)
# See https://www.bittorrent.org/beps/bep_0015.html
_UDP_MAGIC = 0x41727101980   # protocol_id for connection request
_UDP_ACTION_CONNECT = 0
_UDP_ACTION_SCRAPE = 2
_UDP_ACTION_ERROR = 3


def _udp_scrape(host: str, port: int, infohashes: list[str], *,
                timeout: int = 10) -> dict[str, dict[str, int]]:
    """BEP-15 UDP tracker scrape. Clearnet only (UDP does not pass SOCKS5).

    Single attempt with ``timeout`` seconds. No retry — caller decides.
    """
    if not infohashes:
        return {}
    addrs = socket.getaddrinfo(host, port, type=socket.SOCK_DGRAM)
    if not addrs:
        raise OSError(f"resolve failed: {host}")
    family, _, _, _, sockaddr = addrs[0]

    with socket.socket(family, socket.SOCK_DGRAM) as s:
        s.settimeout(timeout)

        # ── Phase 1: connection request / response ───────────────────────
        tx1 = int.from_bytes(os.urandom(4), "big")
        s.sendto(struct.pack(">QII", _UDP_MAGIC, _UDP_ACTION_CONNECT, tx1),
                 sockaddr)
        data, _ = s.recvfrom(65535)
        if len(data) < 16:
            raise ValueError("short connect response")
        action, tx, connection_id = struct.unpack(">IIQ", data[:16])
        if action == _UDP_ACTION_ERROR:
            raise ValueError(f"tracker error: {data[8:].decode('utf-8', 'replace')}")
        if action != _UDP_ACTION_CONNECT or tx != tx1:
            raise ValueError(f"unexpected connect response (action={action})")

        # ── Phase 2: scrape request / response ───────────────────────────
        tx2 = int.from_bytes(os.urandom(4), "big")
        header = struct.pack(">QII", connection_id, _UDP_ACTION_SCRAPE, tx2)
        payload = b"".join(bytes.fromhex(ih) for ih in infohashes)
        s.sendto(header + payload, sockaddr)
        data, _ = s.recvfrom(65535)
        if len(data) < 8:
            raise ValueError("short scrape response")
        action, tx = struct.unpack(">II", data[:8])
        if action == _UDP_ACTION_ERROR:
            raise ValueError(f"tracker error: {data[8:].decode('utf-8', 'replace')}")
        if action != _UDP_ACTION_SCRAPE or tx != tx2:
            raise ValueError(f"unexpected scrape response (action={action})")

        body = data[8:]
        if len(body) != 12 * len(infohashes):
            raise ValueError(f"scrape body size mismatch: got {len(body)}, "
                             f"expected {12 * len(infohashes)}")
        out: dict[str, dict[str, int]] = {}
        for i, ih in enumerate(infohashes):
            complete, downloaded, incomplete = struct.unpack(
                ">III", body[i * 12:(i + 1) * 12])
            out[ih.lower()] = {
                "complete": int(complete),
                "incomplete": int(incomplete),
                "downloaded": int(downloaded),
            }
        return out


def _do_scrape_request(scrape_url: str, infohashes: list[str], *, tor: bool,
                       timeout: int) -> dict[str, dict[str, int]]:
    qs = "&".join(f"info_hash={_encode_infohash(ih)}" for ih in infohashes)
    sep = "&" if urlparse(scrape_url).query else "?"
    url = f"{scrape_url}{sep}{qs}"
    proxies = {"http": TOR_PROXY, "https": TOR_PROXY} if tor else None
    logger.debug("GET %s (%d infohashes)", scrape_url, len(infohashes))
    r = requests.get(url, headers={"User-Agent": USER_AGENT},
                     proxies=proxies, timeout=timeout)
    r.raise_for_status()
    raw = r.content
    logger.debug("response %d bytes: %s", len(raw), raw[:200])
    decoded = _bdecode(raw)
    if not isinstance(decoded, dict):
        raise ValueError("scrape: non-dict response")
    if b"failure reason" in decoded:
        reason = decoded[b"failure reason"]
        if isinstance(reason, (bytes, bytearray)):
            reason = reason.decode("utf-8", "replace")
        raise ValueError(f"tracker failure: {reason}")
    files = decoded.get(b"files") or {}
    if not isinstance(files, dict):
        raise ValueError("scrape: 'files' key missing or wrong type")
    out: dict[str, dict[str, int]] = {}
    for ih_bin, stats in files.items():
        if not isinstance(ih_bin, (bytes, bytearray)) or len(ih_bin) != 20:
            continue
        if not isinstance(stats, dict):
            continue
        out[ih_bin.hex().lower()] = {
            "complete": int(stats.get(b"complete", 0) or 0),
            "incomplete": int(stats.get(b"incomplete", 0) or 0),
            "downloaded": int(stats.get(b"downloaded", 0) or 0),
        }
    return out


def scrape_tracker(scrape_url: str, infohashes: list[str], *, tor: bool,
                   timeout: int = DEFAULT_TIMEOUT) -> dict[str, dict[str, int]]:
    """Scrape a tracker for a batch of infohashes.

    Returns ``{ih_hex: {complete, incomplete, downloaded}}``. Missing
    infohashes (unknown to the tracker) are simply absent from the result.

    Routes by scheme:
    * ``http(s)://`` — BEP-48 multi-infohash GET; falls back to one request
      per infohash if the tracker rejects the batch.
    * ``udp://`` — BEP-15 binary scrape; Tor-incompatible (UDP doesn't
      pass SOCKS5), handled clearnet-only by the caller.
    """
    if not infohashes:
        return {}
    parsed = urlparse(scrape_url)
    if parsed.scheme == "udp":
        host = parsed.hostname or ""
        port = parsed.port or 80
        return _udp_scrape(host, port, infohashes, timeout=timeout)

    out = _do_scrape_request(scrape_url, infohashes, tor=tor, timeout=timeout)
    if not out and len(infohashes) > 1:
        logger.info("batch returned 0 — tracker likely single-infohash only, falling back")
        merged: dict[str, dict[str, int]] = {}
        for ih in infohashes:
            try:
                one = _do_scrape_request(scrape_url, [ih], tor=tor, timeout=timeout)
            except Exception as e:
                logger.debug("single scrape %s: %s", ih, e)
                continue
            merged.update(one)
        return merged
    return out


def _persist(ih: str, scrape_url: str, stats: dict[str, int]) -> None:
    r = _redis()
    meta_key = f"torrent_health:meta:{ih}"
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    mapping = {
        "tracker_last_scrape": now_iso,
        "tracker_last_url": scrape_url,
        "tracker_seeders": str(stats["complete"]),
        "tracker_leechers": str(stats["incomplete"]),
        "tracker_downloaded": str(stats["downloaded"]),
    }
    # Tiny historical ring — last 30 measurements, for a future sparkline.
    existing = r.hget(meta_key, "tracker_history")
    history: list[dict[str, Any]] = []
    if existing:
        try:
            history = json.loads(existing.decode() if isinstance(existing, bytes) else existing)
        except Exception:
            history = []
    history.append({"ts": now_iso, **stats})
    mapping["tracker_history"] = json.dumps(history[-30:])
    r.hset(meta_key, mapping=mapping)


def run_once(*, limit: int | None = None, only_onion: bool | None = None,
             clearnet_too: bool | None = None) -> dict[str, int]:
    """Scrape all known trackers for all tracked torrents.

    Args:
        limit: Stop after this many total tracker requests (batches),
            regardless of how many infohashes remain. Useful for tests or
            staggered runs. ``None`` means exhaustive.
        only_onion: When True, skip clearnet trackers. Defaults to the
            ``only_onion`` config flag (True if unset).
        clearnet_too: Back-compat alias; True forces clearnet even when
            ``only_onion`` is on.
    """
    if only_onion is None:
        only_onion = bool(_cfg("only_onion", True))
    if clearnet_too:
        only_onion = False

    # Group infohashes by scrape URL. Some torrents advertise several
    # trackers — we scrape every one so we capture the most active swarm.
    tracker_to_ihs: dict[str, list[str]] = defaultdict(list)
    for ih in list_infohashes():
        meta = get_meta(ih) or {}
        trackers = meta.get("trackers") or []
        for ann in trackers:
            is_onion = _is_onion(ann)
            scheme = (urlparse(ann).scheme or "").lower()
            # ``only_onion`` means "restrict to onion-reachable trackers".
            # UDP can't be tunnelled through SOCKS5, so UDP is always
            # dropped under only_onion. Non-onion HTTP(S)/UDP are kept
            # only when only_onion is False.
            if only_onion:
                if scheme == "udp" or not is_onion:
                    continue
            scrape = _scrape_url_from_announce(ann)
            if scrape:
                tracker_to_ihs[scrape].append(ih)

    total_scraped = 0
    total_errors = 0
    total_batches = 0
    start = time.time()

    for scrape_url, ihs in tracker_to_ihs.items():
        scheme = (urlparse(scrape_url).scheme or "").lower()
        tor = scheme != "udp" and _is_onion(scrape_url)
        logger.info("scrape %s (%d infohashes, scheme=%s tor=%s)",
                    scrape_url, len(ihs), scheme, tor)
        for i in range(0, len(ihs), BATCH_SIZE):
            if limit is not None and total_batches >= limit:
                logger.info("limit reached after %d batches", total_batches)
                break
            chunk = ihs[i:i + BATCH_SIZE]
            total_batches += 1
            try:
                stats_map = scrape_tracker(scrape_url, chunk, tor=tor)
            except Exception as e:
                total_errors += 1
                logger.warning("scrape %s batch %d: %s", scrape_url, i // BATCH_SIZE, e)
                continue
            for ih, stats in stats_map.items():
                _persist(ih, scrape_url, stats)
                total_scraped += 1
            logger.info("  batch %d: %d/%d returned stats",
                        i // BATCH_SIZE, len(stats_map), len(chunk))
        if limit is not None and total_batches >= limit:
            break

    elapsed = time.time() - start
    logger.info("scrape finished: %d results across %d trackers (%d batches, %d errors, %.1fs)",
                total_scraped, len(tracker_to_ihs), total_batches, total_errors, elapsed)
    return {
        "scraped": total_scraped,
        "trackers": len(tracker_to_ihs),
        "batches": total_batches,
        "errors": total_errors,
        "elapsed": int(elapsed),
    }
