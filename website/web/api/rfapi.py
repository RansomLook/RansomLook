#!/usr/bin/env python3

import json
from valkey import Valkey #type: ignore

from flask_restx import Namespace, Resource # type: ignore

from ransomlook import ransomlook
from ransomlook.default import get_socket_path, get_homedir

from collections import OrderedDict

from typing import Any, List, Dict

api = Namespace('RecordedFutureAPI', description='RecordedFuture Ransomlook API', path='/api/rf')

@api.route('/leaks')
@api.doc(description='Return list of leak', tags=['channels'])
class RFLeaks(Resource): # type: ignore[misc]
    def get(self) -> List[str]:
        leaks = []
        valkey_handle = Valkey(unix_socket_path=get_socket_path('cache'), db=10)
        for key in valkey_handle.keys():
            leaks.append(key.decode())
        return leaks

@api.route('/leak/<string:name>')
@api.doc(description='Return info about the leak', tags=['channels'])
@api.doc(param={'name':'Name of the leak'})
class RFLeakinfo(Resource): # type: ignore[misc]
    def get(self, name: str): # type: ignore[no-untyped-def]
        valkey_handle = Valkey(unix_socket_path=get_socket_path('cache'), db=10)
        leak = None
        leak = valkey_handle.get(name.encode())
        if leak :
            return json.loads(leak)
        return {}
