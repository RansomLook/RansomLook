"""BitTorrent swarm health tracking.

Reads magnets from DB_POSTS, queries each infohash for peers via libtorrent
(DHT + optional trackers listed in the magnet), stores swarm metrics and a
sample of connected peers into DB_TORRENT_HEALTH.

Storage layout
--------------

``torrent_health:meta:<infohash>`` — HASH, never expires
    name, size_bytes (str/int), magnets (JSON list), groups (JSON list),
    first_seen (ISO), last_seen_alive (ISO), last_scan (ISO),
    last_seeders (int), last_leechers (int), last_peers_count (int),
    sparkline (JSON list of ``{ts, peers_count}`` last 30 days).

``torrent_health:scans:<infohash>`` — ZSET, score=unix epoch, member=ts ISO
    Ordered index of scans — used for history browsing and pruning.

``torrent_health:scan:<infohash>:<ts>`` — STRING (JSON), TTL 30 days
    Full scan payload: ``{ts, seeders, leechers, peers_count, peers:[...]}``
    where each peer is ``{ip, port, progress, client, flags, source}``.

Purge policy
------------

* Individual scan entries carry a 30-day TTL → auto-expire.
* Meta entries with ``last_seen_alive`` older than 90 days and no recent
  scan activity are removed via :func:`purge_dead` (called at end of every run).
"""

from __future__ import annotations

import json
import logging
import shutil
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

import libtorrent as lt  # type: ignore[import-untyped, import-not-found, unused-ignore]
import valkey

from .default import DB_POSTS, DB_TORRENT_HEALTH, get_socket_path
from .default.config import get_config

logger = logging.getLogger(__name__)

# ─── Config-driven defaults ────────────────────────────────────────────
# All of these can be overridden in config/generic.json under "torrent_health".
# TTL-style fields accept 0 to mean "unlimited" (never expire).

_DEFAULTS = {
    "scan_retention_days": 30,
    "dead_threshold_days": 90,
    "ip_cache_ttl_days": 7,  # consumed by ipenrich.py
    "scan_duration_seconds": 45,
    "batch_size": 10,
    "alive_interval_hours": 6,
    "dead_interval_hours": 24,
    "frozen_interval_days": 7,
}


def _cfg(key: str) -> int:
    """Read an int from config/generic.json ``torrent_health`` section, else default."""
    try:
        section = get_config("generic", "torrent_health", quiet=True) or {}
    except Exception:
        section = {}
    try:
        return int(section.get(key, _DEFAULTS[key]))
    except (TypeError, ValueError):
        return int(_DEFAULTS[key])


def _ttl_or_none(days: int) -> int | None:
    """Convert a days value to seconds. 0 (or negative) means 'no expiration'."""
    if days <= 0:
        return None
    return days * 86400


def _ignored_ips() -> set[str]:
    """Return the user-configured IP blocklist from generic.json.

    Lists under ``torrent_health.ignored_ips`` in the config: exact IP match,
    one per entry. Applied before storage + indexing, so the listed IPs are
    totally invisible in /admin/torrent-health (peer samples, pivot views,
    exports, API). Useful to hide your own scanner, known researchers, etc.
    """
    try:
        section = get_config("generic", "torrent_health", quiet=True) or {}
    except Exception:
        return set()
    lst = section.get("ignored_ips") or []
    if not isinstance(lst, list):
        return set()
    return {str(ip).strip() for ip in lst if ip and str(ip).strip()}


SPARKLINE_MAX = 180  # 30 days × ~6 scans/day — capped regardless of retention
DEFAULT_SCAN_DURATION = _cfg("scan_duration_seconds")
DEFAULT_BATCH_SIZE = _cfg("batch_size")
DEFAULT_ALIVE_INTERVAL = _cfg("alive_interval_hours") * 3600
DEFAULT_DEAD_INTERVAL = _cfg("dead_interval_hours") * 3600
DEFAULT_FROZEN_INTERVAL = _cfg("frozen_interval_days") * 86400


@dataclass
class Peer:
    ip: str
    port: int
    progress: float       # 0-100
    client: str
    flags: str
    source: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "ip": self.ip,
            "port": self.port,
            "progress": round(self.progress, 1),
            "client": self.client,
            "flags": self.flags,
            "source": self.source,
        }


@dataclass
class ScanResult:
    infohash: str
    ts: datetime
    name: str | None
    size_bytes: int | None
    seeders: int
    leechers: int
    peers: list[Peer] = field(default_factory=list)
    # Static torrent metadata — only filled when libtorrent has the info dict
    # (either loaded from a .torrent or fetched from DHT during the scan).
    metadata: dict[str, Any] | None = None

    @property
    def peers_count(self) -> int:
        return len(self.peers)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ts": self.ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "seeders": self.seeders,
            "leechers": self.leechers,
            "peers_count": self.peers_count,
            "peers": [p.to_dict() for p in self.peers],
        }


def _extract_torrent_metadata(ti: Any) -> dict[str, Any]:
    """Pull static metadata from a libtorrent ``torrent_info`` / ``torrent_file``.

    Returns the subset that is interesting for intel: trackers, file list,
    client that produced the .torrent, creation timestamp, user comment,
    private flag, piece layout. All fields are defensive — different
    libtorrent versions expose them differently.
    """
    def _s(fn: Any) -> str:
        try:
            v = fn()
        except Exception:
            return ""
        if v is None:
            return ""
        if isinstance(v, bytes):
            try:
                return v.decode("utf-8", "replace")
            except Exception:
                return v.decode("latin-1", "replace")
        return str(v)

    def _i(fn: Any) -> int:
        try:
            return int(fn() or 0)
        except Exception:
            return 0

    trackers: list[str] = []
    try:
        for t in (ti.trackers() or []):
            url = getattr(t, "url", None) or (t.get("url") if isinstance(t, dict) else None)
            if url:
                trackers.append(str(url))
    except Exception:
        pass

    # BEP-19 webseeds (url-list / httpseeds). Huge intel value for ransomware
    # leaks: each entry is a direct HTTP URL to the file served by the
    # operator's own mirror infrastructure — often still alive when the BT
    # swarm is empty.
    webseeds: list[str] = []
    try:
        for w in (ti.web_seeds() or []):
            url = getattr(w, "url", None) or (w.get("url") if isinstance(w, dict) else None)
            if url:
                webseeds.append(str(url))
    except Exception:
        pass

    files: list[dict[str, Any]] = []
    try:
        fs = ti.files()
        n = ti.num_files()
        for i in range(n):
            try:
                path = fs.file_path(i)
                size = int(fs.file_size(i))
                if isinstance(path, bytes):
                    path = path.decode("utf-8", "replace")
                files.append({"path": path, "size": size})
            except Exception:
                continue
    except Exception:
        pass

    return {
        "trackers": trackers,
        "webseeds": webseeds,
        "files": files,
        "num_files": len(files),
        "created_by": _s(getattr(ti, "creator", lambda: "")),
        "creation_date": _i(getattr(ti, "creation_date", lambda: 0)),
        "comment": _s(getattr(ti, "comment", lambda: "")),
        "private": bool(getattr(ti, "priv", lambda: False)()),
        "piece_length": _i(getattr(ti, "piece_length", lambda: 0)),
        "num_pieces": _i(getattr(ti, "num_pieces", lambda: 0)),
    }


