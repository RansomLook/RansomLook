#!/usr/bin/env python3

import base64
import hashlib
import json
from typing import Any, Dict, Optional
from redis import Redis

import flask_login  # type: ignore
from flask import request
from flask import send_file

from flask_restx import Api, Namespace, Resource, abort, fields  # type: ignore
from werkzeug.security import check_password_hash

from ransomlook import ransomlook
from ransomlook.default import get_socket_path, get_homedir
from ransomlook.sharedutils import createfile, striptld

import tempfile
import os

import matplotlib.pyplot as plt
import plotly.express as px # type: ignore
import plotly.io as pio     # type: ignore
import pandas as pd

from datetime import datetime, timedelta

api = Namespace('GenericAPI', description='Generic Ransomlook API', path='/api')

@api.route('/recent', '/recent/<int:number>')
@api.doc(description='Return the X last posts, by default 100', tags=['generic'])
class RecentPost(Resource):
    def get(self, number: int=100):
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
                if len(recentposts) == number:
                        break
        return recentposts

@api.route('/last', '/last/<int:number>')
@api.doc(description='Return posts for the last X days, by default 1', tags=['generic'])
class LastPost(Resource):
    def get(self, number: int=1):
        posts = []
        actualdate = datetime.now() + timedelta(days = -number)
        red = Redis(unix_socket_path=get_socket_path('cache'), db=2)
        for key in red.keys():
                entries = json.loads(red.get(key)) # type: ignore
                for entry in entries:
                    if datetime.strptime(entry['discovered'], '%Y-%m-%d %H:%M:%S.%f') > actualdate:
                        entry['group_name']=key.decode()
                        posts.append(entry)
        sorted_posts = sorted(posts, key=lambda x: x['discovered'], reverse=True)
        return sorted_posts


@api.route('/groups')
@api.doc(description='Return list of groups', tags=['groups'])
class Groups(Resource):
    def get(self):
        groups = []
        red = Redis(unix_socket_path=get_socket_path('cache'), db=0)
        for key in red.keys():
            groups.append(key.decode())
        return groups

@api.route('/markets')
@api.doc(description='Return list of markets', tags=['markets'])
class Markets(Resource):
    def get(self):
        groups = []
        red = Redis(unix_socket_path=get_socket_path('cache'), db=3)
        for key in red.keys():
            groups.append(key.decode())
        return groups

@api.route('/group/<string:name>')
@api.doc(description='Return info about the group', tags=['groups'])
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
                        for location in group['locations']:
                            screenfile = '/screenshots/' + name.lower() + '-' + createfile(location['slug']) + '.png'
                            screenpath = str(get_homedir()) + '/source' + screenfile
                            if os.path.exists(screenpath):
                                with open(screenpath, "rb") as image_file:
                                     screenencoded = base64.b64encode(image_file.read()).decode("ascii")
                                location.update({'screen':screenencoded})
                            source = name.lower() + '-' + striptld(location['slug']) + '.html'
                            sourcepath = str(get_homedir()) + '/source/' + source
                            if os.path.exists(sourcepath):
                                with open(sourcepath, "rb") as text_file:
                                     sourceencoded = base64.b64encode(text_file.read()).decode("ascii")
                                location.update({'source':sourceencoded})
                        redpost = Redis(unix_socket_path=get_socket_path('cache'), db=2)
                        if key in redpost.keys():
                            posts=json.loads(redpost.get(key)) # type: ignore
                            sorted_posts = sorted(posts, key=lambda x: x['discovered'], reverse=True)
                        else:
                            sorted_posts = []
        return [group, sorted_posts]

@api.route('/post/<string:name>/<string:postname>')
@api.doc(description='Return details about the post', tags=['groups'])
@api.doc(param={'name':'Name of the group or market', 'postname':'Post title'})
class GroupPost(Resource):
   def get(self, name,postname):
        red = Redis(unix_socket_path=get_socket_path('cache'), db=2)
        for key in red.keys():
            if key.decode().lower() == name.lower():
                posts = json.loads(red.get(key)) # type: ignore
                for post in posts:
                    if post['post_title'] == postname:
                        if 'screen' in post and post['screen'] != None :
                            screenpath = str(get_homedir()) + '/source/' + post['screen']
                            if os.path.exists(screenpath):
                                with open(screenpath, "rb") as image_file:
                                     screenencoded = base64.b64encode(image_file.read()).decode("ascii")
                                post.update({'screen':screenencoded})
                        if 'link' in post and post['link'] != None :
                            filepath = str(get_homedir()) + '/source/' + name + '/' + createfile(postname)+'.html'
                            if os.path.exists(filepath):
                                with open(filepath, "rb") as src_file:
                                     srcencoded = base64.b64encode(src_file.read()).decode("ascii")
                                post.update({'source':srcencoded})

                        return(post)
        return({})

