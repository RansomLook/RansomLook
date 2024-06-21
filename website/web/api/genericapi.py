#!/usr/bin/env python3

import base64
import hashlib
import json
from typing import Any, Dict, Optional, List
from redis import Redis

import flask_login  # type: ignore
from flask import request
from flask import send_file

from flask_restx import Api, Namespace, Resource, abort, fields  # type: ignore
from werkzeug.security import check_password_hash

from ransomlook import ransomlook
from ransomlook.default import get_socket_path, get_homedir, get_config
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
class RecentPost(Resource): # type: ignore[misc]
    def get(self, number: int=100) -> List[str]:
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
class LastPost(Resource): # type: ignore[misc]
    def get(self, number: int=1) -> List[Dict[str, Any]]:
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
class Groups(Resource): # type: ignore[misc]
    def get(self) -> List[str]:
        groups = []
        red = Redis(unix_socket_path=get_socket_path('cache'), db=0)
        for key in red.keys():
            groups.append(key.decode())
        return groups

@api.route('/markets')
@api.doc(description='Return list of markets', tags=['markets'])
class Markets(Resource): # type: ignore[misc]
    def get(self) -> List[str]:
        groups = []
        red = Redis(unix_socket_path=get_socket_path('cache'), db=3)
        for key in red.keys():
            groups.append(key.decode())
        return groups

@api.route('/group/<string:name>')
@api.doc(description='Return info about the group', tags=['groups'])
@api.doc(param={'name':'Name of the group'})
class Groupinfo(Resource): # type: ignore[misc]
   def get(self, name: str) -> List[Any]:
        red = Redis(unix_socket_path=get_socket_path('cache'), db=0)
        group = {}
        sorted_posts:list[Dict[str, Any]] = []
        for key in red.keys():
                if key.decode().lower() == name.lower():
                        group= json.loads(red.get(key)) # type: ignore
                        if group['meta'] is not None:
                            group['meta']=group['meta'].replace('\n', '<br/>')
                        for location in group['locations']:
                            screenfile = '/screenshots/' + name.lower() + '-' + createfile(location['slug']) + '.png'
                            screenpath = os.path.normpath(str(get_homedir()) + '/source' + screenfile)
                            if not screenpath.startswith(str(get_homedir())):
                                raise Exception("not allowed")
                            if os.path.exists(screenpath):
                                with open(screenpath, "rb") as image_file:
                                     screenencoded = base64.b64encode(image_file.read()).decode("ascii")
                                location.update({'screen':screenencoded})
                            source = name.lower() + '-' + striptld(location['slug']) + '.html'
                            sourcepath = os.path.normpath(str(get_homedir()) + '/source/' + source)
                            if not sourcepath.startswith(str(get_homedir())):
                                raise Exception("not allowed")
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
class GroupPost(Resource): # type: ignore[misc]
   def get(self, name: str, postname: str) -> Dict[str, Any]:
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
                            filepath = os.path.normpath(str(get_homedir()) + '/source/' + name + '/' + createfile(postname)+'.html')
                            if not filepath.startswith(str(get_homedir())):
                                raise Exception("not allowed")
                            if os.path.exists(filepath):
                                with open(filepath, "rb") as src_file:
                                     srcencoded = base64.b64encode(src_file.read()).decode("ascii")
                                post.update({'source':srcencoded})

                        return(post)
        return({})