# ─── libtorrent session ─────────────────────────────────────────────────


def build_session(listen_port: int = 6881) -> lt.session:
    """Create a DHT-enabled libtorrent session suitable for passive swarm scan.

    We disable UPnP/NAT-PMP and LSD so the scanner does not advertise itself
    on the local network or to UPnP-enabled routers. Trackers coming from
    the magnet are honoured (we need some way to find peers if DHT fails).
    """
    settings: dict[str, Any] = {
        "enable_dht": True,
        "enable_lsd": False,
        "enable_upnp": False,
        "enable_natpmp": False,
        "listen_interfaces": f"0.0.0.0:{listen_port}",
        "alert_mask": lt.alert.category_t.all_categories,
        "user_agent": "BitTorrent/7.10.5",
        "announce_to_all_tiers": False,
        "announce_to_all_trackers": False,
    }
    sess = lt.session(settings)
    sess.start_dht()
    return sess


def _flags_to_str(flags: int) -> str:
    tokens = []
    peer_info = lt.peer_info
    for name in (
        "interesting",
        "choked",
        "remote_interested",
        "remote_choked",
        "seed",
        "utp_socket",
        "encrypted",
        "dht",
        "connecting",
    ):
        try:
            val = getattr(peer_info, name)
            if flags & int(val):
                tokens.append(name)
        except Exception:
            continue
    return ",".join(tokens) or "-"


def _source_to_str(source: int) -> str:
    tokens = []
    peer_info = lt.peer_info
    for name in ("tracker", "dht", "pex", "lsd", "resume_data", "incoming"):
        try:
            val = getattr(peer_info, f"from_{name}", None)
            if val is not None and source & int(val):
                tokens.append(name)
        except Exception:
            continue
    return ",".join(tokens) or "-"


def _self_ips(sess: lt.session) -> set[str]:
    """Best-effort collection of every IP that should NOT count as an
    external peer: local interface addresses + the public IP libtorrent
    learned from DHT replies."""
    import socket as _sk
    ips: set[str] = {"127.0.0.1", "::1"}
    try:
        host = _sk.gethostname()
        for entry in _sk.getaddrinfo(host, None):
            ips.add(str(entry[4][0]))
    except Exception:
        pass
    try:
        for ext in (sess.external_address(),):
            if ext and isinstance(ext, (tuple, list)) and ext[0]:
                ips.add(str(ext[0]))
            elif ext:
                ips.add(str(ext))
    except Exception:
        pass
    # Drop loopback/empty placeholders we may have collected
    ips.discard("")
    ips.discard("0.0.0.0")
    # Merge in the user-configured blocklist so ignored IPs never show up in
    # peer samples, indexes, or exports.
    ips |= _ignored_ips()
    return ips


def _snapshot(torr: lt.torrent_handle, infohash: str, self_ips: set[str] | None = None) -> ScanResult:
    status = torr.status()
    tf = None
    try:
        tf = torr.torrent_file()
    except Exception:
        tf = None

    def _decode(v: Any) -> str:
        if isinstance(v, bytes):
            try:
                return v.decode("utf-8", "replace")
            except Exception:
                return v.decode("latin-1", "replace")
        return str(v) if v is not None else ""

    raw_peers = list(torr.get_peer_info())
    peers: list[Peer] = []
    seed_flag = int(getattr(lt.peer_info, "seed", 0))
    self_ips_set = self_ips or set()

    def _is_seeder(pi: Any) -> bool:
        # libtorrent sets ``peer_info.seed`` only once it has received a
        # complete bitfield from the peer. Progress is updated as soon as any
        # bitfield or HAVE message arrives, so a peer at ~100% is a seeder in
        # practice even if the flag has not flipped yet.
        try:
            if float(getattr(pi, "progress", 0.0)) >= 0.999:
                return True
        except Exception:
            pass
        return bool(seed_flag) and bool(int(pi.flags) & seed_flag)

    for p in raw_peers:
        try:
            ip, port = p.ip
        except Exception:
            ip, port = ("?", 0)
        ip_str = _decode(ip)
        if ip_str in self_ips_set:
            # Skip our own scanner — it occasionally appears in DHT replies.
            continue
        peers.append(
            Peer(
                ip=ip_str,
                port=int(port),
                progress=float(p.progress) * 100,
                client=_decode(getattr(p, "client", "")),
                flags=_flags_to_str(int(p.flags)),
                source=_source_to_str(int(p.source)),
            )
        )

    # Prefer tracker-reported totals when they indicate activity (the tracker
    # sees the global swarm, not just what we are connected to). Fall back to
    # the local peer sample when the tracker has no data or reports 0 — that
    # otherwise caused "2 peers but 0/0 seed/leech" when the tracker was dead.
    num_complete = int(getattr(status, "num_complete", -1))
    num_incomplete = int(getattr(status, "num_incomplete", -1))

    local_seeders = sum(1 for p in raw_peers if _is_seeder(p))
    local_leechers = max(0, len(raw_peers) - local_seeders)

    if logger.isEnabledFor(logging.DEBUG):
        for i, pi in enumerate(raw_peers[:5]):
            try:
                logger.debug(
                    "%s peer[%d] progress=%.3f flags=0x%x seed_flag_hit=%s",
                    infohash, i, float(pi.progress), int(pi.flags),
                    bool(seed_flag) and bool(int(pi.flags) & seed_flag),
                )
            except Exception:
                continue

    seeders = num_complete if num_complete > 0 else local_seeders
    leechers = num_incomplete if num_incomplete > 0 else local_leechers

    logger.debug(
        "%s raw_peers=%d tracker_num_complete=%d tracker_num_incomplete=%d "
        "local_seeders=%d local_leechers=%d → seeders=%d leechers=%d",
        infohash, len(raw_peers), num_complete, num_incomplete,
        local_seeders, local_leechers, seeders, leechers,
    )

    metadata: dict[str, Any] | None = None
    if tf is not None:
        try:
            metadata = _extract_torrent_metadata(tf)
        except Exception:
            metadata = None

    return ScanResult(
        infohash=infohash,
        ts=datetime.now(timezone.utc),
        name=tf.name() if tf else None,
        size_bytes=tf.total_size() if tf else None,
        seeders=seeders,
        leechers=leechers,
        peers=peers,
        metadata=metadata,
    )


def scan_magnet(sess: lt.session, magnet: str, duration: int = DEFAULT_SCAN_DURATION) -> ScanResult:
    """Scan a single magnet. Kept as a convenience wrapper around :func:`scan_batch`."""
    results = scan_batch(sess, [magnet], duration=duration)
    if not results:
        raise RuntimeError("no result for magnet (failed to parse?)")
    return results[0]


