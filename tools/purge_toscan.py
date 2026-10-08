#!/usr/bin/env python3
"""Purge la file `toscan` des captures que `screen()` ne pourra jamais traiter :
groupe disparu de la base, lien absent, ou lien pointant un fichier brut
(archive/dump) qu'il ne faut pas "screenshotter". On NE purge pas sur private :
un groupe/mirror prive est screenshote quand meme (reste interne cote site).

Dry-run par defaut (n'ecrit rien). Ajouter --apply pour reecrire toscan.
"""
import argparse
import json
from collections import Counter

import valkey

from ransomlook.default import DB_GROUPS, DB_TASKS, get_socket_path

RAW_FILE_EXT = (".zip", ".7z", ".rar", ".tar", ".gz", ".tgz", ".torrent", ".jsonl", ".csv")


def dead_reason(capture: dict, redgroup: valkey.Valkey) -> str | None:
    if redgroup.get(capture["group"].encode()) is None:
        return "groupe_absent"
    link = capture.get("link")
    if not link:
        return "link_absent"
    if str(link).lower().split("?")[0].endswith(RAW_FILE_EXT):
        return "link_fichier_brut"
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="reecrire toscan (sinon dry-run)")
    args = ap.parse_args()

    red = valkey.Valkey(unix_socket_path=get_socket_path("cache"), db=DB_TASKS)
    if b"toscan" not in red.keys():
        print("pas de toscan")
        return
    redgroup = valkey.Valkey(unix_socket_path=get_socket_path("cache"), db=DB_GROUPS)
    captures = json.loads(red.get("toscan"))

    keep, drop = [], Counter()
    newlist = []
    for c in captures:
        r = dead_reason(c, redgroup)
        if r is None:
            newlist.append(c)
        else:
            drop[r] += 1

    print(f"total     : {len(captures)}")
    print(f"a garder  : {len(newlist)}")
    print(f"a purger  : {sum(drop.values())}")
    for k, v in drop.most_common():
        print(f"   {v:4d}  {k}")

    if args.apply:
        red.set("toscan", json.dumps(newlist))
        print(f"\ntoscan reecrit : {len(newlist)} captures conservees.")
    else:
        print("\n[dry-run] rien ecrit. Relancer avec --apply pour purger.")


if __name__ == "__main__":
    main()
