#!/usr/bin/env python3
"""
Export cryptocurrency addresses to CSV.

Usage:
    python3 tools/crypto_export.py                     # all chains
    python3 tools/crypto_export.py --chain bitcoin     # bitcoin only
    python3 tools/crypto_export.py --chain ethereum     # ethereum only
    python3 tools/crypto_export.py -o addresses.csv     # custom output file
"""
import argparse
import csv
import json
import sys

from valkey import Valkey

from ransomlook.default import DB_CRYPTO
from ransomlook.default.config import get_socket_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Export crypto addresses to CSV")
    parser.add_argument("--chain", help="Filter by blockchain (e.g. bitcoin, ethereum)")
    parser.add_argument("-o", "--output", default=None, help="Output CSV file (default: stdout)")
    args = parser.parse_args()

    red = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_CRYPTO)
    pattern = f"crypto:addr:{args.chain}:*" if args.chain else "crypto:addr:*"

    rows = []
    for key in red.scan_iter(match=pattern):
        raw = red.get(key)
        if not raw:
            continue
        try:
            doc = json.loads(raw)  # type: ignore[arg-type]
        except Exception:
            continue
        rows.append({
            "group": doc.get("group", "unknown"),
            "address": doc.get("address", ""),
            "blockchain": doc.get("blockchain", "unknown"),
            "label": doc.get("label") or "",
        })

    rows.sort(key=lambda r: (r["group"], r["blockchain"], r["address"]))

    out = open(args.output, "w", newline="", encoding="utf-8") if args.output else sys.stdout
    writer = csv.DictWriter(out, fieldnames=["group", "blockchain", "address", "label"])
    writer.writeheader()
    writer.writerows(rows)

    if args.output:
        out.close()
        print(f"Exported {len(rows)} addresses to {args.output}")
    else:
        print(f"\n# {len(rows)} addresses", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