def scan_batch(sess: lt.session, magnets: list[str], duration: int = DEFAULT_SCAN_DURATION) -> list[ScanResult]:
    """Scan several magnets concurrently in the same libtorrent session.

    All magnets are added in one shot, resumed together, observed for
    ``duration`` seconds, then snapshotted and removed. A single session
    sharing DHT state is materially more efficient than N sequential sessions.

    Bandwidth: no per-torrent rate limit is applied. Earlier revisions pinned
    both limits at 1 byte/s to avoid downloading any data, but this stalled the
    BT handshake (68 bytes + bitfield) so peers never progressed past
    ``handshake`` state and every swarm reported ``0 seed``. Any piece data that
    flows during the short scan window is acceptable because the tempdir is
    wiped at the end.

    Cleanup: each batch uses a dedicated tempdir. Removed torrents are wiped
    via ``delete_files`` and the tempdir is rmtree'd at the end so the leak
    filenames libtorrent allocates never linger on disk.
    """
    tempdir = tempfile.mkdtemp(prefix="rl-torrent-")
    handles: list[tuple[str, lt.torrent_handle]] = []
    results: list[ScanResult] = []
    try:
        for magnet in magnets:
            try:
                atp = lt.parse_magnet_uri(magnet)
            except Exception as e:
                logger.warning("skip unparseable magnet %s: %s", magnet[:80], e)
                continue
            atp.save_path = tempdir
            # Paused at add time so we can fix per-torrent rate limits before any
            # bytes are exchanged. ``upload_mode`` is intentionally NOT set: it
            # discourages libtorrent from initiating outgoing connections, which
            # then breaks our peer enumeration.
            atp.flags = lt.torrent_flags.paused
            torr = sess.add_torrent(atp)
            infohash_obj = torr.info_hashes()
            infohash = str(getattr(infohash_obj, "get_best", lambda: infohash_obj)())
            handles.append((infohash, torr))
            try:
                trk = [t.get("url") if isinstance(t, dict) else getattr(t, "url", str(t))
                       for t in (atp.trackers or [])]
                logger.debug("%s trackers from magnet: %s", infohash, trk or "(none — DHT-only)")
            except Exception:
                pass

        for _, torr in handles:
            torr.resume()

        # Drain alerts during the wait window — surfaces DHT and tracker errors
        # that are otherwise silent. Only shown at DEBUG level.
        deadline = time.time() + duration
        while time.time() < deadline:
            time.sleep(1)
            if logger.isEnabledFor(logging.DEBUG):
                try:
                    alerts = sess.pop_alerts()
                    for a in alerts:
                        msg = str(a) if not callable(getattr(a, "message", None)) else a.message()
                        cat = a.__class__.__name__
                        if any(k in cat.lower() for k in ("error", "warning", "tracker", "dht")):
                            logger.debug("ALERT %s: %s", cat, msg[:200])
                except Exception:
                    pass

        # Resolve the delete-files flag across libtorrent versions.
        delete_flag = (
            getattr(lt.session, "delete_files", None)
            or getattr(getattr(lt, "options_t", None), "delete_files", None)
            or 1
        )
        self_ips = _self_ips(sess)
        if self_ips:
            logger.debug("filtering out scanner IPs from peers: %s", sorted(self_ips))
        for infohash, torr in handles:
            try:
                results.append(_snapshot(torr, infohash, self_ips=self_ips))
            except Exception as e:
                logger.warning("snapshot failed for %s: %s", infohash, e)
            finally:
                try:
                    sess.remove_torrent(torr, delete_flag)
                except TypeError:
                    # Older binding: positional flag rejected, fall back without
                    # delete (we still rmtree the tempdir below).
                    try:
                        sess.remove_torrent(torr)
                    except Exception:
                        pass
                except Exception:
                    pass
    finally:
        # Guaranteed cleanup — runs even on KeyboardInterrupt, libtorrent
        # crashes, or any exception raised mid-scan. Otherwise the caller
        # accumulates ``rl-torrent-*`` dirs over time.
        shutil.rmtree(tempdir, ignore_errors=True)
    return results


def _purge_stale_tempdirs(max_age_seconds: int = 3600) -> int:
    """Remove leftover ``rl-torrent-*`` directories older than ``max_age_seconds``.

    These come from previous runs that were killed (SIGKILL, OOM, crash) before
    their ``finally`` block could execute. Called at the start of every
    ``run_once`` pass.
    """
    import os
    removed = 0
    base = tempfile.gettempdir()
    now = time.time()
    try:
        entries = os.listdir(base)
    except Exception:
        return 0
    for name in entries:
        if not name.startswith("rl-torrent-"):
            continue
        path = os.path.join(base, name)
        try:
            age = now - os.path.getmtime(path)
        except Exception:
            continue
        if age < max_age_seconds:
            continue
        shutil.rmtree(path, ignore_errors=True)
        removed += 1
    if removed:
        logger.info("purged %d stale tempdir(s) from previous runs", removed)
    return removed


# ─── Storage helpers ────────────────────────────────────────────────────


def _redis() -> valkey.Valkey:
    return valkey.Valkey(unix_socket_path=get_socket_path("cache"), db=DB_TORRENT_HEALTH)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(d: datetime) -> str:
    return d.strftime("%Y-%m-%dT%H:%M:%SZ")


