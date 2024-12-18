#!/usr/bin/env python3

import logging
from subprocess import Popen

from ransomlook.default import get_config, get_homedir, AbstractManager

logging.basicConfig(format='%(asctime)s %(name)s %(levelname)s:%(message)s',
                    level=logging.INFO)


class Website(AbstractManager):

    def __init__(self, loglevel: int=logging.INFO) -> None:
        super().__init__(loglevel)
        self.script_name = 'website'
        self.process = self._launch_website()
        self.set_running()

    def _launch_website(self) -> Popen: # type: ignore[type-arg]
        website_dir = get_homedir() / 'website'
        ip = get_config('generic', 'website_listen_ip')
        port = get_config('generic', 'website_listen_port')
        return Popen(['gunicorn', '-w', '10',
                      '--graceful-timeout', '2', '--timeout', '300',
                      '--limit-request-line', '500000',
                      '--limit-request-field_size', '500000',
                      '--limit-request-fields', '200000',
                      '-b', f'{ip}:{port}',
                      'web:app'],
                     cwd=website_dir)


def main() -> None:
    w = Website()
    w.run(sleep_in_sec=10)


if __name__ == '__main__':
    main()
