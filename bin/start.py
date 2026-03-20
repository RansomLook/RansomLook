#!/usr/bin/env python3

from subprocess import Popen, run

from ransomlook.default import get_homedir
from ransomlook.default.logging import get_logger

logger = get_logger("start")


def main() -> None:
    # Just fail if the env isn't set.
    get_homedir()
    logger.info("Start backend (redis)...")
    p = run(["run_backend", "--start"])
    p.check_returncode()
    logger.info("done.")
    logger.info("Start website...")
    Popen(["start_website"])
    logger.info("done.")


if __name__ == "__main__":
    main()