def store_scan(result: ScanResult, magnets: list[str], groups: list[str]) -> None:
    r = _redis()
    ih = result.infohash
    meta_key = f"torrent_health:meta:{ih}"
    scans_key = f"torrent_health:scans:{ih}"
    scan_key = f"torrent_health:scan:{ih}:{_iso(result.ts)}"

    # Persist the full scan payload with a configurable retention TTL.
    # ``scan_retention_days = 0`` means "keep forever" (no expiration).
    scan_ttl = _ttl_or_none(_cfg("scan_retention_days"))
    if scan_ttl is None:
        r.set(scan_key, json.dumps(result.to_dict()))
    else:
        r.set(scan_key, json.dumps(result.to_dict()), ex=scan_ttl)
    r.zadd(scans_key, {_iso(result.ts): result.ts.timestamp()})

    # Prune old zset entries matching the retention window. Skip when unlimited.
    if scan_ttl is not None:
        cutoff = (result.ts - timedelta(seconds=scan_ttl)).timestamp()
        r.zremrangebyscore(scans_key, "-inf", cutoff)

    # Update meta. valkey-py's hgetall is typed as Awaitable|dict for async/sync
    # parity; this module is sync only, so narrow the type for mypy.
    existing: dict[bytes, bytes] = r.hgetall(meta_key) or {}  # type: ignore[assignment]
    existing_first_seen = existing.get(b"first_seen", b"").decode() if existing else ""
    sparkline_raw = existing.get(b"sparkline", b"[]").decode() if existing else "[]"
    try:
        sparkline = json.loads(sparkline_raw)
    except Exception:
        sparkline = []
    sparkline.append({"ts": _iso(result.ts), "peers_count": result.peers_count})
    sparkline = sparkline[-SPARKLINE_MAX:]

    mapping = {
        "name": result.name or existing.get(b"name", b"").decode(),
        "size_bytes": str(result.size_bytes if result.size_bytes is not None else existing.get(b"size_bytes", b"0").decode()),
        "magnets": json.dumps(sorted(set(magnets + json.loads(existing.get(b"magnets", b"[]").decode() or "[]")))),
        "groups": json.dumps(sorted(set(groups + json.loads(existing.get(b"groups", b"[]").decode() or "[]")))),
        "first_seen": existing_first_seen or _iso(result.ts),
        "last_scan": _iso(result.ts),
        "last_seeders": str(result.seeders),
        "last_leechers": str(result.leechers),
        "last_peers_count": str(result.peers_count),
        "sparkline": json.dumps(sparkline),
    }
    if result.peers_count > 0:
        mapping["last_seen_alive"] = _iso(result.ts)

    # Persist static torrent metadata on first availability. We keep the
    # richer value: once the full file list / trackers / created_by are
    # known, later scans (which may only have partial metadata from DHT)
    # must not overwrite them with emptier versions.
    if result.metadata:
        md = result.metadata
        existing_files = json.loads(existing.get(b"files", b"[]").decode() or "[]") if existing else []
        if md.get("files") and len(md["files"]) >= len(existing_files):
            mapping["files"] = json.dumps(md["files"])
            mapping["num_files"] = str(md.get("num_files") or len(md["files"]))
        existing_trackers = json.loads(existing.get(b"trackers", b"[]").decode() or "[]") if existing else []
        if md.get("trackers"):
            merged_trackers = sorted(set(existing_trackers + md["trackers"]))
            mapping["trackers"] = json.dumps(merged_trackers)
        existing_webseeds = json.loads(existing.get(b"webseeds", b"[]").decode() or "[]") if existing else []
        if md.get("webseeds"):
            merged_webseeds = sorted(set(existing_webseeds + md["webseeds"]))
            mapping["webseeds"] = json.dumps(merged_webseeds)
        for key in ("created_by", "creation_date", "comment", "piece_length", "num_pieces"):
            val = md.get(key)
            if val in (None, "", 0):
                continue
            existing_val = existing.get(key.encode(), b"").decode() if existing else ""
            if not existing_val:
                mapping[key] = str(val)
        if md.get("private") and not existing.get(b"private"):
            mapping["private"] = "1"

    r.hset(meta_key, mapping=mapping)

    # ── Pivot indexes ────────────────────────────────────────────────────
    # For each peer observed in this scan, record the association with this
    # infohash + increment the leaderboards. A peer is counted as seeder if
    # libtorrent flagged it OR if its progress ≥ 99.9% (same rule as elsewhere).
    for peer in result.peers:
        ip = (peer.ip or "").strip()
        if not ip or ip == "?":
            continue
        r.sadd(f"torrent_health:ip_to_ih:{ip}", ih)
        r.zincrby("torrent_health:top:ip", 1, ip)
        is_seeder = "seed" in (peer.flags or "") or peer.progress >= 99.9
        if is_seeder:
            r.sadd(f"torrent_health:ip_seeds:{ip}", ih)
            r.zincrby("torrent_health:top:ip_seed", 1, ip)
        # Cross-group correlation: track every ransomware group this IP has
        # been observed in. An IP showing up across 2+ groups is a strong
        # signal (shared seedbox, common actor, researcher downloading leaks…).
        for grp in groups:
            if not grp:
                continue
            r.sadd(f"torrent_health:ip_to_groups:{ip}", grp)
        group_count: int = r.scard(f"torrent_health:ip_to_groups:{ip}") or 0  # type: ignore[assignment]
        if group_count >= 2:
            r.zadd("torrent_health:top:ip_cross_group", {ip: group_count})


def list_infohashes() -> list[str]:
    """Return the set of infohashes known in the meta store."""
    r = _redis()
    out = []
    for k in r.scan_iter(match="torrent_health:meta:*"):
        name = k.decode()
        out.append(name.split(":", 2)[2])
    return sorted(out)


def get_meta(infohash: str) -> dict[str, Any] | None:
    r = _redis()
    raw: dict[bytes, bytes] = r.hgetall(f"torrent_health:meta:{infohash}")  # type: ignore[assignment]
    if not raw:
        return None
    out: dict[str, Any] = {}
    for k, v in raw.items():
        key = k.decode()
        val = v.decode()
        if key in ("magnets", "groups", "sparkline", "files", "trackers",
                   "webseeds", "tracker_history"):
            try:
                out[key] = json.loads(val)
            except Exception:
                out[key] = []
        elif key in ("size_bytes", "last_seeders", "last_leechers",
                     "last_peers_count", "num_files", "num_pieces",
                     "piece_length", "creation_date",
                     "tracker_seeders", "tracker_leechers", "tracker_downloaded"):
            try:
                out[key] = int(val)
            except Exception:
                out[key] = 0
        elif key == "private":
            out[key] = val == "1"
        else:
            out[key] = val
    out["infohash"] = infohash
    return out


def get_history(infohash: str, limit: int | None = None) -> list[dict[str, Any]]:
    """Return scans ordered from newest to oldest. ``limit`` caps result size."""
    r = _redis()
    scans_key = f"torrent_health:scans:{infohash}"
    members: list[bytes] = r.zrevrange(scans_key, 0, (limit or -1) - (0 if limit is None else 1))  # type: ignore[assignment]
    out = []
    for m in members:
        ts = m.decode()
        raw: bytes | None = r.get(f"torrent_health:scan:{infohash}:{ts}")  # type: ignore[assignment]
        if raw:
            try:
                out.append(json.loads(raw))
            except Exception:
                continue
    return out


def get_scan(infohash: str, ts_iso: str) -> dict[str, Any] | None:
    r = _redis()
    raw: bytes | None = r.get(f"torrent_health:scan:{infohash}:{ts_iso}")  # type: ignore[assignment]
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None


# ─── Pivot queries (IP / ASN) ──────────────────────────────────────────────


def get_top_ips(limit: int = 50, seed_only: bool = False) -> list[dict[str, Any]]:
    """Return the top IPs ranked by scan appearances.

    ``seed_only=True`` ranks by appearances where the IP was observed
    seeding, which is usually the more operationally interesting signal.
    """
    r = _redis()
    zkey = "torrent_health:top:ip_seed" if seed_only else "torrent_health:top:ip"
    rows: list[tuple[bytes, float]] = r.zrevrange(zkey, 0, max(0, limit - 1), withscores=True)  # type: ignore[assignment]
    out = []
    for ip_b, score in rows:
        ip = ip_b.decode() if isinstance(ip_b, bytes) else str(ip_b)
        t_all: int = r.scard(f"torrent_health:ip_to_ih:{ip}") or 0  # type: ignore[assignment]
        t_seed: int = r.scard(f"torrent_health:ip_seeds:{ip}") or 0  # type: ignore[assignment]
        out.append({
            "ip": ip,
            "count": int(score),
            "torrents": t_all,
            "seed_torrents": t_seed,
        })
    return out


