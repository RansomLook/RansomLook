#!/usr/bin/env python3

import argparse
import hashlib
import json
import os
import platform
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

from ransomlook.default import get_homedir, get_socket_path
from ransomlook.default.logging import get_logger

logger = get_logger("update")

# Current version of RansomLook
CURRENT_VERSION = "2.0.0"

# File used to track the installed version
VERSION_FILE = ".version"


def compute_hash_self() -> bytes:
    m = hashlib.sha256()
    with (get_homedir() / "bin" / "update.py").open("rb") as f:
        m.update(f.read())
        return m.digest()


def keep_going(ignore: bool = False) -> None:
    if ignore:
        return
    keep_going = input("Continue? (y/N) ")
    if keep_going.lower() != "y":
        logger.info("Okay, quitting.")
        sys.exit()


def run_command(command: str, expect_fail: bool = False, capture_output: bool = True) -> None:
    args = shlex.split(command)
    homedir = get_homedir()
    process = subprocess.run(args, cwd=homedir, capture_output=capture_output)
    if capture_output:
        logger.info(process.stdout.decode())
    if process.returncode and not expect_fail:
        logger.error(process.stderr.decode())
        sys.exit()


def check_poetry_version() -> None:
    args = shlex.split("poetry self -V")
    homedir = get_homedir()
    process = subprocess.run(args, cwd=homedir, capture_output=True)
    poetry_version_str = process.stdout.decode()
    version = poetry_version_str.split()[2]
    version = version.strip(")")
    version_details = tuple(int(i) for i in version.split("."))
    if version_details < (2, 1, 0):
        logger.error("Ransomlook requires poetry >= 2.1.3, please update.")
        logger.error('If you installed with "pip install --user poetry", run "pip install --user -U poetry"')
        logger.error('If you installed via the recommended method, use "poetry self update"')
        logger.error("More details: https://github.com/python-poetry/poetry#updating-poetry")
        sys.exit()


def get_installed_version() -> str:
    """Read the installed version from the version file."""
    version_path = get_homedir() / VERSION_FILE
    if version_path.exists():
        return version_path.read_text().strip()
    return "0.0.0"


def set_installed_version(version: str) -> None:
    """Write the current version to the version file."""
    version_path = get_homedir() / VERSION_FILE
    version_path.write_text(version + "\n")


def parse_version(version: str) -> tuple[int, ...]:
    """Parse a version string into a comparable tuple.
    Handles: 2.0.0, 2.0.0-dev, 2.0.0.dev0, 1.7.0, etc."""
    import re
    nums = re.findall(r"(\d+)", version.split("-")[0].split(".dev")[0])
    return tuple(int(n) for n in nums) if nums else (0, 0, 0)


def migrate_to_2_0(auto_yes: bool = False) -> None:
    """Migration from v1.x to v2.0.

    Changes:
    - DB 5 was Telegram channels    -> now Threat Actors
    - DB 6 was Telegram messages    -> now Mirror Health
    - DB 8 was Twitter accounts     -> removed
    - DB 9 was Twitter messages     -> removed
    - Twitter config section removed from generic.json
    - Telegram directories cleaned up
    - redis dependency replaced by valkey
    """
    try:
        from valkey import Valkey
    except ImportError:
        from redis import Redis as Valkey  # type: ignore[assignment]

    logger.info("=" * 60)
    logger.info("  Migration to RansomLook 2.0")
    logger.info("=" * 60)
    logger.info("")

    # --- Step 1: Flush deprecated databases ---
    deprecated_dbs = {
        5: "Telegram channels (now used for Threat Actors)",
        6: "Telegram messages (now used for Mirror Health)",
        8: "Twitter accounts (removed)",
        9: "Twitter messages (removed)",
    }

    socket_path = get_socket_path("cache")
    if not os.path.exists(socket_path):
        logger.warning("Valkey is not running. Start the backend first: poetry run start")
        logger.warning("Skipping database migration.")
        return

    has_data = {}
    for db_num, description in deprecated_dbs.items():
        try:
            r = Valkey(unix_socket_path=socket_path, db=db_num)
            count = r.dbsize()
            if count > 0:  # type: ignore[operator]
                has_data[db_num] = (description, count)
        except Exception:
            pass

    if has_data:
        logger.info("The following databases contain legacy data that must be flushed:")
        logger.info("")
        for db_num, (description, count) in has_data.items():
            logger.info("  DB %s: %s (%s keys)", db_num, description, count)
        logger.info("")
        logger.info("These databases have been repurposed in v2.0.")
        logger.info("The old data (Telegram/Twitter) is no longer used.")
        logger.info("")

        if not auto_yes:
            confirm = input("Flush these databases? This cannot be undone. (y/N) ")
            if confirm.lower() != "y":
                logger.info("Migration aborted. The old data was NOT deleted.")
                logger.info('You can re-run "poetry run update" when ready.')
                sys.exit()

        for db_num, (description, count) in has_data.items():
            r = Valkey(unix_socket_path=socket_path, db=db_num)
            r.flushdb()
            logger.info("  Flushed DB %s: %s", db_num, description)

        logger.info("")
        logger.info("Legacy databases flushed successfully.")
    else:
        logger.info("No legacy data to flush.")

    # --- Step 2: Clean up old config ---
    config_path = get_homedir() / "config" / "generic.json"
    if config_path.exists():
        try:
            with open(config_path, encoding='utf-8') as f:
                config = json.load(f)

            modified = False

            # Remove twitter section
            if "twitter" in config:
                del config["twitter"]
                logger.info('Removed "twitter" section from config.')
                modified = True

            # Remove twitter from _notes
            if "_notes" in config and "twitter" in config["_notes"]:
                del config["_notes"]["twitter"]
                modified = True

            if modified:
                with open(config_path, "w", encoding='utf-8') as f:
                    json.dump(config, f, indent=4)
                    f.write("\n")
                logger.info("Configuration file updated.")
        except Exception as e:
            logger.warning("Could not update config: %s", e)
            logger.warning('Please manually remove the "twitter" section from config/generic.json')

    # --- Step 3: Clean up old directories ---
    homedir = get_homedir()
    old_dirs = [
        homedir / "source" / "telegram",
        homedir / "source" / "twitter",
        homedir / "source" / "screenshots" / "telegram",
        homedir / "source" / "screenshots" / "twitter",
    ]
    for d in old_dirs:
        if d.exists():
            shutil.rmtree(d)
            logger.info("Removed old directory: %s", d.relative_to(homedir))

    # --- Step 4: Create logs directory ---
    logs_dir = homedir / "logs"
    if not logs_dir.exists():
        logs_dir.mkdir(parents=True)
        logger.info("Created logs/ directory.")

    logger.info("")
    logger.info("Migration to v2.0 complete!")
    logger.info("")


