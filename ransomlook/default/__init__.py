from .exceptions import RansomlookException

env_global_name: str = "RANSOMLOOK_HOME"

# ── Redis database mapping ──────────────────────────────────────────────
# Single source of truth for all DB numbers used across the project.
# NOTE: These must be defined before importing AbstractManager to avoid
# circular import issues (abstractmanager.py uses DB_TASKS).
DB_GROUPS = 0  # Ransomware group metadata and locations
DB_TASKS = 1  # Lacus queue, audit logs, API keys, internal tasks
DB_POSTS = 2  # Victim posts across all groups
DB_MARKETS = 3  # Market / forum metadata and locations
DB_LEAKS = 4  # Data breach records
DB_ACTORS = 5  # Threat actor profiles and relations
DB_HEALTH = 6  # Mirror uptime / health checks
DB_CRYPTO = 7  # Cryptocurrency wallets and transactions
DB_RF = 10  # Recorded Future channel data
DB_NOTES = 11  # Ransom notes
DB_ALERTS = 12  # Alert keywords and matches
DB_TORRENT_HEALTH = 13  # BitTorrent swarm health + peer samples
DB_LACUS = 15  # Lacus capture queue

from .abstractmanager import AbstractManager  # noqa
from .config import get_homedir, load_configs, get_config, get_socket_path  # noqa


__all__ = [
    "RansomlookException",
    "AbstractManager",
    "get_homedir",
    "load_configs",
    "get_config",
    "get_socket_path",
    "DB_GROUPS",
    "DB_TASKS",
    "DB_POSTS",
    "DB_MARKETS",
    "DB_LEAKS",
    "DB_ACTORS",
    "DB_HEALTH",
    "DB_CRYPTO",
    "DB_RF",
    "DB_NOTES",
    "DB_ALERTS",
    "DB_TORRENT_HEALTH",
    "DB_LACUS",
]