def get_top_asn(limit: int = 50, seed_only: bool = False) -> list[dict[str, Any]]:
    """Return the top ASNs ranked by number of distinct IPs (or seeder IPs)."""
    r = _redis()
    zkey = "torrent_health:top:asn_seed" if seed_only else "torrent_health:top:asn"
    rows: list[tuple[bytes, float]] = r.zrevrange(zkey, 0, max(0, limit - 1), withscores=True)  # type: ignore[assignment]
    out = []
    for asn_b, score in rows:
        asn = asn_b.decode() if isinstance(asn_b, bytes) else str(asn_b)
        t_all: int = r.scard(f"torrent_health:asn_to_ih:{asn}") or 0  # type: ignore[assignment]
        t_seed: int = r.scard(f"torrent_health:asn_seed_ih:{asn}") or 0  # type: ignore[assignment]
        out.append({
            "asn": asn,
            "ips": int(score),
            "torrents": t_all,
            "seed_torrents": t_seed,
        })
    return out


def get_ip_detail(ip: str) -> dict[str, Any]:
    """Return everything we know about an IP: torrent associations + enrichment."""
    r = _redis()
    ih_all_b: set[bytes] = r.smembers(f"torrent_health:ip_to_ih:{ip}")  # type: ignore[assignment]
    ih_seed_b: set[bytes] = r.smembers(f"torrent_health:ip_seeds:{ip}")  # type: ignore[assignment]
    ih_all = sorted(b.decode() if isinstance(b, bytes) else b for b in ih_all_b)
    ih_seed = {b.decode() if isinstance(b, bytes) else b for b in ih_seed_b}

    # Resolve infohash → human-friendly name + groups so the UI can link nicely.
    torrents = []
    for ih in ih_all:
        meta = get_meta(ih) or {}
        torrents.append({
            "infohash": ih,
            "name": meta.get("name") or "",
            "groups": meta.get("groups") or [],
            "is_seeder": ih in ih_seed,
            "last_scan": meta.get("last_scan"),
            "last_peers_count": meta.get("last_peers_count") or 0,
        })
    # Newest-scan first, then by name
    torrents.sort(key=lambda t: (t["last_scan"] or "", t["name"] or ""), reverse=True)

    # Enrichment: fetch lazily if not cached. Safe to import here to avoid
    # cyclic imports (ipenrich reads DB_TORRENT_HEALTH via this module too).
    enrichment: dict[str, Any] = {}
    try:
        from . import ipenrich
        enrichment = ipenrich.enrich(ip) or {}
    except Exception as e:
        logger.debug("enrichment lookup failed for %s: %s", ip, e)

    return {
        "ip": ip,
        "enrichment": enrichment,
        "torrents": torrents,
        "seen_count": int(r.zscore("torrent_health:top:ip", ip) or 0),  # type: ignore[arg-type]
        "seed_count": int(r.zscore("torrent_health:top:ip_seed", ip) or 0),  # type: ignore[arg-type]
    }


def get_top_ips_windowed(limit: int = 50, seed_only: bool = False, days: int = 7) -> list[dict[str, Any]]:
    """Top IPs observed in the last ``days`` days, computed from raw scans.

    No dedicated time-bucketed zsets on purpose: 200 swarms × 6 scans/day
    × 30 days = 36k JSON reads worst case, takes well under a second on a
    local Valkey. Keeps the schema simple.
    """
    r = _redis()
    end = _now()
    start = end - timedelta(days=days)

    counts: dict[str, int] = {}
    torrents_by_ip: dict[str, set[str]] = {}
    seed_torrents_by_ip: dict[str, set[str]] = {}

    for ih in list_infohashes():
        scans_key = f"torrent_health:scans:{ih}"
        members: list[bytes] = r.zrangebyscore(  # type: ignore[assignment]
            scans_key, start.timestamp(), end.timestamp(),
        )
        for ts_b in members:
            ts_iso = ts_b.decode() if isinstance(ts_b, bytes) else str(ts_b)
            raw: bytes | None = r.get(f"torrent_health:scan:{ih}:{ts_iso}")  # type: ignore[assignment]
            if not raw:
                continue
            try:
                scan = json.loads(raw)
            except Exception:
                continue
            for p in scan.get("peers") or []:
                ip = (p.get("ip") or "").strip()
                if not ip or ip == "?":
                    continue
                flags = p.get("flags") or ""
                progress = float(p.get("progress") or 0)
                is_seed = "seed" in flags or progress >= 99.9
                if seed_only and not is_seed:
                    continue
                counts[ip] = counts.get(ip, 0) + 1
                torrents_by_ip.setdefault(ip, set()).add(ih)
                if is_seed:
                    seed_torrents_by_ip.setdefault(ip, set()).add(ih)

    ranked = sorted(counts.items(), key=lambda kv: -kv[1])[:limit]
    return [
        {
            "ip": ip,
            "count": c,
            "torrents": len(torrents_by_ip.get(ip, set())),
            "seed_torrents": len(seed_torrents_by_ip.get(ip, set())),
        }
        for ip, c in ranked
    ]


def get_top_asn_windowed(limit: int = 50, seed_only: bool = False, days: int = 7) -> list[dict[str, Any]]:
    """Top ASNs in the last ``days`` days. ASN is resolved from the enrichment
    cache for each observed IP; IPs without cached enrichment are skipped.
    """
    from . import ipenrich

    ips_rows = get_top_ips_windowed(limit=limit * 10, seed_only=seed_only, days=days)
    by_asn: dict[str, dict[str, Any]] = {}
    for row in ips_rows:
        ip = row["ip"]
        enr = ipenrich.enrich(ip) or {}
        asn = enr.get("asn")
        if not asn:
            continue
        key = str(asn)
        bucket = by_asn.setdefault(key, {"asn": key, "ips": 0, "torrents": 0, "seed_torrents": 0, "_ip_set": set(), "_ih_set": set(), "_ih_seed_set": set()})
        bucket["_ip_set"].add(ip)
        bucket["_ih_set"].add(row["torrents"])  # placeholder; we merge infohash sets below

    # Second pass — we need actual IH sets, not counts. Re-walk to aggregate.
    r = _redis()
    for asn_key, bucket in by_asn.items():
        bucket["_ih_set"] = set()
        bucket["_ih_seed_set"] = set()
    for row in ips_rows:
        ip = row["ip"]
        enr = ipenrich.enrich(ip) or {}
        asn = enr.get("asn")
        if not asn:
            continue
        key = str(asn)
        ih_all_b: set[bytes] = r.smembers(f"torrent_health:ip_to_ih:{ip}")  # type: ignore[assignment]
        ih_seed_b: set[bytes] = r.smembers(f"torrent_health:ip_seeds:{ip}")  # type: ignore[assignment]
        by_asn[key]["_ih_set"].update(b.decode() if isinstance(b, bytes) else b for b in ih_all_b)
        by_asn[key]["_ih_seed_set"].update(b.decode() if isinstance(b, bytes) else b for b in ih_seed_b)

    out = []
    for asn_key, bucket in by_asn.items():
        out.append({
            "asn": asn_key,
            "ips": len(bucket["_ip_set"]),
            "torrents": len(bucket["_ih_set"]),
            "seed_torrents": len(bucket["_ih_seed_set"]),
        })
    out.sort(key=lambda x: -x["ips"])  # type: ignore[operator]
    return out[:limit]


