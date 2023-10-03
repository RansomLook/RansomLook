#!/usr/bin/env python3

import base64
import hashlib
import json
from typing import Any, Dict, Optional
from redis import Redis

import flask_login  # type: ignore
from flask import request
from flask import send_file, send_from_directory

from flask_restx import Api, Namespace, Resource, abort, fields  # type: ignore
from werkzeug.security import check_password_hash

from ransomlook import ransomlook
from ransomlook.default import get_socket_path, get_homedir

import tempfile

import matplotlib.pyplot as plt
import plotly.express as px # type: ignore
import plotly.io as pio     # type: ignore
import pandas as pd

from collections import OrderedDict

from datetime import datetime, timedelta

api = Namespace('RecordedFutureAPI', description='RecordedFuture Ransomlook API', path='/api/rf')

@api.route('/leaks')
@api.doc(description='Return list of leak', tags=['channels'])
class RFLeaks(Resource):
    def get(self):
        leaks = []
        red = Redis(unix_socket_path=get_socket_path('cache'), db=10)
        for key in red.keys():
            leaks.append(key.decode())
        return leaks

@api.route('/leak/<string:name>')
@api.doc(description='Return info about the leak', tags=['channels'])
@api.doc(param={'name':'Name of the leak'})
class RFLeakinfo(Resource):
    def get(self, name):
        red = Redis(unix_socket_path=get_socket_path('cache'), db=10)
        leak = None
        leak = red.get(name.encode())
        if leak :
            return json.loads(leak)
        return {}
