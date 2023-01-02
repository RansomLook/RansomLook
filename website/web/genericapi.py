#!/usr/bin/env python3

import base64
import hashlib
import json
from typing import Any, Dict, Optional
from redis import Redis

import flask_login  # type: ignore
from flask import request

from flask_restx import Api, Namespace, Resource, abort, fields  # type: ignore
from werkzeug.security import check_password_hash

from ransomlook import ransomlook
from ransomlook.default import get_socket_path

from .helpers import build_users_table, load_user_from_request

api = Namespace('GenericAPI', description='Generic Ransomlook API', path='/api')

@api.route('/recent')
@api.doc(description='Return the 100 last posts')
class RecentPost(Resource):
    def get(self):
        posts = []
        red = Redis(unix_socket_path=get_socket_path('cache'), db=2)
        for key in red.keys():
                entries = json.loads(red.get(key)) # type: ignore
                for entry in entries:
                    entry['group_name']=key.decode()
                    posts.append(entry)
        sorted_posts = sorted(posts, key=lambda x: x['discovered'], reverse=True)
        recentposts = []
        for post in sorted_posts:
                recentposts.append(post)
                if len(recentposts) == 100:
                        break
        return recentposts

@api.route('/groups')
@api.doc(description='Return list of groups')
class Groups(Resource):
    def get(self):
        groups = []
        red = Redis(unix_socket_path=get_socket_path('cache'), db=0)
        for key in red.keys():
            groups.append(key.decode())
        return groups

@api.route('/markets')
@api.doc(description='Return list of markets')
class Markets(Resource):
    def get(self):
        groups = []
        red = Redis(unix_socket_path=get_socket_path('cache'), db=3)
        for key in red.keys():
            groups.append(key.decode())
        return groups

@api.route('/leaks')
@api.doc(description='Return list of breaches')
class Leaks(Resource):
    def get(self):
        groups = []
        red = Redis(unix_socket_path=get_socket_path('cache'), db=4)
        for key in red.keys():
            groups.append(key.decode())
        return groups

@api.route('/group/<string:name>')
@api.doc(description='Return info about the group')
@api.doc(param={'name':'Name of the group'})
class Groupinfo(Resource):
   def get(self, name):
        red = Redis(unix_socket_path=get_socket_path('cache'), db=0)
        group = {}
        sorted_posts:list = []
        for key in red.keys():
                if key.decode().lower() == name.lower():
                        group= json.loads(red.get(key)) # type: ignore
                        if group['meta'] is not None:
                            group['meta']=group['meta'].replace('\n', '<br/>')
                        redpost = Redis(unix_socket_path=get_socket_path('cache'), db=2)
                        if key in redpost.keys():
                            posts=json.loads(redpost.get(key)) # type: ignore
                            sorted_posts = sorted(posts, key=lambda x: x['discovered'], reverse=True)
                        else:
                            sorted_posts = []
        return [group, sorted_posts]

@api.route('/market/<string:name>')
@api.doc(description='Return info about the market')
@api.doc(param={'name':'Name of the market'})
class Marketinfo(Resource):
   def get(self, name):
        red = Redis(unix_socket_path=get_socket_path('cache'), db=3)
        group = {}
        sorted_posts: list  = []
        for key in red.keys():
                if key.decode().lower() == name.lower():
                        group= json.loads(red.get(key)) # type: ignore
                        if group['meta'] is not None:
                            group['meta']=group['meta'].replace('\n', '<br/>')
                        redpost = Redis(unix_socket_path=get_socket_path('cache'), db=2)
                        if key in redpost.keys():
                            posts=json.loads(redpost.get(key)) # type: ignore
                            sorted_posts = sorted(posts, key=lambda x: x['discovered'], reverse=True)
                        else:
                            sorted_posts = []
        return [group, sorted_posts]


@api.route('/export/<database>')
class Exportdb(Resource):
    def get(self, database):
        if database not in ['0','2','3','4','5','6']:
            return(['You are not allowed to dump this DataBase'])
        red = Redis(unix_socket_path=get_socket_path('cache'), db=database)
        dump={}
        for key in red.keys():
            dump[key.decode()]=json.loads(red.get(key))
        return dump
