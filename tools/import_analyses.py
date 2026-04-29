#!/usr/bin/env python3
"""Bulk-import in-house Markdown analyses into RansomLook's data/analyses/.

Source layout (one folder per ransomware family, may contain extra artefacts
the script ignores):

    /home/fafner/Documents/ransowmare/<family>/{<prefix_>FULL_ANALYSIS.md,<prefix_>SUMMARY.md, ...}

Target layout:

    <homedir>/data/analyses/<family-lowercase>/{FULL_ANALYSIS.md,SUMMARY.md,meta.json}

The script is idempotent: re-running it overwrites the target files only when
the source mtime is newer.

Usage:
    python tools/import_analyses.py --src /path/to/ransomware --dry-run
    python tools/import_analyses.py --src /path/to/ransomware            # actually copy
    python tools/import_analyses.py --src /path/to/ransomware --force    # overwrite even if older
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from pathlib import Path

# Make sure RansomLook's homedir helper is importable when the script is run from anywhere.
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

try:
    from ransomlook.default.config import get_homedir
except Exception as e:
    print(f"warning: could not import ransomlook.default.config ({e}); falling back to PWD")
    def get_homedir() -> Path:
        return ROOT


# Filenames we accept as the canonical full report or summary inside a source folder.
FULL_PATTERNS = ["FULL_ANALYSIS.md", "*_FULL_ANALYSIS.md"]
SUMMARY_PATTERNS = ["SUMMARY.md", "*_SUMMARY.md"]


def _first_match(folder: Path, patterns: list[str]) -> Path | None:
    for pat in patterns:
        hits = sorted(folder.glob(pat))
        if hits:
            return hits[0]
    return None


def _safe_name(family: str) -> str:
    """Normalise a folder name into a safe lowercase slug (mirrors the Flask helper)."""
    return re.sub(r"[^a-z0-9_-]+", "", family.lower().strip())


def _maybe_extract_sha256(md_path: Path) -> str | None:
    """Best-effort: pick the first 64-hex-char string under a 'SHA-256' table cell."""
    try:
        text = md_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None
    m = re.search(r"SHA-?256[^\n]*\|[^|\n]*?([a-fA-F0-9]{64})", text)
    return m.group(1).lower() if m else None


def _copy(src: Path, dst: Path, force: bool) -> bool:
    if not src.exists():
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists() and not force:
        if dst.stat().st_mtime >= src.stat().st_mtime:
            return False
    shutil.copy2(src, dst)
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--src", required=True, help="Source root (a directory of family folders)")
    parser.add_argument("--target", default=None, help="Target data/analyses (default: <homedir>/data/analyses)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be copied")
    parser.add_argument("--force", action="store_true", help="Overwrite even if the target is newer")
    args = parser.parse_args()

    src_root = Path(args.src).resolve()
    if not src_root.is_dir():
        print(f"error: source {src_root} is not a directory")
        return 2

    target_root = Path(args.target).resolve() if args.target else (Path(get_homedir()) / "data" / "analyses").resolve()
    target_root.mkdir(parents=True, exist_ok=True)

    print(f"src    : {src_root}")
    print(f"target : {target_root}")
    print(f"mode   : {'DRY-RUN' if args.dry_run else 'COPY'}{' (force)' if args.force else ''}")
    print()

    counters = {"copied": 0, "skipped": 0, "missing": 0, "groups": 0}

    for family_dir in sorted(p for p in src_root.iterdir() if p.is_dir()):
        slug = _safe_name(family_dir.name)
        if not slug:
            continue
        full_md = _first_match(family_dir, FULL_PATTERNS)
        if not full_md:
            counters["missing"] += 1
            continue
        counters["groups"] += 1
        summary_md = _first_match(family_dir, SUMMARY_PATTERNS)
        target_dir = target_root / slug

        action = "[skip]"
        if args.dry_run:
            action = "[would copy]"
            counters["copied"] += 1
        else:
            did_full = _copy(full_md, target_dir / "FULL_ANALYSIS.md", args.force)
            did_summary = bool(summary_md and _copy(summary_md, target_dir / "SUMMARY.md", args.force))
            if did_full or did_summary:
                action = "[copy]"
                counters["copied"] += 1
            else:
                counters["skipped"] += 1
            # Bonus: write a meta.json sidecar with the SHA-256 if we can extract one.
            if did_full or not (target_dir / "meta.json").exists():
                sha = _maybe_extract_sha256(full_md)
                meta_path = target_dir / "meta.json"
                meta = {}
                if meta_path.exists():
                    try:
                        meta = json.loads(meta_path.read_text(encoding="utf-8"))
                    except Exception:
                        meta = {}
                if sha and meta.get("sha256") != sha:
                    meta["sha256"] = sha
                    target_dir.mkdir(parents=True, exist_ok=True)
                    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")

        print(f"  {action:<14} {family_dir.name:<22}-> {slug:<22}{'(+SUMMARY)' if summary_md else ''}")

    print()
    print(f"groups with FULL_ANALYSIS  : {counters['groups']}")
    print(f"sources missing FULL_*     : {counters['missing']}")
    print(f"copied / would-copy        : {counters['copied']}")
    print(f"skipped (target newer)     : {counters['skipped']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
