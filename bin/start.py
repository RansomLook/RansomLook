#!/usr/bin/env python3

from subprocess import Popen, run

from ransomlook.default import get_config, get_homedir


def main() -> None:
    # Just fail if the env isn't set.
    get_homedir()
    print('Start backend (valkey)...')
    p = run(['run_backend', '--start'])
    p.check_returncode()
    print('done.')
    print('Start website...')
    Popen(['start_website'])
    print('done.')

if __name__ == '__main__':
    main()
