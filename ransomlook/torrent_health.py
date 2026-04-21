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

import libtorrent as lt  # type: ignore[import-untyped]
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
            ips.add(entry[4][0])
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

    local_seeders = sum(1 for p in raw_peers if int(p.flags) & seed_flag) if seed_flag else 0
    local_leechers = max(0, len(raw_peers) - local_seeders)

    seeders = num_complete if num_complete > 0 else local_seeders
    leechers = num_incomplete if num_incomplete > 0 else local_leechers

    logger.debug(
        "%s raw_peers=%d tracker_num_complete=%d tracker_num_incomplete=%d "
        "local_seeders=%d local_leechers=%d → seeders=%d leechers=%d",
        infohash, len(raw_peers), num_complete, num_incomplete,
        local_seeders, local_leechers, seeders, leechers,
    )

    return ScanResult(
        infohash=infohash,
        ts=datetime.now(timezone.utc),
        name=tf.name() if tf else None,
        size_bytes=tf.total_size() if tf else None,
        seeders=seeders,
        leechers=leechers,
        peers=peers,
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

    Bandwidth: per-torrent download/upload limits are pinned at 1 byte/s once
    added, so the swarm content is never actually transferred — peer handshakes
    (which carry the bitfield we need for ``progress``) still complete because
    they exchange BT control messages, not piece data.

    Cleanup: each batch uses a dedicated tempdir. Removed torrents are wiped
    via ``delete_files`` and the tempdir is rmtree'd at the end so the leak
    filenames libtorrent allocates never linger on disk.
    """
    tempdir = tempfile.mkdtemp(prefix="rl-torrent-")

    handles: list[tuple[str, lt.torrent_handle]] = []
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
        # Throttle to 1 B/s in both directions before resuming. With this cap
        # the longest a 45–120 s scan can transfer is a few dozen bytes.
        try:
            torr.set_download_limit(1)
            torr.set_upload_limit(1)
        except Exception:
            pass
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

    results: list[ScanResult] = []
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

    # Belt and braces: scrub the tempdir even if libtorrent left fragments.
    try:
        shutil.rmtree(tempdir, ignore_errors=True)
    except Exception:
        pass
    return results


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

    # Update meta
    existing = r.hgetall(meta_key) or {}
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
    r.hset(meta_key, mapping=mapping)


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
    raw = r.hgetall(f"torrent_health:meta:{infohash}")
    if not raw:
        return None
    out: dict[str, Any] = {}
    for k, v in raw.items():
        key = k.decode()
        val = v.decode()
        if key in ("magnets", "groups", "sparkline"):
            try:
                out[key] = json.loads(val)
            except Exception:
                out[key] = []
        elif key in ("size_bytes", "last_seeders", "last_leechers", "last_peers_count"):
            try:
                out[key] = int(val)
            except Exception:
                out[key] = 0
        else:
            out[key] = val
    out["infohash"] = infohash
    return out


def get_history(infohash: str, limit: int | None = None) -> list[dict[str, Any]]:
    """Return scans ordered from newest to oldest. ``limit`` caps result size."""
    r = _redis()
    scans_key = f"torrent_health:scans:{infohash}"
    members = r.zrevrange(scans_key, 0, (limit or -1) - (0 if limit is None else 1))
    out = []
    for m in members:
        ts = m.decode()
        raw = r.get(f"torrent_health:scan:{infohash}:{ts}")
        if raw:
            try:
                out.append(json.loads(raw))
            except Exception:
                continue
    return out


def get_scan(infohash: str, ts_iso: str) -> dict[str, Any] | None:
    r = _redis()
    raw = r.get(f"torrent_health:scan:{infohash}:{ts_iso}")
    if not raw:
        return None
    try:
        return json.loads(raw)  # type: ignore[no-any-return]
    except Exception:
        return None


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
    for key in posts_r.scan_iter():  # type: ignore[union-attr]
        try:
            group = key.decode()
            raw = posts_r.get(key)
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

    return {
        ih: {
            "magnets": sorted(v["magnets"]),
            "groups": sorted(v["groups"]),
        }
        for ih, v in out.items()
    }


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
            data = by_infohash.get(result.infohash)
            if not data:
                # infohash may differ (v1 vs v2); fall back to first batch entry not yet seen
                for ih, d in batch:
                    if ih not in seen:
                        data = d
                        seen.add(ih)
                        break
            else:
                seen.add(result.infohash)
            if not data:
                continue
            try:
                store_scan(result, data["magnets"], data["groups"])
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