@api.route('/market/<string:name>')
@api.doc(description='Return info about the market', tags=['markets'])
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
                        for location in group['locations']:
                            screenfile = '/screenshots/' + name.lower() + '-' + createfile(location['slug']) + '.png'
                            screenpath = str(get_homedir()) + '/source' + screenfile
                            if os.path.exists(screenpath):
                                with open(screenpath, "rb") as image_file:
                                     screenencoded = base64.b64encode(image_file.read()).decode("ascii")
                                location.update({'screen':screenencoded})
                            source = name.lower() + '-' + striptld(location['slug']) + '.html'
                            sourcepath = str(get_homedir()) + '/source/' + source
                            if os.path.exists(sourcepath):
                                with open(sourcepath, "rb") as text_file:
                                     sourceencoded = base64.b64encode(text_file.read()).decode("ascii")
                                location.update({'source':sourceencoded})
                        redpost = Redis(unix_socket_path=get_socket_path('cache'), db=2)
                        if key in redpost.keys():
                            posts=json.loads(redpost.get(key)) # type: ignore
                            sorted_posts = sorted(posts, key=lambda x: x['discovered'], reverse=True)
                        else:
                            sorted_posts = []
        return [group, sorted_posts]


@api.route('/export/<database>')
@api.doc(description='Dump a databse to reimport it', tags=['generic'])
class Exportdb(Resource):
    def get(self, database):
        if database not in ['0','2','3','4','5','6']:
            return(['You are not allowed to dump this DataBase'])
        red = Redis(unix_socket_path=get_socket_path('cache'), db=database)
        dump={}
        for key in red.keys():
            dump[key.decode()]=json.loads(red.get(key)) # type: ignore
        return dump

@api.route('/posts/<year>/<month>')
@api.doc(description='Dump posts for a month', tags=['posts'])
class PostPerMonth(Resource):
    def get(self, year, month):
        posts = []
        date = str(year)+'-'+str(month)
        red = Redis(unix_socket_path=get_socket_path('cache'), db=2)
        for key in red.keys():
                entries = json.loads(red.get(key)) # type: ignore
                for entry in entries:
                    if entry['discovered'].startswith(date):
                        entry['group_name']=key.decode()
                        posts.append(entry)
        sorted_posts = sorted(posts, key=lambda x: x['discovered'], reverse=True)
        return sorted_posts

@api.route('/graphs/heatmap/<year>/<month>')
@api.route('/graphs/heatmap/<year>')
@api.doc(description='Density heatmap for a month', tags=['posts'])
class DensityHeatmap(Resource):
    def get(self, year, month=None):
        group_names = []
        timestamps = []
        if month != None:
            date = str(year)+'-'+str(month)
        else :
            date = str(year)+'-'
        red = Redis(unix_socket_path=get_socket_path('cache'), db=2)
        for key in red.keys():
                entries = json.loads(red.get(key)) # type: ignore
                for entry in entries:
                    if entry['discovered'].startswith(date):
                        group_names.append(key.decode())
                        timestamps.append(entry['discovered'])
        df = pd.DataFrame({'group_name': group_names, 'timestamp': timestamps})
        df['timestamp'] = pd.to_datetime(df['timestamp'])

        df_sorted = df.groupby(['group_name', 'timestamp']).size().reset_index(name='count')
        df_sorted = df_sorted.sort_values(by='count', ascending=False)
        fig = px.density_heatmap(df_sorted, x='timestamp', y='group_name', z='count', title='Posts per group per day (heatmap)', width=1050, height=750)
        fig.update_layout(font=dict(family='Roboto'))
        filename = tempfile.TemporaryFile()
        fig.write_image(filename)
        filename.seek(0)
        return send_file(filename, mimetype='image/gif')

