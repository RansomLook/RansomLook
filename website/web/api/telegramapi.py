#!/usr/bin/env python3

import json
from typing import Any, Dict, Optional
from valkey import Valkey

from flask import send_from_directory

from flask_restx import Namespace, Resource # type: ignore

from ransomlook import ransomlook
from ransomlook.default import get_socket_path, get_homedir

from collections import OrderedDict

from typing import List, Any, Dict

api = Namespace('TelegramAPI', description='Telegram Ransomlook API', path='/api/telegram')

@api.route('/channels')
@api.doc(description='Return list of groups', tags=['channels'])
class Channels(Resource): # type: ignore[misc]
    def get(self): # type: ignore
        groups = []
        valkey_handle = Valkey(unix_socket_path=get_socket_path('cache'), db=5)
        for key in valkey_handle.keys():
            groups.append(key.decode())
        return groups

@api.route('/channel/<string:name>')
@api.doc(description='Return info about the group', tags=['channels'])
@api.doc(param={'name':'Name of the group'})
class Channnelinfo(Resource): # type: ignore[misc]
    def get(self, name: str) -> List[Any]:
        valkey_handle = Valkey(unix_socket_path=get_socket_path('cache'), db=5)
        group = {}
        sorted_posts:Dict[str, Any] = {}
        for key in valkey_handle.keys():
                if key.decode().lower() == name.lower():
                        group= json.loads(valkey_handle.get(key)) # type: ignore
                        if group['meta'] is not None:
                            group['meta']=group['meta'].replace('\n', '<br/>')
                        valkey_post_handle = Valkey(unix_socket_path=get_socket_path('cache'), db=6)
                        if key in valkey_post_handle.keys():
                            posts=json.loads(valkey_post_handle.get(key)) # type: ignore
                            sorted_posts = OrderedDict(sorted(posts.items(), key=lambda t: t[0], reverse=True))
                        else:
                            sorted_posts = {}
        if group == {}:
            return []
        return [group, sorted_posts]

@api.route('/channel/<string:name>/image/<string:image>')
@api.doc(description='Return the requested image from the channel', tags=['channels'])
@api.doc(param={'name':'Name of the group', 'image':'Image to get'})
class Channelimg(Resource): # type: ignore[misc]
    def get(self, name: str, image: str): # type: ignore[no-untyped-def]
        return send_from_directory( str(get_homedir())+ '/source/screenshots/telegram/img',name+'-'+image+'.jpg')

