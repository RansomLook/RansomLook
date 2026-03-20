#!/usr/bin/env python3
import sys

from ransomlook import ransomlook
from ransomlook.default.logging import get_logger

logger = get_logger("add")


def main() -> None:
    logger.info("Adding location")
    if len(sys.argv) != 4:
        logger.error("usage : poetry run add [group url DB(0or3)]")
        exit(1)
    ransomlook.adder(sys.argv[1].lower(), sys.argv[2], int(sys.argv[3]), fs=True)


if __name__ == "__main__":
    main()
