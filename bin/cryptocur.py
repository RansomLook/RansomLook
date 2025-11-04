#!/usr/bin/env python3
import sys
import json
import time
from datetime import datetime, timezone
from typing import Dict, Any, Tuple, List
from collections import defaultdict

import requests
from redis import Redis
from ransomlook.default.config import get_socket_path

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

def _resolve_group_db7(red7: Redis, family: str) -> str:
    # DB7-only resolution: alias first, else slug; empty -> Unknwn -> 'unknwn'
    base = family if family else "Unknwn"
    ak = "crypto:alias:" + _norm_alias(base)
    tgt = red7.get(ak)
    if tgt:
        try:
            return tgt.decode()
        except Exception:
            return str(tgt)
    return _slug(base) or "unknwn"

def _tx_key(tx: Dict[str, Any]) -> str:
    # Prefer unique tx hash, else synthetic key on (time, value/amount, to/from)
    h = str(tx.get("hash") or "").strip()
    if h:
        return "h:" + h
    t = tx.get("time")
    val = tx.get("value") if "value" in tx else tx.get("amount")
    to_ = tx.get("to") if "to" in tx else tx.get("address")
    frm = tx.get("from") if "from" in tx else tx.get("sender")
    return f"x:{t}:{val}:{to_}:{frm}"

def _index_by_addr(items: List[Dict[str, Any]]) -> Dict[Tuple[str, str], Dict[str, Any]]:
    idx = {}
    for it in items or []:
        chain = str(it.get("blockchain") or "unknown").strip().lower()
        addr = str(it.get("address") or "").strip()
        if not addr:
            continue
        idx[(chain, addr)] = it
    return idx

def _merge_transactions(old_list, new_list, new_source: str):
    # Return union preserving existing tx fields; prefer existing on conflict
    out_map = {}
    for tx in old_list or []:
        k = _tx_key(tx)
        out_map[k] = dict(tx)  # copy
        if "source" not in out_map[k] or not out_map[k]["source"]:
            out_map[k]["source"] = tx.get("source") or "unknown"
    for tx in new_list or []:
        k = _tx_key(tx)
        if k in out_map:
            # merge non-destructively (keep existing fields, fill missing)
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
    # Optional: order by time desc if present
    def _t(v): 
        t = v[1].get("time")
        try: 
            return int(t) if t is not None else -1
        except Exception:
            return -1
    return [v for _, v in sorted(out_map.items(), key=_t, reverse=True)]

def main() -> int:
    print("Importing crypto addresses from ransomwhe.re (DB=7 only)")
    try:
        r = requests.get(API, timeout=90)
        r.raise_for_status()
        payload = r.json() or {}
    except Exception as e:
        print(f"[crypto] fetch error: {e}", file=sys.stderr)
        return 2

    rows = payload.get("result") or []
    red7 = Redis(unix_socket_path=get_socket_path('cache'), db=7)

    # Bucketize by canonical group (DB7 only)
    buckets: Dict[str, list] = defaultdict(list)
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
        # ensure every tx has a source
        item["transactions"] = [ dict(tx, **({"source": "ransomwhe.re"} if "source" not in tx or not tx["source"] else {})) for tx in txs ]
        item["tx_count"] = len(item["transactions"])
        try:
            item["last_tx_time"] = max([t.get("time") for t in item["transactions"] if isinstance(t, dict) and t.get("time") is not None])
        except ValueError:
            item["last_tx_time"] = None

        now = _now_iso()
        item.setdefault("created_at", row.get("createdAt") or now)
        item["updated_at"] = now
        item["imported_at"] = now
        item["source"] = "ransomwhe.re"   # address-level source
        item["origin"] = "script"         # script import
        item.setdefault("family", family_raw)
        item["group"] = canon

        buckets[canon].append(item)

    created, updated, preserved = 0, 0, 0

    for canon, new_items in buckets.items():
        # new_items are per-address objects for this group
        # We will upsert per address key AND index under the group
        for obj in new_items:
            chain = obj.get("blockchain")
            addr  = obj.get("address")
            if not addr:
                continue
            key = f"crypto:addr:{chain}:{addr}"
            old_raw = red7.get(key)
            if old_raw:
                try:
                    old = json.loads(old_raw)
                except Exception:
                    old = {}
            else:
                old = {}

            origin = old.get("origin") or ""
            src    = old.get("source") or ""

            if origin == "manual" or (src and src != "ransomwhe.re"):
                # Preserve manual address: no top-level overwrite, only merge transactions
                merged_txs = _merge_transactions(old.get("transactions") or [], obj.get("transactions") or [], "ransomwhe.re")
                old["transactions"] = merged_txs
                old["tx_count"] = len(merged_txs)
                try:
                    old["last_tx_time"] = max([t.get("time") for t in merged_txs if isinstance(t, dict) and t.get("time") is not None])
                except ValueError:
                    old["last_tx_time"] = None
                # Keep timestamps but update updated_at
                old["updated_at"] = _now_iso()
                doc = old
                preserved += 1
            else:
                # Update/insert script address: keep created_at if any, else set
                if "created_at" in old and "created_at" not in obj:
                    obj["created_at"] = old["created_at"]
                # Merge transactions (in case manual tx were previously added)
                merged_txs = _merge_transactions(old.get("transactions") or [], obj.get("transactions") or [], "ransomwhe.re")
                obj["transactions"] = merged_txs
                obj["tx_count"] = len(merged_txs)
                try:
                    obj["last_tx_time"] = max([t.get("time") for t in merged_txs if isinstance(t, dict) and t.get("time") is not None])
                except ValueError:
                    obj["last_tx_time"] = None
                doc = obj
                if old_raw:
                    updated += 1
                else:
                    created += 1

            # Write address doc
            red7.set(key, json.dumps(doc, ensure_ascii=False))

            # Update group index (ensure membership is up-to-date)
            grp = (doc.get("group") or canon)
            red7.sadd(f"idx:group:{grp}:crypto", f"{chain}:{addr}")
            red7.sadd(f"idx:group:{grp}:crypto:{chain}", addr)

            # Update source index
            source = doc.get("source") or "unknown"
            red7.sadd(f"idx:source:{source}:crypto", f"{chain}:{addr}")

    print(f"Done. created={created}, updated={updated}, preserved_manual={preserved}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
