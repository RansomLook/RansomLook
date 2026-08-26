#!/usr/bin/env python3
import argparse
import glob
import importlib
import logging
from os.path import basename, dirname, isfile, join

from ransomlook.default.logging import get_logger
from ransomlook.posts import appender

logger = get_logger("parse")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run ransomware parsers")
    parser.add_argument("names", nargs="*", help="Parser name(s) to run (e.g. lockbit3 akira). If omitted, runs all.")
    parser.add_argument("--list", action="store_true", help="List available parsers and exit")
    parser.add_argument("--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"], default=None, help="Override log level (e.g. --log-level DEBUG)")
    args = parser.parse_args()

    if args.log_level:
        level = getattr(logging, args.log_level)
        logging.getLogger().setLevel(level)
        for handler in logging.getLogger().handlers:
            handler.setLevel(level)

    modules = glob.glob(join(dirname("ransomlook/parsers/"), "*.py"))
    available = sorted([basename(f)[:-3] for f in modules if isfile(f) and not basename(f).startswith("_")])

    if args.list:
        logger.info("Available parsers (%s):", len(available))
        for p in available:
            logger.info("  %s", p)
        return

    if args.names:
        to_run = []
        for name in args.names:
            if name in available:
                to_run.append(name)
            else:
                logger.error("Parser not found: %s", name)
        if not to_run:
            return
    else:
        to_run = available

    logger.info("Running %s parser(s)", len(to_run))
    for p in to_run:
        module = importlib.import_module(f"ransomlook.parsers.{p}")
        logger.info("Parser : %s", p)
        try:
            for entry in module.main():
                # Per entry, not per parser: one malformed victim used to drop
                # every victim listed after it, and the crash repeats on each
                # run because it happens before the write.
                try:
                    appender(entry, p)
                except Exception:
                    logger.exception("Error with : %s, entry: %r", p, entry)
        except Exception:
            logger.exception("Error with : %s", p)


if __name__ == "__main__":
    main()
