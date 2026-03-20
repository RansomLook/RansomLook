#!/usr/bin/env python3

from subprocess import Popen, run

from valkey import Valkey
from valkey.exceptions import ConnectionError

from ransomlook.default import DB_TASKS, get_homedir, get_socket_path
from ransomlook.default.logging import get_logger

logger = get_logger("stop")


def main() -> None:
    get_homedir()
    p = Popen(["shutdown"])
    p.wait()
    try:
        r = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_TASKS)
        r.delete("shutdown")
        logger.info("Shutting down databases...")
        p_backend = run(["run_backend", "--stop"])
        p_backend.check_returncode()
        logger.info("done.")
    except ConnectionError:
        # Already down, skip the stacktrace
        pass


if __name__ == "__main__":
    main()
