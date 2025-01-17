#!/usr/bin/env python3
import importlib
from os.path import dirname, basename, isfile, join
import glob
import json

from datetime import datetime
from datetime import timedelta

import collections

import valkey # type: ignore

from ransomlook.default.config import get_config, get_socket_path

from ransomlook.posts import appender
from ransomlook.sharedutils import dbglog, stdlog, errlog, statsgroup, run_data_viz

from typing import Dict, Optional, Union, Any, List

def main() -> None:
    modules = glob.glob(join(dirname('ransomlook/parsers/'), "*.py"))
    __all__ = [ basename(f)[:-3] for f in modules if isfile(f) and not f.endswith('__init__.py')]
    for parser in __all__:
        module = importlib.import_module(f'ransomlook.parsers.{parser}')
        print('\nParser : '+parser)

        try:
            for entry in module.main():
                appender(entry, parser)
        except Exception as e:
            print("Error with : " + parser)
            print(e)
            pass
    valkey_handle = valkey.Valkey(unix_socket_path=get_socket_path('cache'), db=2)
    for key in valkey_handle.keys():
        statsgroup(key)
    run_data_viz(7)
    run_data_viz(14)
    run_data_viz(30)
    run_data_viz(90)

if __name__ == '__main__':
    main()