@api.route('/market/<string:name>')
@api.doc(description='Return info about the market', tags=['markets'])
@api.doc(param={'name':'Name of the market'})
class Marketinfo(Resource): # type: ignore[misc]
   def get(self, name: str) -> List[Any]:
        red = Redis(unix_socket_path=get_socket_path('cache'), db=3)
        group = {}
        sorted_posts: List[Dict[str, Any]]  = []
        for key in red.keys():
                if key.decode().lower() == name.lower():
                        group= json.loads(red.get(key)) # type: ignore
                        if group['meta'] is not None:
                            group['meta']=group['meta'].replace('\n', '<br/>')
                        for location in group['locations']:
                            screenfile = '/screenshots/' + name.lower() + '-' + createfile(location['slug']) + '.png'
                            screenpath = os.path.normpath(str(get_homedir()) + '/source' + screenfile)
                            if not screenpath.startswith(str(get_homedir())):
                                raise Exception("not allowed")
                            if os.path.exists(screenpath):
                                with open(screenpath, "rb") as image_file:
                                     screenencoded = base64.b64encode(image_file.read()).decode("ascii")
                                location.update({'screen':screenencoded})
                            source = name.lower() + '-' + striptld(location['slug']) + '.html'
                            sourcepath = os.path.normpath(os.path.join(str(get_homedir()) + '/source/' , source))
                            if not sourcepath.startswith(str(get_homedir())):
                                raise Exception("not allowed")
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
class Exportdb(Resource): # type: ignore[misc]
    def get(self, database: int) -> Any:
        if str(database) not in ['0','2','3','4','5','6']:
            return(['You are not allowed to dump this DataBase'])
        red = Redis(unix_socket_path=get_socket_path('cache'), db=database)
        dump={}
        for key in red.keys():
            dump[key.decode()]=json.loads(red.get(key)) # type: ignore
        return dump

@api.route('/posts/<year>/<month>')
@api.route('/posts/<year>')
@api.doc(description='Dump posts for a month/year', tags=['posts'])
class PostPerMonth(Resource): # type: ignore[misc]
    def get(self, year: int, month: Optional[int]=None) -> List[Dict[str, Any]]:
        posts = []
        if month != None:
            date = str(year)+'-'+str(month)
        else:
            date = str(year)+'-'
        red = Redis(unix_socket_path=get_socket_path('cache'), db=2)
        for key in red.keys():
                entries = json.loads(red.get(key)) # type: ignore
                for entry in entries:
                    if entry['discovered'].startswith(date):
                        entry['group_name']=key.decode()
                        posts.append(entry)
        sorted_posts = sorted(posts, key=lambda x: x['discovered'], reverse=True)
        return sorted_posts