@api.route('/graphs/scatter/<year>')
@api.route('/graphs/scatter/<year>/<month>')
@api.doc(description='Distribution per days for a month', tags=['posts'])
class Scatter(Resource):
    def get(self, year, month=None):
        group_names = []
        timestamps = []
        if month != None:
            date = str(year)+'-'+str(month)
        else:
            date = str(year)+'-'
        red = Redis(unix_socket_path=get_socket_path('cache'), db=2)
        for key in red.keys():
                entries = json.loads(red.get(key)) # type: ignore
                for entry in entries:
                    if entry['discovered'].startswith(date):
                        group_names.append(key.decode())
                        timestamps.append(entry['discovered'])
        df = pd.DataFrame({'group_name': group_names, 'timestamp': timestamps})
        df['timestamp'] = pd.to_datetime(df['timestamp'])

        df_sorted = df.groupby(['group_name', 'timestamp']).size().reset_index(name='count')
        df_sorted = df_sorted.sort_values(by='count', ascending=False)
        fig = px.scatter(df_sorted, x='timestamp', y='group_name', color='group_name', title='Distribution per days', color_continuous_scale='Plotly3', width=1050, height=750)
        fig.update_layout(font=dict(family='Roboto'))
        filename = tempfile.TemporaryFile()
        fig.write_image(filename)
        filename.seek(0)
        return send_file(filename, mimetype='image/gif')

@api.route('/graphs/pie/<year>')
@api.route('/graphs/pie/<year>/<month>')
@api.doc(description='Percentage of total post during the month', tags=['posts'])
class Pie(Resource):
    def get(self, year, month=None):
        group_names = []
        timestamps = []
        if month != None:
            date = str(year)+'-'+str(month)
        else:
            date = str(year)+'-'
        red = Redis(unix_socket_path=get_socket_path('cache'), db=2)
        for key in red.keys():
                entries = json.loads(red.get(key)) # type: ignore
                for entry in entries:
                    if entry['discovered'].startswith(date):
                        group_names.append(key.decode())
                        timestamps.append(entry['discovered'])
        df = pd.DataFrame({'group_name': group_names, 'timestamp': timestamps})
        df['timestamp'] = pd.to_datetime(df['timestamp'])

        df_sorted = df.groupby(['group_name', 'timestamp']).size().reset_index(name='count')
        df_sorted = df_sorted.sort_values(by='count', ascending=False)
        df_sorted = df.groupby('group_name').size().reset_index(name='count').sort_values(by='count', ascending=True)
        fig = px.pie(df_sorted, values='count', names='group_name', title='Percentage of total post during the period', width=1050, height=750)
        fig.update_layout(font=dict(family='Roboto'))
        filename = tempfile.TemporaryFile()
        fig.write_image(filename)
        filename.seek(0)
        return send_file(filename, mimetype='image/gif')

@api.route('/graphs/bar/<year>')
@api.route('/graphs/bar/<year>/<month>')
@api.doc(description='Posts per group during the month', tags=['posts'])
class Bar(Resource):
    def get(self, year, month=None):
        group_names = []
        timestamps = []
        if month != None:
            date = str(year)+'-'+str(month)
        else:
            date = str(year)+'-'
        red = Redis(unix_socket_path=get_socket_path('cache'), db=2)
        for key in red.keys():
                entries = json.loads(red.get(key)) # type: ignore
                for entry in entries:
                    if entry['discovered'].startswith(date):
                        group_names.append(key.decode())
                        timestamps.append(entry['discovered'])
        df = pd.DataFrame({'group_name': group_names, 'timestamp': timestamps})
        df['timestamp'] = pd.to_datetime(df['timestamp'])

        df_sorted = df.groupby(['group_name', 'timestamp']).size().reset_index(name='count')
        df_sorted = df_sorted.sort_values(by='count', ascending=False)
        df_sorted = df.groupby('group_name').size().reset_index(name='count').sort_values(by='count', ascending=True)
        fig = px.bar(df_sorted, x='group_name', y='count', color='count', title='Posts per group during the month', color_continuous_scale='Portland',width=1050, height=750)
        fig.update_layout(font=dict(family='Roboto'))
        filename = tempfile.TemporaryFile()
        fig.write_image(filename)
        filename.seek(0)
        return send_file(filename, mimetype='image/gif')
