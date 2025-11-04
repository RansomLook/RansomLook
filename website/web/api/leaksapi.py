#!/usr/bin/env python3

import json
from redis import Redis

from flask_restx import Namespace, Resource # type: ignore

from ransomlook.default import get_socket_path

from typing import Any, Dict, List

api = Namespace('LeaksAPI', description='Leaks Ransomlook API', path='/api/leaks')

@api.route('/leaks')
@api.doc(description='Return list of breaches', tags=['breaches'])
class Leaks(Resource): # type: ignore[misc]
    def get(self) -> List[Dict[str, Any]]:
        leaks = []
        red = Redis(unix_socket_path=get_socket_path('cache'), db=4)
        for key in red.keys():
            leak = {}
            leak['id'] = int(key.decode())
            leak['name'] = json.loads(red.get(key))['name'] # type: ignore
            leaks.append(leak)
        return sorted(leaks, key=lambda x: x['id'])

@api.route('/leaks/<string:id>')
@api.doc(description='Return details for a breach', tags=['breaches'])
@api.doc(param={'id':'Id of the leak'})
class LeaksDetails(Resource): # type: ignore[misc]
    def get(self, id: str) -> Dict[str, Any]:
        red = Redis(unix_socket_path=get_socket_path('cache'), db=4)
        return json.loads(red.get(id)) # type: ignore
