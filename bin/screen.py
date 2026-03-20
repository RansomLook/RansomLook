#!/usr/bin/env python3
from ransomlook import ransomlook
from ransomlook.default.logging import get_logger

logger = get_logger("screen")


def main() -> None:
    logger.info("Starting screenshot")
    ransomlook.screen()
    logger.info("Stopping screenshot")


if __name__ == "__main__":
    main()
