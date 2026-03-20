#!/usr/bin/env python3
"""
One-shot script: normalize all Bitcoin transaction amounts from satoshis to BTC in DB=7.

Only converts transactions with source='ransomwhe.re' (always in satoshis).
Breadcrumbs/ransomlook transactions are already in BTC and are NOT touched.

Usage:
    python3 tools/normalize_crypto_amounts.py --dry-run   # preview
    python3 tools/normalize_crypto_amounts.py              # apply
"""
import argparse
import json

from valkey import Valkey

from ransomlook.default import DB_CRYPTO
from ransomlook.default.config import get_socket_path

SATOSHI_DIVISOR = 100_000_000


def main() -> int:
    parser = argparse.ArgumentParser(description="Normalize crypto amounts (satoshis → BTC)")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    args = parser.parse_args()

    red = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_CRYPTO)

    fixed_addrs = 0
    fixed_txs = 0
    total_addrs = 0

    for key in red.scan_iter(match="crypto:addr:bitcoin:*"):
        raw = red.get(key)
        if not raw:
            continue
        try:
            doc = json.loads(raw)  # type: ignore[arg-type]
        except Exception:
            continue

        total_addrs += 1
        changed = False
        for tx in doc.get("transactions", []):
            src = tx.get("source", "")
            # Only convert ransomwhe.re amounts (always in satoshis)
            if src != "ransomwhe.re":
                continue
            a = tx.get("amount")
            if a is None:
                continue
            try:
                a = float(a)
            except (ValueError, TypeError):
                continue
            # ransomwhe.re amounts are integers in satoshis (typically > 1000)
            if a > 1:
                tx["amount"] = a / SATOSHI_DIVISOR
                changed = True
                fixed_txs += 1

        if changed:
            fixed_addrs += 1
            if not args.dry_run:
                red.set(key, json.dumps(doc, ensure_ascii=False))

    print(f"Scanned {total_addrs} bitcoin addresses")
    print(f"Fixed {fixed_txs} transactions (ransomwhe.re source) across {fixed_addrs} addresses")
    if args.dry_run:
        print("(dry-run — no changes written)")
    else:
        print("Done — all ransomwhe.re amounts normalized to BTC")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
