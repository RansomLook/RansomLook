import hashlib
import os
import json
from functools import lru_cache

import flask_login  # type: ignore
from werkzeug.security import generate_password_hash

from typing import Any, Dict

from ransomlook.default import get_config, get_homedir
from pathlib import Path

def load_user_from_request(request): # type: ignore
    api_key = request.headers.get('Authorization')
    if not api_key:
        return None
    user = User()
    api_key = api_key.strip()
    keys_table = build_keys_table()
    if api_key in keys_table:
        user.id = keys_table[api_key]
        return user
    return None

class User(flask_login.UserMixin): # type: ignore
    pass

@lru_cache(64)
def build_keys_table() -> Dict[str, str]:
    keys_table = {}
    for username, authstuff in build_users_table().items():
        if 'authkey' in authstuff:
            keys_table[authstuff['authkey']] = username
    return keys_table


@lru_cache(64)
def get_users() -> Any:
    try:
        # Use legacy user mgmt, no need to print a warning, and it will fail on new install.
        return get_config('generic', 'cache_clean_user', quiet=True)
    except Exception:
        return get_config('generic', 'users')


@lru_cache(64)
def build_users_table() -> Dict[str, Dict[str, str]]:
    users_table: Dict[str, Dict[str, str]] = {}
    for username, authstuff in get_users().items():
        if isinstance(authstuff, str):
            # just a password, make a key
            users_table[username] = {}
            users_table[username]['password'] = generate_password_hash(authstuff)
            users_table[username]['authkey'] = hashlib.pbkdf2_hmac('sha256', get_secret_key(),
                                                                   authstuff.encode(),
                                                                   100000).hex()

        elif isinstance(authstuff, list) and len(authstuff) == 2:
            if isinstance(authstuff[0], str) and isinstance(authstuff[1], str) and len(authstuff[1]) == 64:
                users_table[username] = {}
                users_table[username]['password'] = generate_password_hash(authstuff[0])
                users_table[username]['authkey'] = authstuff[1]
        else:
            raise Exception('User setup invalid. Must be "username": "password" or "username": ["password", "token 64 chars (sha256)"]')
    return users_table


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
def sri_load() -> Any:
    with (get_homedir() / 'website' / 'web' / 'sri.txt').open() as f:
        return json.load(f)
