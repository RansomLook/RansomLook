#!/usr/bin/env python3
"""
Fetch missing transactions for all crypto addresses in DB=7.

API: Breadcrumbs One (requires API key in config/generic.json)

Breadcrumbs supported chains:
  BTC, ETH, MATIC, SOL, TRX, BNB, DOGE, LTC, OP, BASE, BLAST, SCROLL,
  RON, CHZ, AA

Usage:
    python3 bin/update_crypto_tx.py              # update all addresses
    python3 bin/update_crypto_tx.py --chain bitcoin  # only bitcoin
    python3 bin/update_crypto_tx.py --group lockbit  # only one group
    python3 bin/update_crypto_tx.py --dry-run    # preview without writing
    python3 bin/update_crypto_tx.py --limit 10   # max 10 addresses
    python3 bin/update_crypto_tx.py --risk       # also fetch risk scores
    python3 bin/update_crypto_tx.py --stale-days 30  # only addresses not updated in 30 days
"""

import argparse
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any

import requests
from valkey import Valkey

from ransomlook.default import DB_CRYPTO
from ransomlook.default.config import get_config, get_socket_path
from ransomlook.default.logging import get_logger

# ---------------------------------------------------------------------------
# Breadcrumbs One chain mapping:  our DB name -> Breadcrumbs chain code
# ---------------------------------------------------------------------------
BREADCRUMBS_CHAINS = {
    "bitcoin": "BTC",
    "ethereum": "ETH",
    "litecoin": "LTC",
    "dogecoin": "DOGE",
    "polygon": "MATIC",
    "solana": "SOL",
    "tron": "TRX",
    "bnb": "BNB",
    "optimism": "OP",
    "base": "BASE",
    "blast": "BLAST",
    "scroll": "SCROLL",
    "ronin": "RON",
    "chiliz": "CHZ",
}

logger = get_logger("update_crypto_tx")

RATE_LIMIT_DELAY = 2.0  # seconds between Breadcrumbs requests
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "RansomLook/2.0 crypto-updater"})


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _tx_key(tx: dict[str, Any]) -> str:
    h = str(tx.get("hash") or "").strip()
    if h:
        return f"h:{h}"
    # Fallback for hashless tx
    t = tx.get("time")
    to_ = tx.get("to") if "to" in tx else tx.get("address") or ""
    frm = tx.get("from") if "from" in tx else tx.get("sender") or ""
    amt = tx.get("amount") or tx.get("value") or ""
    return f"x:{t}:{amt}:{to_}:{frm}"


