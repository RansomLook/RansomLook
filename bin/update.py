#!/usr/bin/env python3

import argparse
import hashlib
import logging
import platform
import shlex
import subprocess
import sys
from pathlib import Path

from ransomlook.default import get_homedir

logging.basicConfig(format='%(asctime)s %(name)s %(levelname)s:%(message)s',
                    level=logging.INFO)


def compute_hash_self() -> bytes:
    m = hashlib.sha256()
    with (get_homedir() / 'bin' / 'update.py').open('rb') as f:
        m.update(f.read())
        return m.digest()


def keep_going(ignore: bool=False) -> None:
    if ignore:
        return
    keep_going = input('Continue? (y/N) ')
    if keep_going.lower() != 'y':
        print('Okay, quitting.')
        sys.exit()


def run_command(command: str, expect_fail: bool=False, capture_output: bool=True) -> None:
    args = shlex.split(command)
    homedir = get_homedir()
    process = subprocess.run(args, cwd=homedir, capture_output=capture_output)
    if capture_output:
        print(process.stdout.decode())
    if process.returncode and not expect_fail:
        print(process.stderr.decode())
        sys.exit()


def check_poetry_version() -> None:
    args = shlex.split("poetry self -V")
    homedir = get_homedir()
    process = subprocess.run(args, cwd=homedir, capture_output=True)
    poetry_version_str = process.stdout.decode()
    version = poetry_version_str.split()[2]
    version = version.strip(')')
    version_details = tuple(int(i) for i in version.split('.'))
    if version_details < (1, 8, 4):
        print('Ransomlook requires poetry >= 1.8.4, please update.')
        print('If you installed with "pip install --user poetry", run "pip install --user -U poetry"')
        print('If you installed via the recommended method, use "poetry self update"')
        print('More details: https://github.com/python-poetry/poetry#updating-poetry')
        sys.exit()


def main() -> None:
    parser = argparse.ArgumentParser(description='Pull latest release, update dependencies, update and validate the config files, update 3rd deps for the website.')
    parser.add_argument('--yes', default=False, action='store_true', help='Run all commands without asking.')
    args = parser.parse_args()

    old_hash = compute_hash_self()

    print('* Update repository.')
    keep_going(args.yes)
    run_command('git pull')
    new_hash = compute_hash_self()
    if old_hash != new_hash:
        print('Update script changed, please do "poetry run update"')
        sys.exit()

    check_poetry_version()

    print('* Install/update dependencies.')
    keep_going(args.yes)
    run_command('poetry install')

    print('* Install or make sure the playwright browsers are installed.')
    keep_going(args.yes)
    run_command('poetry run playwright install')

    print('* Validate configuration files.')
    keep_going(args.yes)
    run_command(f'poetry run {(Path("tools") / "validate_config_files.py").as_posix()} --check')

    print('* Update configuration files.')
    keep_going(args.yes)
    run_command(f'poetry run {(Path("tools") / "validate_config_files.py").as_posix()} --update')

    print('* Update third party dependencies for the website.')
    keep_going(args.yes)
    run_command(f'poetry run {(Path("tools") / "3rdparty.py").as_posix()}')
    run_command(f'poetry run {(Path("tools") / "generate_sri.py").as_posix()}')

    print('* Restarting RansomLook.')
    keep_going(args.yes)
    if platform.system() == 'Windows':
        print('Restarting Ransomlook with poetry...')
        run_command('poetry run stop', expect_fail=True)
        run_command('poetry run start', capture_output=False)
        print('Lookyloo started.')
    else:
        service = "ransomlook"
        p = subprocess.run(["systemctl", "is-active", "--quiet", service])
        try:
            p.check_returncode()
            print('Restarting Ransomlook with systemd...')
            run_command('sudo service ransomlook restart')
            print('done.')
        except subprocess.CalledProcessError:
            print('Restarting Ransomlook with poetry...')
            run_command('poetry run stop', expect_fail=True)
            run_command('poetry run start', capture_output=False)
            print('Ransomlook started.')


if __name__ == '__main__':
    main()