def get_top_cross_group_ips(limit: int = 50) -> list[dict[str, Any]]:
    """IPs seen across multiple ransomware groups, ordered by group count.

    This is the most high-signal pivot view: an IP seeding for both Clop and
    Akira (for example) is either a researcher aggregating leaks, a seedbox
    shared between actors, or somebody with an unusual exfiltration pattern.
    """
    r = _redis()
    rows: list[tuple[bytes, float]] = r.zrevrange(  # type: ignore[assignment]
        "torrent_health:top:ip_cross_group", 0, max(0, limit - 1), withscores=True,
    )
    out = []
    for ip_b, score in rows:
        ip = ip_b.decode() if isinstance(ip_b, bytes) else str(ip_b)
        groups_b: set[bytes] = r.smembers(f"torrent_health:ip_to_groups:{ip}")  # type: ignore[assignment]
        groups = sorted(g.decode() if isinstance(g, bytes) else g for g in groups_b)
        t_all: int = r.scard(f"torrent_health:ip_to_ih:{ip}") or 0  # type: ignore[assignment]
        t_seed: int = r.scard(f"torrent_health:ip_seeds:{ip}") or 0  # type: ignore[assignment]
        out.append({
            "ip": ip,
            "group_count": int(score),
            "groups": groups,
            "torrents": t_all,
            "seed_torrents": t_seed,
        })
    return out


def get_ip_timeline(ip: str, days: int = 30) -> list[dict[str, Any]]:
    """Return daily observation counts for an IP over the last ``days`` days.

    For each torrent the IP has been observed in, walks the scans in the
    window and checks whether the IP was actually present in that specific
    scan's peer list. Precise (not approximated from the top-level index)
    so the sparkline reflects real activity. Bounded I/O: an IP tied to N
    torrents × M scans = N·M JSON reads.
    """
    r = _redis()
    ih_all_b: set[bytes] = r.smembers(f"torrent_health:ip_to_ih:{ip}")  # type: ignore[assignment]
    ih_all = [b.decode() if isinstance(b, bytes) else b for b in ih_all_b]

    end = _now()
    start = end - timedelta(days=days)
    by_day: dict[str, dict[str, int]] = {}
    for i in range(days + 1):
        d = (start + timedelta(days=i)).strftime("%Y-%m-%d")
        by_day[d] = {"seen": 0, "seed": 0}

    for ih in ih_all:
        scans_key = f"torrent_health:scans:{ih}"
        members: list[bytes] = r.zrangebyscore(  # type: ignore[assignment]
            scans_key, start.timestamp(), end.timestamp(),
        )
        for ts_b in members:
            ts_iso = ts_b.decode() if isinstance(ts_b, bytes) else str(ts_b)
            day = ts_iso[:10]
            if day not in by_day:
                continue
            raw: bytes | None = r.get(f"torrent_health:scan:{ih}:{ts_iso}")  # type: ignore[assignment]
            if not raw:
                continue
            try:
                scan = json.loads(raw)
            except Exception:
                continue
            for p in scan.get("peers") or []:
                if (p.get("ip") or "").strip() != ip:
                    continue
                by_day[day]["seen"] += 1
                flags = p.get("flags") or ""
                progress = float(p.get("progress") or 0)
                if "seed" in flags or progress >= 99.9:
                    by_day[day]["seed"] += 1
                break  # Only count once per scan even if the IP recurs.

    return [{"day": d, **counts} for d, counts in by_day.items()]


def get_asn_detail(asn: str) -> dict[str, Any]:
    """Return IPs and torrents associated with an ASN."""
    r = _redis()
    asn_key = str(asn).lstrip("AS").strip()
    ips_b: set[bytes] = r.smembers(f"torrent_health:asn_to_ip:{asn_key}")  # type: ignore[assignment]
    ih_all_b: set[bytes] = r.smembers(f"torrent_health:asn_to_ih:{asn_key}")  # type: ignore[assignment]
    ih_seed_b: set[bytes] = r.smembers(f"torrent_health:asn_seed_ih:{asn_key}")  # type: ignore[assignment]
    ips = sorted(b.decode() if isinstance(b, bytes) else b for b in ips_b)
    ih_all = sorted(b.decode() if isinstance(b, bytes) else b for b in ih_all_b)
    ih_seed = {b.decode() if isinstance(b, bytes) else b for b in ih_seed_b}

    torrents = []
    for ih in ih_all:
        meta = get_meta(ih) or {}
        torrents.append({
            "infohash": ih,
            "name": meta.get("name") or "",
            "groups": meta.get("groups") or [],
            "has_seeder": ih in ih_seed,
            "last_scan": meta.get("last_scan"),
        })
    torrents.sort(key=lambda t: (t["last_scan"] or "", t["name"] or ""), reverse=True)

    # Resolve ASN → org/country from one of its IPs (cheapest path: use the
    # cached enrichment of any of the IPs; they all share the same ASN).
    asn_org = ""
    country = ""
    for ip in ips:
        try:
            from . import ipenrich
            enr = ipenrich.enrich(ip) or {}
            if enr.get("asn_org"):
                asn_org = enr["asn_org"]
                country = enr.get("country") or ""
                break
        except Exception:
            continue

    return {
        "asn": asn_key,
        "asn_org": asn_org,
        "country": country,
        "ips": ips,
        "torrents": torrents,
    }