# ---------------------------------------------------------------------------
# Breadcrumbs One — /smartexpand/transaction  (paginated)
# ---------------------------------------------------------------------------
def _fetch_breadcrumbs(api_key: str, chain: str, address: str, max_pages: int = 0) -> list[dict[str, Any]] | None:
    bc_chain = BREADCRUMBS_CHAINS.get(chain)
    if not bc_chain:
        return None

    url = "https://api.breadcrumbs.one/smartexpand/transaction"
    headers = {
        "X-API-KEY": api_key,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    txs: list[dict[str, Any]] = []
    cursor = None
    page = 0

    while True:
        body: dict[str, Any] = {"chain": bc_chain, "address": address}
        if cursor:
            body["cursor"] = cursor

        try:
            r = SESSION.post(url, json=body, headers=headers, timeout=30)
            retries = 0
            while r.status_code == 429 and retries < 3:
                retries += 1
                wait = 30 * retries
                logger.info("  [rate-limited] waiting %ss (attempt %s/3)...", wait, retries)
                time.sleep(wait)
                r = SESSION.post(url, json=body, headers=headers, timeout=30)
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            logger.error("  [breadcrumbs error] %s", e)
            return None if page == 0 else txs  # return what we have so far

        for raw in data.get("transactions") or []:
            tx: dict[str, Any] = {
                "hash": raw.get("transaction_hash") or "",
                "source": "ransomlook",
            }

            amt = raw.get("amount")
            if amt is not None:
                try:
                    amt = float(amt)
                    # Breadcrumbs always returns amounts in satoshis for Bitcoin
                    if bc_chain == "BTC":
                        amt = amt / 100_000_000
                    tx["amount"] = amt
                except (ValueError, TypeError):
                    tx["amount"] = amt

            sender = raw.get("sender_address")
            if sender:
                tx["from"] = sender
            receiver = raw.get("receiver_address")
            if receiver:
                tx["to"] = receiver

            tx_date = raw.get("transaction_date")
            if tx_date:
                tx["time"] = tx_date

            block = raw.get("block_number")
            if block is not None:
                tx["block"] = block

            txs.append(tx)

        cursor = data.get("next_cursor")
        page += 1
        if not cursor:
            break
        if max_pages and page >= max_pages:
            logger.info("  [max-pages] stopped at page %s (%s tx so far)", page, len(txs))
            break
        time.sleep(RATE_LIMIT_DELAY)

    logger.info("  [breadcrumbs] %s pages, %s tx fetched", page, len(txs))
    return txs


# ---------------------------------------------------------------------------
# Breadcrumbs One — /risk/address
# ---------------------------------------------------------------------------
def fetch_risk(api_key: str, chain: str, address: str) -> dict[str, Any] | None:
    bc_chain = BREADCRUMBS_CHAINS.get(chain)
    if not bc_chain:
        return None

    url = "https://api.breadcrumbs.one/risk/address"
    headers = {"X-API-KEY": api_key, "Accept": "application/json"}
    params = {"chain": bc_chain, "address": address}

    try:
        r = SESSION.get(url, params=params, headers=headers, timeout=30)
        if r.status_code == 429:
            time.sleep(30)
            r = SESSION.get(url, params=params, headers=headers, timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        logger.error("  [risk error] %s", e)
        return None


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------
def fetch_transactions(api_key: str, chain: str, address: str, max_pages: int = 0) -> list[dict[str, Any]] | None:
    if not api_key:
        logger.error("No Breadcrumbs API key configured")
        return None
    if chain not in BREADCRUMBS_CHAINS:
        logger.info("  [skip] chain '%s' not supported by Breadcrumbs", chain)
        return None
    return _fetch_breadcrumbs(api_key, chain, address, max_pages)


# ---------------------------------------------------------------------------
# Merge
# ---------------------------------------------------------------------------
def merge_transactions(
    existing: list[dict[str, Any]], new_txs: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], int, int]:
    # One entry per tx hash. Enrich existing with new fields.
    existing_by_key: dict[str, dict[str, Any]] = {}
    for tx in existing:
        existing_by_key[_tx_key(tx)] = tx

    added = 0
    enriched = 0
    for tx in new_txs:
        k = _tx_key(tx)
        if k in existing_by_key:
            old = existing_by_key[k]
            changed = False
            for field in ("from", "to", "amount", "amountUSD", "block", "time", "fee"):
                new_val = tx.get(field)
                if new_val is not None and new_val != "" and old.get(field) != new_val:
                    old[field] = new_val
                    changed = True
            if changed:
                enriched += 1
        else:
            existing_by_key[k] = tx
            added += 1

    merged = list(existing_by_key.values())
    return merged, added, enriched


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(description="Update crypto transactions from Breadcrumbs One API")
    parser.add_argument("--chain", help="Only process this blockchain (e.g., bitcoin)")
    parser.add_argument("--group", help="Only process this group")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing to Redis")
    parser.add_argument("--limit", type=int, default=0, help="Max addresses to process (0=all)")
    parser.add_argument("--risk", action="store_true", help="Also fetch risk scores from Breadcrumbs")
    parser.add_argument("--stale-days", type=int, default=0, help="Only process addresses not updated in N days (0=all)")
    parser.add_argument("--max-pages", type=int, default=0, help="Max API pages per address (0=all, each page ~50 tx)")
    parser.add_argument("--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"], default=None, help="Override log level")
    args = parser.parse_args()

    if args.log_level:
        level = getattr(logging, args.log_level)
        logging.getLogger().setLevel(level)
        for handler in logging.getLogger().handlers:
            handler.setLevel(level)

    # Load Breadcrumbs API key from config
    bc_conf = get_config("generic", "breadcrumbs", quiet=True)
    api_key = ""
    if isinstance(bc_conf, dict) and bc_conf.get("enable"):
        api_key = bc_conf.get("api_key", "")

    if api_key:
        logger.info("Breadcrumbs One API: enabled")
        logger.info("Supported chains: %s", ', '.join(sorted(BREADCRUMBS_CHAINS.keys())))
    else:
        logger.error("Breadcrumbs One API: disabled — enable in config/generic.json: breadcrumbs.enable=true + api_key")
        return 1

    red = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_CRYPTO)

    # Collect all crypto:addr:* keys
    keys = []
    cursor = 0
    while True:
        cursor, batch = red.scan(cursor=cursor, match="crypto:addr:*", count=500)  # type: ignore[misc]
        keys.extend(batch)
        if cursor == 0:
            break

    logger.info("Found %s address keys in DB=7", len(keys))

    processed = 0
    updated = 0
    skipped = 0
    errors = 0
    risk_fetched = 0
    stats_by_group: dict[str, dict[str, int]] = {}

    for raw_key in sorted(keys):
        key = raw_key.decode()
        parts = key.split(":", 3)
        if len(parts) < 4:
            continue
        chain = parts[2]
        addr = parts[3]

        # Filter by chain
        if args.chain and chain != args.chain:
            continue

        # Check if chain is supported
        if chain not in BREADCRUMBS_CHAINS or not api_key:
            skipped += 1
            continue

        # Load current doc
        raw_doc = red.get(raw_key)
        if not raw_doc:
            continue
        try:
            doc = json.loads(raw_doc)  # type: ignore[arg-type]
        except Exception:
            continue

        # Filter by group
        if args.group:
            if doc.get("group", "").lower() != args.group.lower():
                continue

        # Filter by staleness
        if args.stale_days > 0:
            updated_at = doc.get("updated_at", "")
            if updated_at:
                try:
                    last = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
                    age = (datetime.now(timezone.utc) - last).days
                    if age < args.stale_days:
                        skipped += 1
                        continue
                except Exception:
                    pass  # can't parse date, process anyway

        if args.limit and processed >= args.limit:
            logger.info("Reached limit of %s addresses", args.limit)
            break

        existing_txs = doc.get("transactions") or []
        existing_count = len(existing_txs)
        group = doc.get("group") or "?"
        source = doc.get("source") or "?"
        label = doc.get("label") or ""
        label_str = f" [{label}]" if label else ""

        logger.info("[%s] %s | %s:%s…%s (src=%s, %s tx)", processed + 1, group, chain, addr[:24], label_str, source, existing_count)

        time.sleep(RATE_LIMIT_DELAY)
        new_txs = fetch_transactions(api_key, chain, addr, args.max_pages)

        if new_txs is None:
            logger.info("SKIP (API error)")
            errors += 1
            processed += 1
            continue

        if not new_txs:
            logger.info("OK (no new tx from API)")
            processed += 1
            continue

        merged, added, enriched = merge_transactions(existing_txs, new_txs)

        if added == 0 and enriched == 0:
            logger.info("OK (no changes, %s tx from API matched %s existing)", len(new_txs), existing_count)
        else:
            logger.info("+%s new, %s enriched (was: %s, now: %s, API returned: %s)", added, enriched, existing_count, len(merged), len(new_txs))

            g = doc.get("group") or "?"
            if g not in stats_by_group:
                stats_by_group[g] = {"addresses": 0, "new_tx": 0}
            stats_by_group[g]["addresses"] += 1
            stats_by_group[g]["new_tx"] += added

        # Risk score
        if args.risk and api_key and chain in BREADCRUMBS_CHAINS:
            time.sleep(RATE_LIMIT_DELAY)
            risk = fetch_risk(api_key, chain, addr)
            if risk:
                doc["risk_score"] = risk.get("risk_score")
                doc["entity_tags"] = risk.get("entity_tags", [])
                risk_fetched += 1
                logger.info("    risk=%s tags=%s", risk.get('risk_score'), risk.get('entity_tags', []))

        has_changes = added > 0 or enriched > 0
        if not args.dry_run and (has_changes or args.risk):
            if has_changes:
                # Normalize timestamps in all transactions
                for tx in merged:
                    t = tx.get("time")
                    if isinstance(t, (int, float)):
                        try:
                            tx["time"] = datetime.fromtimestamp(t, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
                        except (OSError, ValueError):
                            tx["time"] = str(t)
                doc["transactions"] = merged
                doc["tx_count"] = len(merged)

            doc["updated_at"] = _now_iso()

            times = []
            for tx in merged if has_changes else existing_txs:
                t = tx.get("time")
                if t is not None:
                    times.append(str(t))
            if times:
                doc["last_tx_time"] = max(times)

            red.set(raw_key, json.dumps(doc, ensure_ascii=False))

        if has_changes:
            updated += 1
        processed += 1

    logger.info("Done. processed=%s, updated=%s, skipped=%s, errors=%s", processed, updated, skipped, errors)
    if args.risk:
        logger.info("Risk scores fetched: %s", risk_fetched)

    if stats_by_group:
        logger.info("%-30s %10s %10s", 'Group', 'Addresses', 'New TX')
        logger.info("-" * 52)
        for g in sorted(stats_by_group, key=lambda x: stats_by_group[x]["new_tx"], reverse=True):
            s = stats_by_group[g]
            logger.info("%-30s %10s %10s", g, s['addresses'], s['new_tx'])

    if args.dry_run:
        logger.info("(dry-run — no changes written)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
