#!/usr/bin/env python3
"""
Pre-generate screenshot thumbnails on disk.

Mirrors the logic of website.web.screenshot_thumb so that visiting /urls or
/group/<name> pages never triggers thumb generation on the request path.

Usage:
    poetry run python tools/generate_thumbs.py            # incremental
    poetry run python tools/generate_thumbs.py --force    # rebuild all
    poetry run python tools/generate_thumbs.py --jobs 4   # parallel workers
    poetry run python tools/generate_thumbs.py --dry-run  # report only
"""

import argparse
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from PIL import Image

from ransomlook.default import get_homedir

THUMB_SIZE = (280, 180)
SRC_EXTS = {".png", ".jpg", ".jpeg", ".webp"}
SKIP_DIRS = {"thumbs", "old", "logo"}


def _thumb_path_for(src: Path, screenshots_root: Path) -> Path:
    rel = src.relative_to(screenshots_root)
    return screenshots_root / "thumbs" / rel.with_suffix(".jpg")


def _needs_rebuild(src: Path, thumb: Path, force: bool) -> bool:
    if force or not thumb.is_file():
        return True
    try:
        return src.stat().st_mtime > thumb.stat().st_mtime
    except OSError:
        return True


def _make_thumb(src_str: str, thumb_str: str) -> tuple[str, bool, str]:
    try:
        src = Path(src_str)
        thumb = Path(thumb_str)
        thumb.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(src) as img:
            img.thumbnail(THUMB_SIZE, Image.LANCZOS)
            if img.mode != "RGB":
                img = img.convert("RGB")
            img.save(thumb, "JPEG", quality=75, optimize=True)
        return (src_str, True, "")
    except Exception as e:  # noqa: BLE001
        return (src_str, False, str(e))


def _iter_sources(screenshots_root: Path):
    for root, dirs, files in os.walk(screenshots_root):
        # Only honour top-level skip dirs: source/screenshots/<skip>/...
        if Path(root) == screenshots_root:
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            p = Path(root, f)
            if p.suffix.lower() in SRC_EXTS:
                yield p


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--force", action="store_true", help="Rebuild every thumb")
    ap.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 2) - 1),
                    help="Parallel workers (default: N-1 cores)")
    ap.add_argument("--dry-run", action="store_true", help="Only report what would be done")
    ap.add_argument("--quiet", action="store_true", help="Suppress per-file output")
    ap.add_argument("--limit", type=int, default=0, help="Stop after N rebuilds (debug)")
    args = ap.parse_args()

    screenshots_root = Path(get_homedir()) / "source" / "screenshots"
    if not screenshots_root.is_dir():
        print(f"error: {screenshots_root} does not exist", file=sys.stderr)
        return 2

    todo: list[tuple[Path, Path]] = []
    scanned = 0
    for src in _iter_sources(screenshots_root):
        scanned += 1
        thumb = _thumb_path_for(src, screenshots_root)
        if _needs_rebuild(src, thumb, args.force):
            todo.append((src, thumb))
            if args.limit and len(todo) >= args.limit:
                break

    print(f"scanned {scanned} source image(s); {len(todo)} thumb(s) to build")

    if args.dry_run:
        for src, _thumb in todo[:20]:
            print(f"  would build: {src.relative_to(screenshots_root)}")
        if len(todo) > 20:
            print(f"  ... and {len(todo) - 20} more")
        return 0

    if not todo:
        return 0

    t0 = time.time()
    ok = 0
    ko = 0
    with ProcessPoolExecutor(max_workers=args.jobs) as ex:
        futures = {
            ex.submit(_make_thumb, str(src), str(thumb)): src
            for src, thumb in todo
        }
        for n, fut in enumerate(as_completed(futures), 1):
            src_str, success, err = fut.result()
            if success:
                ok += 1
                if not args.quiet and (n % 50 == 0 or n == len(todo)):
                    print(f"  [{n}/{len(todo)}] built")
            else:
                ko += 1
                print(f"  FAIL {src_str}: {err}", file=sys.stderr)

    dt = time.time() - t0
    rate = (ok + ko) / dt if dt > 0 else 0
    print(f"done: {ok} built, {ko} failed in {dt:.1f}s ({rate:.1f}/s)")
    return 0 if ko == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
