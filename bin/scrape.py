#!/usr/bin/env python3
import argparse
import logging

from ransomlook import ransomlook
from ransomlook.default.logging import get_logger

logger = get_logger("scrape")


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape ransomware sites")
    parser.add_argument("names", nargs="*", help="Group name(s) to scrape (e.g. lockbit3 akira). If omitted, scrapes all.")
    parser.add_argument("--db", type=int, choices=[0, 3], default=None, help="Database: 0=groups, 3=markets. If omitted, scrapes both.")
    parser.add_argument("--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"], default=None, help="Override log level")
    args = parser.parse_args()

    if args.log_level:
        level = getattr(logging, args.log_level)
        logging.getLogger().setLevel(level)
        for handler in logging.getLogger().handlers:
            handler.setLevel(level)

    if args.names:
        dbs = [args.db] if args.db is not None else [0, 3]
        for db in dbs:
            logger.info("Scraping %s group(s) in DB %s", len(args.names), db)
            ransomlook.scraper(db, args.names)
    else:
        if args.db is not None:
            logger.info("Scraping all in DB %s", args.db)
            ransomlook.scraper(args.db)
        else:
            logger.info("Scraping all groups and markets")
            ransomlook.scraper(0)
            ransomlook.scraper(3)


if __name__ == "__main__":
    main()
