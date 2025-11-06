#!/usr/bin/env python3

import base64
import json
from typing import Any, Dict, Optional, List
from redis import Redis

from flask import request
from flask_restx import Namespace, Resource  # type: ignore

from ransomlook.default import get_socket_path, get_homedir
from ransomlook.sharedutils import createfile, striptld

import os

from datetime import timezone
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
                    try:
                        datetime_object = datetime.strptime(entry['discovered'], '%Y-%m-%d %H:%M:%S.%f')
                    except:
                        datetime_object = datetime.strptime(entry['discovered'], '%Y-%m-%d %H:%M:%S')
                    if datetime_object > actualdate:
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
            group= json.loads(red.get(key)) # type: ignore
            if 'private' in group and group['private'] is True:
                  continue
            groups.append(key.decode())
        return groups

@api.route('/markets')
@api.doc(description='Return list of markets', tags=['markets'])
class Markets(Resource): # type: ignore[misc]
    def get(self) -> List[str]:
        groups = []
        red = Redis(unix_socket_path=get_socket_path('cache'), db=3)
        for key in red.keys():
            group= json.loads(red.get(key)) # type: ignore
            if 'private' in group and group['private'] is True:
                  continue
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
                        if 'private' in group and group['private'] is True:
                           return [[],{}]

                        if group['meta'] is not None:
                            group['meta']=group['meta'].replace('\n', '<br/>')
                        group['locations'] = [location for location in group['locations'] if not ('private' in location and location['private'] is True)]
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
                        if 'screen' in post and post['screen'] is not None :
                            screenpath = str(get_homedir()) + '/source/' + post['screen']
                            if os.path.exists(screenpath):
                                with open(screenpath, "rb") as image_file:
                                     screenencoded = base64.b64encode(image_file.read()).decode("ascii")
                                post.update({'screen':screenencoded})
                        if 'link' in post and post['link'] is not None :
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
                        if 'private' in group and group['private'] is True:
                           return [[],{}]
                        if group['meta'] is not None:
                            group['meta']=group['meta'].replace('\n', '<br/>')
                        group['locations'] = [location for location in group['locations'] if not ('private' in location and location['private'] is True)]
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
            if str(database) != '0' and str(database) != '3':
                dump[key.decode()]=json.loads(red.get(key)) # type: ignore
            else:
                temp = json.loads(red.get(key)) # type: ignore
                if 'private' in temp and temp['private'] is True:
                    continue
                if 'locations' in temp:
                    temp['locations'] = [location for location in temp['locations'] if not ('private' in location and location['private'] is True)]
                dump[key.decode()]=temp
        return dump


# Utils de temps
def _parse_iso_maybe_z(s: str) -> datetime | None:
    """Parse ISO 8601, accepte ...Z et avec offset. Renvoie un datetime timezone-aware en UTC."""
    if not s:
        return None
    try:
        # remplace 'Z' par +00:00 pour fromisoformat
        if s.endswith('Z'):
            s = s[:-1] + '+00:00'
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            # on considère UTC si pas d’info de TZ
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None

def _date_only_to_utc_start(day: str) -> datetime:
    # YYYY-MM-DD -> 00:00:00Z
    return datetime.fromisoformat(day).replace(tzinfo=timezone.utc)

def _date_only_to_utc_end(day: str) -> datetime:
    # YYYY-MM-DD -> 23:59:59.999999Z
    d = datetime.fromisoformat(day).replace(tzinfo=timezone.utc)
    return d.replace(hour=23, minute=59, second=59, microsecond=999999)

@api.route('/posts')
@api.doc(description='Return raw posts (group_name, discovered) for client-side stats', tags=['stats'])
class Posts(Resource):  # type: ignore[misc]
    @api.doc(params={
        'days': 'Relative period in days (e.g. 7, 14, 30, 90). Ignored if "from" and "to" are provided.',
        'from': 'Start date (YYYY-MM-DD) UTC (inclusive).',
        'to':   'End date (YYYY-MM-DD) UTC (inclusive).',
        'groups': 'Comma-separated group names to include (optional).'
    })
    def get(self) -> dict:
        # --- Time window ---
        now = datetime.now(timezone.utc)
        days = request.args.get('days', type=int)
        from_s = request.args.get('from')
        to_s   = request.args.get('to')

        if from_s and to_s:
            try:
                start = _date_only_to_utc_start(from_s)
                end   = _date_only_to_utc_end(to_s)
            except Exception:
                # fallback si mauvais format -> dernière 30j
                start = now - timedelta(days=30)
                end   = now
        else:
            if not days:
                days = 30
            start = now - timedelta(days=days)
            end   = now

        # --- Optional group filter ---
        groups_param = request.args.get('groups', '') or ''
        groups_wanted = set([g.strip() for g in groups_param.split(',') if g.strip()]) if groups_param else None

        # --- Read Redis db=2 as in your script ---
        red = Redis(unix_socket_path=get_socket_path('cache'), db=2)

        out: list[dict] = []
        for key in red.keys():
            group_name = key.decode()
            if groups_wanted and group_name not in groups_wanted:
                continue

            raw = red.get(key)
            if not raw:
                continue

            try:
                posts = json.loads(raw)
            except Exception:
                continue

            for p in posts:
                ts_s = p.get('discovered')
                dt = _parse_iso_maybe_z(ts_s)
                if not dt:
                    continue
                if start <= dt <= end:
                    out.append({
                        "group_name": group_name,
                        "discovered": dt.isoformat().replace('+00:00','Z')  # propre ISO en Z
                    })

        # On peut trier par date pour plus de cohérence (optionnel)
        out.sort(key=lambda r: r['discovered'])

        return {"posts": out}

@api.route('/posts/<year>/<month>')
@api.route('/posts/<year>')
@api.doc(description='Dump posts for a month/year', tags=['posts'])
class PostPerMonth(Resource): # type: ignore[misc]
    def get(self, year: int, month: Optional[int]=None) -> List[Dict[str, Any]]:
        posts = []
        if month is not None:
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
