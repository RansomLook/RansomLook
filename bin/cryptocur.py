#!/usr/bin/env python3
import argparse
import json
import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

import requests
from valkey import Valkey

from ransomlook.default import DB_CRYPTO
from ransomlook.default.config import get_socket_path
from ransomlook.default.logging import get_logger

logger = get_logger("cryptocur")

API = "https://api.ransomwhe.re/export"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _slug(s: str) -> str:
    s = (s or "").strip().lower()
    out = []
    for ch in s:
        if ch.isalnum():
            out.append(ch)
        elif ch in " _./()[]{}&+'\"":
            out.append("-")
    slug = "".join(out)
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-")


def _norm_alias(s: str) -> str:
    s = (s or "").lower()
    return "".join(ch for ch in s if ch.isalnum())


def _resolve_group_db7(red7: Valkey, family: str) -> str:
    # DB7-only resolution: alias first, else slug; empty -> Unknwn -> 'unknwn'
    base = family if family else "Unknwn"
    ak = "crypto:alias:" + _norm_alias(base)
    tgt = red7.get(ak)
    if tgt:
        try:
            return tgt.decode()  # type: ignore[union-attr]
        except Exception:
            return str(tgt)
    return _slug(base) or "unknwn"


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


def _index_by_addr(items: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    idx = {}
    for it in items or []:
        chain = str(it.get("blockchain") or "unknown").strip().lower()
        addr = str(it.get("address") or "").strip()
        if not addr:
            continue
        idx[(chain, addr)] = it
    return idx


def _merge_transactions(old_list: list[Any], new_list: list[Any], new_source: str) -> list[Any]:
    # One entry per tx hash. Enrich existing with new fields, prefer existing on conflict.
    out_map: dict[str, dict[str, Any]] = {}

    for tx in old_list or []:
        k = _tx_key(tx)
        out_map[k] = dict(tx)
        if "source" not in out_map[k] or not out_map[k]["source"]:
            out_map[k]["source"] = tx.get("source") or "unknown"

    for tx in new_list or []:
        k = _tx_key(tx)
        if k in out_map:
            merged = out_map[k]
            for kk, vv in tx.items():
                if kk not in merged or merged[kk] in (None, "", 0):
                    merged[kk] = vv
            if not merged.get("source"):
                merged["source"] = new_source
        else:
            tx2 = dict(tx)
            tx2.setdefault("source", new_source)
            out_map[k] = tx2

    # Order by time desc
    def _t(v: tuple[str, Any]) -> str:
        t = v[1].get("time")
        return str(t) if t is not None else ""

    return [v for _, v in sorted(out_map.items(), key=_t, reverse=True)]


def main() -> int:
    parser = argparse.ArgumentParser(description="Import crypto addresses from ransomwhe.re")
    parser.add_argument("--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"], default=None, help="Override log level")
    args = parser.parse_args()

    if args.log_level:
        level = getattr(logging, args.log_level)
        logging.getLogger().setLevel(level)
        for handler in logging.getLogger().handlers:
            handler.setLevel(level)

    logger.info("Importing crypto addresses from ransomwhe.re (DB=7 only)")
    try:
        r = requests.get(API, timeout=90)
        r.raise_for_status()
        payload = r.json() or {}
    except Exception as e:
        logger.error("[crypto] fetch error: %s", e)
        return 2

    rows = payload.get("result") or []
    red7 = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_CRYPTO)

    # Bucketize by canonical group (DB7 only)
    buckets: dict[str, list[Any]] = defaultdict(list)
    for row in rows:
        addr = row.get("address")
        if not addr:
            continue
        family_raw = str(row.get("family") or "Unknwn")
        canon = _resolve_group_db7(red7, family_raw)

        item = dict(row)
        item["address"] = str(row.get("address")).strip()
        item["blockchain"] = str(row.get("blockchain") or "unknown").strip().lower()
        txs = item.get("transactions") or []
        # ensure every tx has a source + normalize satoshis to BTC
        chain_name = item["blockchain"]
        normalized_txs = []
        for tx in txs:
            tx = dict(tx)
            if "source" not in tx or not tx["source"]:
                tx["source"] = "ransomwhe.re"
            # Convert satoshis to BTC for bitcoin (ransomwhe.re is always in satoshis)
            a = tx.get("amount")
            if a is not None and chain_name == "bitcoin":
                try:
                    a = float(a)
                    tx["amount"] = a / 100_000_000
                except (ValueError, TypeError):
                    pass
            # Convert Unix timestamp to ISO string
            t = tx.get("time")
            if isinstance(t, (int, float)):
                try:
                    tx["time"] = datetime.fromtimestamp(t, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
                except (OSError, ValueError):
                    tx["time"] = str(t)
            normalized_txs.append(tx)
        item["transactions"] = normalized_txs
        item["tx_count"] = len(item["transactions"])
        try:
            item["last_tx_time"] = max(
                [str(t.get("time")) for t in item["transactions"] if isinstance(t, dict) and t.get("time") is not None]
            )  # type: ignore[type-var]
        except ValueError:
            item["last_tx_time"] = None

        now = _now_iso()
        item.setdefault("created_at", row.get("createdAt") or now)
        item["updated_at"] = now
        item["imported_at"] = now
        item["source"] = "ransomwhe.re"  # address-level source
        item["origin"] = "script"  # script import
        item.setdefault("family", family_raw)
        item["group"] = canon

        buckets[canon].append(item)

    created, updated, preserved = 0, 0, 0

    for canon, new_items in buckets.items():
        # new_items are per-address objects for this group
        # We will upsert per address key AND index under the group
        for obj in new_items:
            chain = obj.get("blockchain")
            addr = obj.get("address")
            if not addr:
                continue
            key = f"crypto:addr:{chain}:{addr}"
            old_raw = red7.get(key)
            if old_raw:
                try:
                    old = json.loads(old_raw)  # type: ignore[arg-type]
                except Exception:
                    old = {}
            else:
                old = {}

            origin = old.get("origin") or ""
            src = old.get("source") or ""

            if origin == "manual" or (src and src != "ransomwhe.re"):
                # Preserve manual address: no top-level overwrite, only merge transactions
                merged_txs = _merge_transactions(
                    old.get("transactions") or [], obj.get("transactions") or [], "ransomwhe.re"
                )
                old["transactions"] = merged_txs
                old["tx_count"] = len(merged_txs)
                try:
                    old["last_tx_time"] = max(
                        [t.get("time") for t in merged_txs if isinstance(t, dict) and t.get("time") is not None]
                    )  # type: ignore[type-var]
                except ValueError:
                    old["last_tx_time"] = None
                # Keep timestamps but update updated_at
                old["updated_at"] = _now_iso()
                doc = old
                preserved += 1
            elif old_raw:
                # Existing address from script: merge on top of existing doc to preserve enrichment
                merged_txs = _merge_transactions(
                    old.get("transactions") or [], obj.get("transactions") or [], "ransomwhe.re"
                )
                old["transactions"] = merged_txs
                old["tx_count"] = len(merged_txs)
                try:
                    old["last_tx_time"] = max(
                        [t.get("time") for t in merged_txs if isinstance(t, dict) and t.get("time") is not None]
                    )  # type: ignore[type-var]
                except ValueError:
                    old["last_tx_time"] = None
                # Update basic fields from ransomwhe.re without overwriting enriched data
                for field in ("group", "family", "blockchain", "address"):
                    if obj.get(field):
                        old[field] = obj[field]
                old.setdefault("source", "ransomwhe.re")
                old["updated_at"] = _now_iso()
                doc = old
                updated += 1
            else:
                # New address: use ransomwhe.re data as-is
                obj.setdefault("created_at", _now_iso())
                obj["updated_at"] = _now_iso()
                obj["tx_count"] = len(obj.get("transactions") or [])
                try:
                    obj["last_tx_time"] = max(
                        [t.get("time") for t in (obj.get("transactions") or []) if isinstance(t, dict) and t.get("time") is not None]
                    )  # type: ignore[type-var]
                except ValueError:
                    obj["last_tx_time"] = None
                doc = obj
                created += 1

            # Write address doc
            red7.set(key, json.dumps(doc, ensure_ascii=False))

            # Update group index (ensure membership is up-to-date)
            grp = doc.get("group") or canon
            red7.sadd(f"idx:group:{grp}:crypto", f"{chain}:{addr}")
            red7.sadd(f"idx:group:{grp}:crypto:{chain}", addr)

            # Update source index
            source = doc.get("source") or "unknown"
            red7.sadd(f"idx:source:{source}:crypto", f"{chain}:{addr}")

    logger.info("Done. created=%s, updated=%s, preserved_manual=%s", created, updated, preserved)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
