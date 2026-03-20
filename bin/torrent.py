#!/usr/bin/env python3
from ransomlook import ransomlook
from ransomlook.default.logging import get_logger

logger = get_logger("torrent")


def main() -> None:
    logger.info("Starting torrent")
    ransomlook.gettorrentinfo()
    logger.info("Stopping torrent")


if __name__ == "__main__":
    main()
