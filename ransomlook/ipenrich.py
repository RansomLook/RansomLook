"""IP enrichment via CIRCL IP ASN History + local reverse DNS.

Cached in :data:`DB_TORRENT_HEALTH` under ``ipenrich:<ip>`` with a 7-day TTL.
A single public endpoint (``https://ipasnhistory.circl.lu/``) is queried;
no third-party geolocation provider is used.

Record shape::

    {
      "ip": str,
      "asn": str | None,
      "asn_org": str | None,
      "country": str | None,   # 2-letter ISO code when CIRCL provides it
      "ptr": str | None,
      "fetched_at": "YYYY-MM-DDTHH:MM:SSZ",
    }
"""

from __future__ import annotations

import json
import logging
import socket
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

import valkey

from .default import DB_TORRENT_HEALTH, get_socket_path
from .default.config import get_config

logger = logging.getLogger(__name__)

CACHE_SCHEMA = 2  # bump when the record shape or source changes — busts stale entries
CIRCL_IPASN_URL = "https://ipasnhistory.circl.lu/ip"
CIRCL_BGPRANKING_ASN_URL = "https://bgpranking-ng.circl.lu/json/asn"
HTTP_TIMEOUT = 5.0
DNS_TIMEOUT = 2.0
USER_AGENT = "RansomLook/2.0 ipenrich"
_DEFAULT_TTL_DAYS = 7


def _cache_ttl_seconds() -> int | None:
    """Return cache TTL in seconds, or ``None`` when unlimited (config = 0)."""
    try:
        section = get_config("generic", "torrent_health", quiet=True) or {}
        days = int(section.get("ip_cache_ttl_days", _DEFAULT_TTL_DAYS))
    except Exception:
        days = _DEFAULT_TTL_DAYS
    return None if days <= 0 else days * 86400


def _redis() -> valkey.Valkey:
    return valkey.Valkey(unix_socket_path=get_socket_path("cache"), db=DB_TORRENT_HEALTH)


def _cache_key(ip: str) -> str:
    return f"ipenrich:{ip}"


def _reverse_dns(ip: str) -> str | None:
    try:
        # gethostbyaddr does not expose a timeout parameter; use the default socket timeout.
        socket.setdefaulttimeout(DNS_TIMEOUT)
        host, _, _ = socket.gethostbyaddr(ip)
        return host
    except Exception:
        return None
    finally:
        socket.setdefaulttimeout(None)


def _http_json(url: str, method: str = "GET", body: dict[str, Any] | None = None) -> dict[str, Any] | None:
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
            raw = resp.read()
        return json.loads(raw)
    except Exception as e:
        logger.debug("HTTP %s %s failed: %s", method, url, e)
        return None


def _most_recent_value(mapping: dict[str, Any]) -> dict[str, Any] | None:
    """Given a {timestamp: entry} dict, return the entry with the latest timestamp."""
    if not mapping:
        return None
    try:
        latest_ts = max(mapping.keys())
        return mapping[latest_ts] if isinstance(mapping[latest_ts], dict) else None
    except Exception:
        return None


def _circl_ipasn(ip: str) -> str | None:
    """Return the current ASN for ``ip`` via CIRCL IP ASN History, or None."""
    url = CIRCL_IPASN_URL + "?" + urllib.parse.urlencode({"ip": ip})
    data = _http_json(url)
    if not data:
        return None
    resp = data.get("response") or {}
    entry = _most_recent_value(resp) if isinstance(resp, dict) else None
    if not entry:
        return None
    asn = entry.get("asn")
    return str(asn) if asn else None


def _circl_asn_meta(asn: str) -> dict[str, Any] | None:
    """Return ``{asn_org, country}`` for an ASN via CIRCL BGP Ranking, or None."""
    try:
        asn_int = int(str(asn).lstrip("AS"))
    except (TypeError, ValueError):
        return None
    data = _http_json(CIRCL_BGPRANKING_ASN_URL, method="POST", body={"asn": asn_int})
    if not data:
        return None
    resp = data.get("response") or {}
    desc = resp.get("asn_description") or resp.get("asn_descriptions")
    if not desc:
        return None
    # Typical shape: "GOOGLE, US" — split on last comma.
    org = desc
    country = None
    if "," in desc:
        left, right = desc.rsplit(",", 1)
        right = right.strip().upper()
        if len(right) == 2 and right.isalpha():
            org = left.strip()
            country = right
    return {"asn_org": org, "country": country}


def enrich(ip: str, force: bool = False) -> dict[str, Any]:
    """Return enrichment for ``ip`` (cached 7 days). ``force`` bypasses the cache."""
    r = _redis()
    key = _cache_key(ip)
    if not force:
        raw: bytes | None = r.get(key)  # type: ignore[assignment]
        if raw:
            try:
                cached = json.loads(raw)
                # Ignore records produced by a previous schema version.
                if isinstance(cached, dict) and cached.get("_schema") == CACHE_SCHEMA:
                    return cached
            except Exception:
                pass

    record: dict[str, Any] = {
        "_schema": CACHE_SCHEMA,
        "ip": ip,
        "asn": None,
        "asn_org": None,
        "country": None,
        "ptr": None,
        "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    asn = _circl_ipasn(ip)
    if asn:
        record["asn"] = asn
        meta = _circl_asn_meta(asn)
        if meta:
            record["asn_org"] = meta.get("asn_org")
            record["country"] = meta.get("country")
    record["ptr"] = _reverse_dns(ip)

    ttl = _cache_ttl_seconds()
    if ttl is None:
        r.set(key, json.dumps(record))
    else:
        r.set(key, json.dumps(record), ex=ttl)
    return record


def bulk_enrich(ips: list[str], force: bool = False) -> dict[str, dict[str, Any]]:
    """Enrich a list of IPs, returning a dict keyed by IP. Deduplicates input."""
    out: dict[str, dict[str, Any]] = {}
    for ip in {i.strip() for i in ips if i and i != "?"}:
        try:
            out[ip] = enrich(ip, force=force)
        except Exception as e:
            logger.debug("enrich failed for %s: %s", ip, e)
            out[ip] = {"ip": ip, "error": str(e)}
    return out


def collect_torrent_health_ips() -> set[str]:
    """Walk every stored scan in DB_TORRENT_HEALTH and return the set of peer IPs."""
    r = _redis()
    ips: set[str] = set()
    for raw_key in r.scan_iter(match="torrent_health:scan:*"):
        try:
            raw: bytes | None = r.get(raw_key)  # type: ignore[assignment]
            if not raw:
                continue
            payload = json.loads(raw)
        except Exception:
            continue
        for p in payload.get("peers") or []:
            ip = (p.get("ip") or "").strip()
            if ip and ip != "?":
                ips.add(ip)
    return ips


def is_cached(ip: str) -> bool:
    """Cheap cache-presence check (no deserialisation)."""
    return bool(_redis().exists(_cache_key(ip)))