def purge_dead(now: datetime | None = None) -> int:
    """Remove meta + zset for infohashes whose last_seen_alive is older than
    ``dead_threshold_days``. A value of 0 disables the purge entirely."""
    dead_ttl = _ttl_or_none(_cfg("dead_threshold_days"))
    if dead_ttl is None:
        return 0
    now = now or _now()
    cutoff = now - timedelta(seconds=dead_ttl)
    removed = 0
    for ih in list_infohashes():
        meta = get_meta(ih) or {}
        last = meta.get("last_seen_alive") or meta.get("last_scan") or meta.get("first_seen")
        if not last:
            continue
        try:
            last_dt = datetime.strptime(last, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        except Exception:
            continue
        if last_dt < cutoff:
            r = _redis()
            r.delete(f"torrent_health:meta:{ih}")
            r.delete(f"torrent_health:scans:{ih}")
            removed += 1
    return removed


# ─── Collecting magnets from posts ─────────────────────────────────────


def collect_magnets() -> dict[str, dict[str, Any]]:
    """Walk DB_POSTS and return ``{infohash: {"magnets": [...], "groups": [...]}}``.

    Skips entries whose magnet cannot be parsed.
    """
    posts_r = valkey.Valkey(unix_socket_path=get_socket_path("cache"), db=DB_POSTS)
    out: dict[str, dict[str, Any]] = {}
    for key in posts_r.scan_iter():
        try:
            group = key.decode()
            raw: bytes | None = posts_r.get(key)  # type: ignore[assignment]
            if not raw:
                continue
            posts = json.loads(raw)
        except Exception:
            continue
        if not isinstance(posts, list):
            continue
        for p in posts:
            mag = p.get("magnet") if isinstance(p, dict) else None
            if not mag:
                continue
            try:
                atp = lt.parse_magnet_uri(mag)
                ih_obj = atp.info_hashes
                infohash = str(getattr(ih_obj, "get_best", lambda: ih_obj)())
            except Exception:
                continue
            entry = out.setdefault(infohash, {"magnets": set(), "groups": set()})
            entry["magnets"].add(mag)
            entry["groups"].add(group)

    # Merge in manually-added "orphan" torrents (not tied to any post) from
    # DB_TORRENT_HEALTH meta. A meta entry qualifies as an orphan when it
    # carries ≥ 1 group. If an infohash is both post-linked AND in meta, we
    # union the two groups lists so a manual tag survives.
    th_r = _redis()
    for meta_key in th_r.scan_iter(match="torrent_health:meta:*"):
        ih = meta_key.decode().split(":", 2)[2]
        meta = get_meta(ih) or {}
        meta_groups = [g for g in (meta.get("groups") or []) if g]
        meta_magnets = [m for m in (meta.get("magnets") or []) if m]
        if not meta_groups or not meta_magnets:
            continue
        entry = out.setdefault(ih, {"magnets": set(), "groups": set()})
        entry["magnets"].update(meta_magnets)
        entry["groups"].update(meta_groups)

    return {
        ih: {
            "magnets": sorted(v["magnets"]),
            "groups": sorted(v["groups"]),
        }
        for ih, v in out.items()
    }


def parse_magnet_or_torrent(source: str) -> dict[str, Any]:
    """Normalise a user-supplied magnet URI or .torrent file path into a dict.

    Returns ``{infohash, magnet, name, size_bytes}``. Raises ``ValueError`` on
    anything we can't parse. Used by the CLI adder and the admin /manage form.
    """
    source = source.strip()
    if source.startswith("magnet:"):
        atp = lt.parse_magnet_uri(source)
        ih_obj = atp.info_hashes
        ih = str(getattr(ih_obj, "get_best", lambda: ih_obj)()).lower()
        if not ih:
            raise ValueError("magnet has no infohash")
        # Name from the dn= parameter if any.
        name = ""
        try:
            name = (atp.name or "") if hasattr(atp, "name") else ""
        except Exception:
            pass
        # Magnets can carry trackers (tr=) and webseeds (ws=). Both are BEP
        # extensions that the libtorrent parser already splits out into the
        # add_torrent_params object — capture them so BEP-48 scrape + the
        # detail page see the full picture even before DHT metadata arrives.
        magnet_trackers: list[str] = []
        try:
            for t in (atp.trackers or []):
                url = t.get("url") if isinstance(t, dict) else getattr(t, "url", str(t))
                if url:
                    magnet_trackers.append(str(url))
        except Exception:
            pass
        magnet_webseeds: list[str] = []
        try:
            # ``url_seeds`` → BEP-19 (http), ``http_seeds`` → BEP-17 (deprecated).
            for attr in ("url_seeds", "http_seeds"):
                for w in (getattr(atp, attr, []) or []):
                    if w:
                        magnet_webseeds.append(str(w))
        except Exception:
            pass
        return {
            "infohash": ih,
            "magnet": source,
            "name": name,
            "size_bytes": 0,
            "metadata": {
                "trackers": magnet_trackers,
                "webseeds": magnet_webseeds,
                "files": [],
                "num_files": 0,
                "created_by": "",
                "creation_date": 0,
                "comment": "",
                "private": False,
                "piece_length": 0,
                "num_pieces": 0,
            },
        }

    # Treat as a .torrent file path.
    try:
        ti = lt.torrent_info(source)
    except Exception as e:
        raise ValueError(f"cannot read .torrent file: {e}") from e
    ih_obj = ti.info_hashes()
    ih = str(getattr(ih_obj, "get_best", lambda: ih_obj)()).lower()
    return {
        "infohash": ih,
        "magnet": lt.make_magnet_uri(ti),
        "name": ti.name() or "",
        "size_bytes": ti.total_size() or 0,
        "metadata": _extract_torrent_metadata(ti),
    }


def add_manual_torrent(group: str, magnet_or_path: str) -> dict[str, Any]:
    """Register a torrent under ``group`` without requiring a post.

    Writes (or merges) a ``torrent_health:meta:<ih>`` entry. Subsequent cron
    runs of :func:`run_once` will pick it up via :func:`collect_magnets`.
    Returns ``{infohash, name, size_bytes, magnet, groups, already_tracked}``.
    """
    info = parse_magnet_or_torrent(magnet_or_path)
    ih = info["infohash"]
    r = _redis()
    meta_key = f"torrent_health:meta:{ih}"

    existing: dict[bytes, bytes] = r.hgetall(meta_key) or {}  # type: ignore[assignment]
    already = bool(existing)

    existing_groups: list[str] = []
    existing_magnets: list[str] = []
    if existing:
        try:
            existing_groups = json.loads(existing.get(b"groups", b"[]").decode() or "[]") or []
        except Exception:
            existing_groups = []
        try:
            existing_magnets = json.loads(existing.get(b"magnets", b"[]").decode() or "[]") or []
        except Exception:
            existing_magnets = []

    merged_groups = sorted(set(existing_groups + [group]))
    merged_magnets = sorted(set(existing_magnets + [info["magnet"]]))

    mapping: dict[str, str] = {
        "name": info["name"] or existing.get(b"name", b"").decode(),
        "size_bytes": str(info["size_bytes"] or int(existing.get(b"size_bytes", b"0") or 0)),
        "magnets": json.dumps(merged_magnets),
        "groups": json.dumps(merged_groups),
    }
    if not existing:
        mapping["first_seen"] = _iso(_now())

    # Persist static metadata from the .torrent when available (magnets give
    # us nothing at this stage; the DHT fetch in scan_batch will fill it in).
    md = info.get("metadata") or {}
    if md:
        existing_files = json.loads(existing.get(b"files", b"[]").decode() or "[]") if existing else []
        if md.get("files") and len(md["files"]) >= len(existing_files):
            mapping["files"] = json.dumps(md["files"])
            mapping["num_files"] = str(md.get("num_files") or len(md["files"]))
        existing_trackers = json.loads(existing.get(b"trackers", b"[]").decode() or "[]") if existing else []
        if md.get("trackers"):
            mapping["trackers"] = json.dumps(sorted(set(existing_trackers + md["trackers"])))
        existing_webseeds = json.loads(existing.get(b"webseeds", b"[]").decode() or "[]") if existing else []
        if md.get("webseeds"):
            mapping["webseeds"] = json.dumps(sorted(set(existing_webseeds + md["webseeds"])))
        for key in ("created_by", "creation_date", "comment", "piece_length", "num_pieces"):
            val = md.get(key)
            if val in (None, "", 0):
                continue
            if not (existing.get(key.encode(), b"").decode() if existing else ""):
                mapping[key] = str(val)
        if md.get("private") and not existing.get(b"private"):
            mapping["private"] = "1"

    r.hset(meta_key, mapping=mapping)

    return {
        "infohash": ih,
        "name": info["name"],
        "size_bytes": info["size_bytes"],
        "magnet": info["magnet"],
        "groups": merged_groups,
        "already_tracked": already,
    }


def delete_manual_torrent(infohash: str) -> bool:
    """Remove meta + history for ``infohash``. Returns True if something was removed."""
    r = _redis()
    deleted = 0
    deleted += int(r.delete(f"torrent_health:meta:{infohash}") or 0)  # type: ignore[arg-type]
    deleted += int(r.delete(f"torrent_health:scans:{infohash}") or 0)  # type: ignore[arg-type]
    for k in r.scan_iter(match=f"torrent_health:scan:{infohash}:*"):
        r.delete(k)
        deleted += 1
    return deleted > 0


# ─── Orchestration ─────────────────────────────────────────────────────


def should_scan(meta: dict[str, Any] | None, alive_interval: int, dead_interval: int, frozen_interval: int,
                now: datetime | None = None) -> bool:
    """Adaptive scheduling.

    * No meta → always scan.
    * Alive (peers_count > 0 in last scan) → every ``alive_interval``.
    * Dead < 7 days ago → every ``dead_interval``.
    * Frozen (dead > 7 days) → every ``frozen_interval``.
    """
    if not meta:
        return True
    now = now or _now()
    last_scan_iso = meta.get("last_scan")
    if not last_scan_iso:
        return True
    try:
        last_scan = datetime.strptime(last_scan_iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except Exception:
        return True

    last_peers = int(meta.get("last_peers_count") or 0)
    last_alive_iso = meta.get("last_seen_alive")
    if last_peers > 0:
        interval = alive_interval
    elif last_alive_iso:
        try:
            last_alive = datetime.strptime(last_alive_iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        except Exception:
            return True
        age = (now - last_alive).total_seconds()
        interval = dead_interval if age < 7 * 86400 else frozen_interval
    else:
        interval = dead_interval
    return (now - last_scan).total_seconds() >= interval


def run_once(
    only: list[str] | None = None,
    scan_duration: int = DEFAULT_SCAN_DURATION,
    batch_size: int = DEFAULT_BATCH_SIZE,
    alive_interval: int = DEFAULT_ALIVE_INTERVAL,
    dead_interval: int = DEFAULT_DEAD_INTERVAL,
    frozen_interval: int = DEFAULT_FROZEN_INTERVAL,
    max_infohashes: int | None = None,
    listen_port: int = 6881,
) -> dict[str, int]:
    """Single pass scan over the magnets referenced in DB_POSTS.

    Magnets eligible for scanning are grouped into batches of ``batch_size``
    and observed concurrently in one libtorrent session (all batches share
    the same session + DHT state). A batch completes in ``scan_duration``
    seconds regardless of the number of magnets in it.

    ``only`` is an optional list of infohashes to restrict to (lowercased).
    Returns counters ``{scanned, skipped, failed, purged, total}``.
    """
    _purge_stale_tempdirs()
    targets = collect_magnets()
    only_set = {x.lower() for x in only} if only else None
    if only_set:
        # First keep post-linked entries matching --only, then for any
        # infohash the user requested that isn't in DB_POSTS, pull its
        # magnets straight from DB_TORRENT_HEALTH (handles ad-hoc magnets
        # previously ingested via --magnet).
        targets = {k: v for k, v in targets.items() if k.lower() in only_set}
        missing = only_set - {k.lower() for k in targets}
        if missing:
            for ih in missing:
                meta = get_meta(ih)
                if meta and meta.get("magnets"):
                    targets[ih] = {
                        "magnets": list(meta["magnets"]),
                        "groups": list(meta.get("groups") or []),
                    }

    if max_infohashes:
        targets = dict(list(targets.items())[:max_infohashes])

    # Interval filter first — we want to skip before adding anything to the session.
    eligible: list[tuple[str, dict[str, Any]]] = []
    skipped = 0
    for infohash, data in targets.items():
        meta = get_meta(infohash)
        if only_set is None and not should_scan(
            meta, alive_interval=alive_interval, dead_interval=dead_interval,
            frozen_interval=frozen_interval,
        ):
            skipped += 1
            continue
        eligible.append((infohash, data))

    if not eligible:
        return {"scanned": 0, "skipped": skipped, "failed": 0, "purged": purge_dead(), "total": len(targets)}

    sess = build_session(listen_port=listen_port)
    # DHT cold bootstrap: contact bootstrap nodes, fill the routing table,
    # and allow a first round of get_peers requests to resolve before the
    # first batch starts scanning. Shorter windows miss most peers.
    time.sleep(30)
    try:
        is_dht = bool(sess.is_dht_running())
        dht_nodes = int(sess.status().dht_nodes) if hasattr(sess, "status") else -1
        logger.info("session bootstrap: dht_running=%s dht_nodes=%d", is_dht, dht_nodes)
    except Exception as e:
        logger.warning("could not probe session status: %s", e)

    scanned = failed = 0
    batch_size = max(1, batch_size)
    for start in range(0, len(eligible), batch_size):
        batch = eligible[start:start + batch_size]
        magnets = [d["magnets"][0] for _, d in batch]
        by_infohash = {ih: d for ih, d in batch}
        logger.info("scanning batch of %d (%d/%d)", len(batch), start + len(batch), len(eligible))
        try:
            results = scan_batch(sess, magnets, duration=scan_duration)
        except Exception as e:
            logger.warning("batch failed: %s", e)
            failed += len(batch)
            continue
        seen = set()
        for result in results:
            entry: dict[str, Any] | None = by_infohash.get(result.infohash)
            if not entry:
                # infohash may differ (v1 vs v2); fall back to first batch entry not yet seen
                for ih, d in batch:
                    if ih not in seen:
                        entry = d
                        seen.add(ih)
                        break
            else:
                seen.add(result.infohash)
            if not entry:
                continue
            try:
                store_scan(result, entry["magnets"], entry["groups"])
                scanned += 1
                logger.info(
                    "scanned %s: %d peers (%d seed / %d leech)",
                    result.infohash, result.peers_count, result.seeders, result.leechers,
                )
            except Exception as e:
                failed += 1
                logger.warning("store failed for %s: %s", result.infohash, e)
        # Infohashes in the batch that produced no result
        for ih, _ in batch:
            if ih not in seen:
                failed += 1
                logger.warning("no result for %s in this batch", ih)

    purged = purge_dead()
    return {"scanned": scanned, "skipped": skipped, "failed": failed, "purged": purged, "total": len(targets)}
