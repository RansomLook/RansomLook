import os
import json
from functools import lru_cache

from typing import Any, Dict, List, Optional, Union, TypedDict

from ransomlook.default import get_config, get_homedir

@lru_cache(64)
def get_secret_key() -> bytes:
    secret_file_path: Path = get_homedir() / 'secret_key'
    if not secret_file_path.exists() or secret_file_path.stat().st_size < 64:
        if not secret_file_path.exists() or secret_file_path.stat().st_size < 64:
            with secret_file_path.open('wb') as f:
                f.write(os.urandom(64))
    with secret_file_path.open('rb') as f:
        return f.read()

@lru_cache(64)
def sri_load() -> Dict[str, Dict[str, str]]:
    with (get_homedir() / 'website' / 'web' / 'sri.txt').open() as f:
        return json.load(f)
