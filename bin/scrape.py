#!/usr/bin/env python3
from ransomlook import ransomlook
from ransomlook.default.logging import get_logger

logger = get_logger("scrape")


def main() -> None:
    logger.info("Starting scraping")
    ransomlook.scraper(0)
    ransomlook.scraper(3)


if __name__ == "__main__":
    main()
