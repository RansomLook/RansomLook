#!/usr/bin/env python3

import json
from typing import Any, Dict, Optional
from redis import Redis

from flask import send_from_directory

from flask_restx import Namespace, Resource # type: ignore

from ransomlook import ransomlook
from ransomlook.default import get_socket_path, get_homedir

from collections import OrderedDict

api = Namespace('TelegramAPI', description='Telegram Ransomlook API', path='/api/telegram')

@api.route('/channels')
@api.doc(description='Return list of groups', tags=['channels'])
class Channels(Resource):
    def get(self):
        groups = []
        red = Redis(unix_socket_path=get_socket_path('cache'), db=5)
        for key in red.keys():
            groups.append(key.decode())
        return groups

@api.route('/channel/<string:name>')
@api.doc(description='Return info about the group', tags=['channels'])
@api.doc(param={'name':'Name of the group'})
class Channnelinfo(Resource):
    def get(self, name):
        red = Redis(unix_socket_path=get_socket_path('cache'), db=5)
        group = {}
        sorted_posts:Dict = {}
        for key in red.keys():
                if key.decode().lower() == name.lower():
                        group= json.loads(red.get(key)) # type: ignore
                        if group['meta'] is not None:
                            group['meta']=group['meta'].replace('\n', '<br/>')
                        redpost = Redis(unix_socket_path=get_socket_path('cache'), db=6)
                        if key in redpost.keys():
                            posts=json.loads(redpost.get(key)) # type: ignore
                            sorted_posts = OrderedDict(sorted(posts.items(), key=lambda t: t[0], reverse=True))
                        else:
                            sorted_posts = {}
        if group == {}:
            return {}
        return [group, sorted_posts]

@api.route('/channel/<string:name>/image/<string:image>')
@api.doc(description='Return the requested image from the channel', tags=['channels'])
@api.doc(param={'name':'Name of the group', 'image':'Image to get'})
class Channelimg(Resource):
    def get(self, name, image):
        return send_from_directory( str(get_homedir())+ '/source/screenshots/telegram/img',name+'-'+image+'.jpg')

