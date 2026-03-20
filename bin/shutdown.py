#!/usr/bin/env python3

import time

from ransomlook.default import AbstractManager
from ransomlook.default.logging import get_logger

logger = get_logger("shutdown")


def main() -> None:
    AbstractManager.force_shutdown()
    time.sleep(5)
    while True:
        running = AbstractManager.is_running()
        if not running:
            break
        logger.debug(running)
        time.sleep(5)


if __name__ == "__main__":
    main()