@api.route('/posts/period/<start_date>/<end_date>')
@api.doc(description='Dump posts for a month/year', tags=['posts'])
class PostPerPeriod(Resource): # type: ignore[misc]
    def get(self, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        posts = []
        red = Redis(unix_socket_path=get_socket_path('cache'), db=2)
        for key in red.keys():
                entries = json.loads(red.get(key)) # type: ignore
                for entry in entries:
                    if start_date <= entry['discovered'].split(' ')[0] <= end_date:
                        entry['group_name']=key.decode()
                        posts.append(entry)
        sorted_posts = sorted(posts, key=lambda x: x['discovered'], reverse=True)
        return sorted_posts

@api.route('/graphs/heatmap/<year>/<month>')
@api.route('/graphs/heatmap/<year>')
@api.doc(description='Density heatmap for a month', tags=['posts'])
class DensityHeatmap(Resource): # type: ignore[misc]
    def get(self, year: int, month: Optional[int]=None): # type: ignore[no-untyped-def]
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

        df_sorted = df.groupby(['group_name', 'timestamp']).size().reset_index(name='count') # type: ignore
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
class Scatter(Resource): # type: ignore[misc]
    def get(self, year: int, month: Optional[int]=None): # type: ignore[no-untyped-def]
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

        df_sorted = df.groupby(['group_name', 'timestamp']).size().reset_index(name='count') # type: ignore
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
class Pie(Resource): # type: ignore[misc]
    def get(self, year: int, month: Optional[int]=None): # type: ignore[no-untyped-def]
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

        df_sorted = df.groupby(['group_name', 'timestamp']).size().reset_index(name='count') # type: ignore
        df_sorted = df_sorted.sort_values(by='count', ascending=False)
        df_sorted = df.groupby('group_name').size().reset_index(name='count').sort_values(by='count', ascending=True) # type: ignore[call-overload]
        fig = px.pie(df_sorted, values='count', names='group_name', title='Percentage of total post during the period', width=1050, height=750)
        fig.update_layout(font=dict(family='Roboto'))
        filename = tempfile.TemporaryFile()
        fig.write_image(filename)
        filename.seek(0)
        return send_file(filename, mimetype='image/gif')

@api.route('/graphs/bar/<year>')
@api.route('/graphs/bar/<year>/<month>')
@api.doc(description='Posts per group during the month', tags=['posts'])
class Bar(Resource): # type: ignore[misc]
    def get(self, year: int, month: Optional[int]=None): # type: ignore[no-untyped-def]
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

        df_sorted = df.groupby(['group_name', 'timestamp']).size().reset_index(name='count') # type: ignore[call-overload]
        df_sorted = df_sorted.sort_values(by='count', ascending=False)
        df_sorted = df.groupby('group_name').size().reset_index(name='count').sort_values(by='count', ascending=True) # type: ignore[call-overload]
        fig = px.bar(df_sorted, x='group_name', y='count', color='count', title='Posts per group during the month', color_continuous_scale='Portland',width=1050, height=750)
        fig.update_layout(font=dict(family='Roboto'))
        filename = tempfile.TemporaryFile()
        fig.write_image(filename)
        filename.seek(0)
        return send_file(filename, mimetype='image/gif')

@api.route('/graphs/period/heatmap/<start_date>/<end_date>')
@api.doc(description='Density heatmap for a period', tags=['posts'])
class PeriodDensityHeatmap(Resource): # type: ignore[misc]
    def get(self, start_date: str, end_date: str ): # type: ignore[no-untyped-def]
        group_names = []
        timestamps = []

        red = Redis(unix_socket_path=get_socket_path('cache'), db=2)
        for key in red.keys():
                entries = json.loads(red.get(key)) # type: ignore
                for entry in entries:
                    if start_date <= entry['discovered'].split(' ')[0] <= end_date:
                        group_names.append(key.decode())
                        timestamps.append(entry['discovered'])
        df = pd.DataFrame({'group_name': group_names, 'timestamp': timestamps})
        df['timestamp'] = pd.to_datetime(df['timestamp'])

        df_sorted = df.groupby(['group_name', 'timestamp']).size().reset_index(name='count') # type: ignore
        df_sorted = df_sorted.sort_values(by='count', ascending=False)
        fig = px.density_heatmap(df_sorted, x='timestamp', y='group_name', z='count', title='Posts per group per day (heatmap)', width=1050, height=750)
        fig.update_layout(font=dict(family='Roboto'))
        filename = tempfile.TemporaryFile()
        fig.write_image(filename)
        filename.seek(0)
        return send_file(filename, mimetype='image/gif')

@api.route('/graphs/period/heatmap/<start_date>/<end_date>/<group>')
@api.doc(description='Density heatmap for a period for a group', tags=['posts'])
class PeriodDensityHeatmapGroup(Resource): # type: ignore[misc]
    def get(self, start_date: str, end_date: str, group: str ): # type: ignore[no-untyped-def]
        group_names = []
        timestamps = []

        red = Redis(unix_socket_path=get_socket_path('cache'), db=2)
        entries = json.loads(red.get(group)) # type: ignore
        for entry in entries:
            if start_date <= entry['discovered'].split(' ')[0] <= end_date:
                 group_names.append(group)
                 timestamps.append(entry['discovered'])
        df = pd.DataFrame({'group_name': group_names, 'timestamp': timestamps})
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df_sorted = df.groupby(['group_name', 'timestamp']).size().reset_index(name='count') # type: ignore
        df_sorted = df_sorted.sort_values(by='count', ascending=False)
        fig = px.density_heatmap(df_sorted, x='timestamp', y='group_name', z='count', title='Posts per group per day (heatmap)', width=1050, height=750)
        fig.update_layout(font=dict(family='Roboto'))
        filename = tempfile.TemporaryFile()
        fig.write_image(filename)
        filename.seek(0)
        return send_file(filename, mimetype='image/gif')

@api.route('/graphs/period/scatter/<start_date>/<end_date>')
@api.doc(description='Distribution per days for a period', tags=['posts'])
class PeriodScatter(Resource): # type: ignore[misc]
    def get(self, start_date: str, end_date: str): # type: ignore[no-untyped-def]
        group_names = []
        timestamps = []

        red = Redis(unix_socket_path=get_socket_path('cache'), db=2)
        for key in red.keys():
                entries = json.loads(red.get(key)) # type: ignore
                for entry in entries:
                    if start_date <= entry['discovered'].split(' ')[0] <= end_date:
                        group_names.append(key.decode())
                        timestamps.append(entry['discovered'])
        df = pd.DataFrame({'group_name': group_names, 'timestamp': timestamps})
        df['timestamp'] = pd.to_datetime(df['timestamp'])

        df_sorted = df.groupby(['group_name', 'timestamp']).size().reset_index(name='count') # type: ignore
        df_sorted = df_sorted.sort_values(by='count', ascending=False)
        fig = px.scatter(df_sorted, x='timestamp', y='group_name', color='group_name', title='Distribution per days', color_continuous_scale='Plotly3', width=1050, height=750)
        fig.update_layout(font=dict(family='Roboto'))
        filename = tempfile.TemporaryFile()
        fig.write_image(filename)
        filename.seek(0)
        return send_file(filename, mimetype='image/gif')

@api.route('/graphs/period/scatter/<start_date>/<end_date>/<group>')
@api.doc(description='Distribution per days for a period for a group', tags=['posts'])
class PeriodScatterGroup(Resource): # type: ignore[misc]
    def get(self, start_date: str, end_date: str, group: str): # type: ignore[no-untyped-def]
        group_names = []
        timestamps = []

        red = Redis(unix_socket_path=get_socket_path('cache'), db=2)
        entries = json.loads(red.get(group)) # type: ignore
        for entry in entries:
            if start_date <= entry['discovered'].split(' ')[0] <= end_date:
                group_names.append(group)
                timestamps.append(entry['discovered'])
        df = pd.DataFrame({'group_name': group_names, 'timestamp': timestamps})
        df['timestamp'] = pd.to_datetime(df['timestamp'])

        df_sorted = df.groupby(['group_name', 'timestamp']).size().reset_index(name='count') # type: ignore
        df_sorted = df_sorted.sort_values(by='count', ascending=False)
        fig = px.scatter(df_sorted, x='timestamp', y='group_name', color='group_name', title='Distribution per days', color_continuous_scale='Plotly3', width=1050, height=750)
        fig.update_layout(font=dict(family='Roboto'))
        filename = tempfile.TemporaryFile()
        fig.write_image(filename)
        filename.seek(0)
        return send_file(filename, mimetype='image/gif')

@api.route('/graphs/period/pie/<start_date>/<end_date>')
@api.doc(description='Percentage of total post during the period', tags=['posts'])
class PeriodPie(Resource): # type: ignore[misc]
    def get(self, start_date: str, end_date: str): # type: ignore[no-untyped-def]
        group_names = []
        timestamps = []
        red = Redis(unix_socket_path=get_socket_path('cache'), db=2)
        for key in red.keys():
                entries = json.loads(red.get(key)) # type: ignore
                for entry in entries:
                    if start_date <= entry['discovered'].split(' ')[0] <= end_date:
                        group_names.append(key.decode())
                        timestamps.append(entry['discovered'])
        df = pd.DataFrame({'group_name': group_names, 'timestamp': timestamps})
        df['timestamp'] = pd.to_datetime(df['timestamp'])

        df_sorted = df.groupby(['group_name', 'timestamp']).size().reset_index(name='count') # type: ignore
        df_sorted = df_sorted.sort_values(by='count', ascending=False)
        df_sorted = df.groupby('group_name').size().reset_index(name='count').sort_values(by='count', ascending=True) # type: ignore[call-overload]
        fig = px.pie(df_sorted, values='count', names='group_name', title='Percentage of total post during the period', width=1050, height=750)
        fig.update_layout(font=dict(family='Roboto'))
        filename = tempfile.TemporaryFile()
        fig.write_image(filename)
        filename.seek(0)
        return send_file(filename, mimetype='image/gif')

@api.route('/graphs/period/bar/<start_date>/<end_date>')
@api.doc(description='Posts per group during the period', tags=['posts'])
class PeriodBar(Resource): # type: ignore[misc]
    def get(self, start_date: str, end_date: str): # type: ignore[no-untyped-def]
        group_names = []
        timestamps = []
        red = Redis(unix_socket_path=get_socket_path('cache'), db=2)
        for key in red.keys():
                entries = json.loads(red.get(key)) # type: ignore
                for entry in entries:
                    if start_date <= entry['discovered'].split(' ')[0] <= end_date:
                        group_names.append(key.decode())
                        timestamps.append(entry['discovered'])
        df = pd.DataFrame({'group_name': group_names, 'timestamp': timestamps})
        df['timestamp'] = pd.to_datetime(df['timestamp'])

        df_sorted = df.groupby(['group_name', 'timestamp']).size().reset_index(name='count') # type: ignore
        df_sorted = df_sorted.sort_values(by='count', ascending=False)
        df_sorted = df.groupby('group_name').size().reset_index(name='count').sort_values(by='count', ascending=True) # type: ignore
        fig = px.bar(df_sorted, x='group_name', y='count', color='count', title='Posts per group during the month', color_continuous_scale='Portland',width=1050, height=750)
        fig.update_layout(font=dict(family='Roboto'))
        filename = tempfile.TemporaryFile()
        fig.write_image(filename)
        filename.seek(0)
        return send_file(filename, mimetype='image/gif')

@api.route('/graphs/period/bar/<start_date>/<end_date>/<group>')
@api.doc(description='Posts per group during the period for a group', tags=['posts'])
class PeriodBarGroup(Resource): # type: ignore[misc]
    def get(self, start_date: str, end_date: str, group: str): # type: ignore[no-untyped-def]
        group_names = []
        timestamps = []
        red = Redis(unix_socket_path=get_socket_path('cache'), db=2)
        entries = json.loads(red.get(group)) # type: ignore
        victim_counts: Dict[str, int] = {}
        dates = (Any)
        counts = (Any)

        post_data = json.loads(red.get(group)) # type: ignore
        # Count the number of victims per day
        for post in post_data:
            if start_date <= post['discovered'].split(' ')[0] <= end_date:
                date = post['discovered'].split(' ')[0]
                victim_counts[date] = victim_counts.get(date, 0) + 1 

        # Sort the victim counts by date
        sorted_counts = sorted(victim_counts.items())

        # Extract the dates and counts for plotting
        dates, counts = zip(*sorted_counts)
        # Plot the graph
        plt.clf()
        # Create a new figure and axes for each group with a larger figure size
        px = 1/plt.rcParams['figure.dpi']
        if get_config("generic","darkmode"):
            fig,ax = plt.subplots(figsize=(1050*px, 750*px), facecolor='#272b30')
        else:
            fig,ax = plt.subplots(figsize=(1050*px, 750*px))
        # plt.plot(dates, counts)
        color = '#505d6b'
        if get_config("generic","darkmode"):
            color ='#ddd'
        ax.bar(dates, counts, color = '#6ad37a')
        ax.set_xlabel('New daily discovery when parsing', color = color)
        ax.set_ylabel('Number of Victims', color = color)
        ax.set_title('Number of Victims for Group: ' + group.title(), color = color)
        ax.tick_params(axis='x', bottom=False, labelbottom=False)
        if get_config("generic","darkmode"):
            #ax.set_xtick
            for pos in ['top', 'bottom', 'right', 'left']:
                ax.spines[pos].set_edgecolor(color)
            ax.tick_params(colors=color)
            ax.set_facecolor("#272b30")

        # Set the x-axis limits
        #ax.set_xlim(str(dates[0]), str(dates[-1:]))
        # Format y-axis ticks as whole numbers without a comma separator

        plt.tight_layout()

        filename = tempfile.TemporaryFile()
        plt.savefig(filename)
        filename.seek(0)
        return send_file(filename, mimetype='image/gif')