def run_migrations(auto_yes: bool = False) -> None:
    """Detect version and run any pending migrations."""
    installed = get_installed_version()
    installed_tuple = parse_version(installed)

    if installed_tuple < (2, 0, 0):
        # Check actual installed package version
        try:
            from importlib.metadata import version
            pkg_version = version("ransomlook")
            pkg_tuple = parse_version(pkg_version) if pkg_version else (0, 0, 0)
        except Exception:
            pkg_tuple = (0, 0, 0)

        if pkg_tuple >= (2, 0, 0):
            logger.info("Already on version %s. Skipping migration, creating .version file.", pkg_version)
        else:
            migrate_to_2_0(auto_yes)

    set_installed_version(CURRENT_VERSION)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Pull latest release, update dependencies, update and validate the config files, update 3rd deps for the website."
    )
    parser.add_argument("--yes", default=False, action="store_true", help="Run all commands without asking.")
    args = parser.parse_args()

    old_hash = compute_hash_self()

    logger.info("* Update repository.")
    keep_going(args.yes)
    run_command("git pull")
    new_hash = compute_hash_self()
    if old_hash != new_hash:
        logger.info('Update script changed, please do "poetry run update"')
        sys.exit()

    check_poetry_version()

    logger.info("* Install/update dependencies.")
    keep_going(args.yes)
    run_command("poetry install")

    logger.info("* Install or make sure the playwright browsers are installed.")
    keep_going(args.yes)
    run_command("poetry run playwright install")

    logger.info("* Checking for pending migrations.")
    run_migrations(args.yes)

    logger.info("* Validate configuration files.")
    keep_going(args.yes)
    run_command(f"poetry run {(Path('tools') / 'validate_config_files.py').as_posix()} --check")

    logger.info("* Update configuration files.")
    keep_going(args.yes)
    run_command(f"poetry run {(Path('tools') / 'validate_config_files.py').as_posix()} --update")

    logger.info("* Update third party dependencies for the website.")
    keep_going(args.yes)
    run_command(f"poetry run {(Path('tools') / '3rdparty.py').as_posix()}")
    run_command(f"poetry run {(Path('tools') / 'generate_sri.py').as_posix()}")

    logger.info("* Restarting RansomLook.")
    keep_going(args.yes)
    if platform.system() == "Windows":
        logger.info("Restarting Ransomlook with poetry...")
        run_command("poetry run stop", expect_fail=True)
        run_command("poetry run start", capture_output=False)
        logger.info("Lookyloo started.")
    else:
        service = "ransomlook"
        p = subprocess.run(["systemctl", "is-active", "--quiet", service])
        try:
            p.check_returncode()
            logger.info("Restarting Ransomlook with systemd...")
            run_command("sudo service ransomlook restart")
            logger.info("done.")
        except subprocess.CalledProcessError:
            logger.info("Restarting Ransomlook with poetry...")
            run_command("poetry run stop", expect_fail=True)
            run_command("poetry run start", capture_output=False)
            logger.info("Ransomlook started.")


if __name__ == "__main__":
    main()
