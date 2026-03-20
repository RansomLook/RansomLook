#!/usr/bin/env python3
import glob
import importlib
from os.path import basename, dirname, isfile, join

from ransomlook.default.logging import get_logger
from ransomlook.posts import appender

logger = get_logger("parse")


def main() -> None:
    modules = glob.glob(join(dirname("ransomlook/parsers/"), "*.py"))
    __all__ = [basename(f)[:-3] for f in modules if isfile(f) and not basename(f).startswith("_")]
    for parser in __all__:
        module = importlib.import_module(f"ransomlook.parsers.{parser}")
        logger.info("Parser : %s", parser)
        try:
            for entry in module.main():
                appender(entry, parser)
        except Exception:
            logger.exception("Error with : %s", parser)


if __name__ == "__main__":
    main()
