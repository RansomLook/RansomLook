#!/usr/bin/env python3
import argparse
import logging

from ransomlook import ransomlook
from ransomlook.default.logging import get_logger

logger = get_logger("screen")


def main() -> None:
    parser = argparse.ArgumentParser(description="Take screenshots of ransomware sites")
    parser.add_argument("--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"], default=None, help="Override log level")
    args = parser.parse_args()

    if args.log_level:
        level = getattr(logging, args.log_level)
        logging.getLogger().setLevel(level)
        for handler in logging.getLogger().handlers:
            handler.setLevel(level)

    logger.info("Starting screenshot")
    ransomlook.screen()
    logger.info("Stopping screenshot")


if __name__ == "__main__":
    main()
