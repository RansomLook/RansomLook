#!/usr/bin/env python3
#from ransomlook import ransomlook
import importlib
from os.path import dirname, basename, isfile, join
import glob
import json

from datetime import datetime
from datetime import timedelta

import collections

import redis
import uuid

from ransomlook.default.config import get_config, get_socket_path
from ransomlook.rocket import rocketnotify
from ransomlook.twitter import twitternotify
from ransomlook.misp import mispevent
from ransomlook.email import alertingnotify

from ransomlook.sharedutils import dbglog, stdlog, errlog

def posttemplate(victim, description, timestamp):
    '''
    assuming we have a new post - form the template we will use for the new entry in posts.json
    '''
    schema = {
        'post_title': victim,
        'discovered': timestamp,
        'description' : description
    }
    stdlog('new post: ' + victim)
    dbglog(schema)
    return schema

def appender(entry, group_name):
    '''
    append a new post to posts.json
    '''
    rocketconfig = get_config('generic','rocketchat')
    twitterconfig = get_config('generic','twitter')
    mispconfig = get_config('generic','misp')
    emailconfig = get_config('generic', 'email')
    if type(entry) is str :
       post_title = entry
       description = ''
    else :
       post_title=entry['title']
       description = entry['description']
    if len(post_title) == 0:
        errlog('post_title is empty')
        return
    # limit length of post_title to 90 chars
    if len(post_title) > 90:
        post_title = post_title[:90]
    red = redis.Redis(unix_socket_path=get_socket_path('cache'), db=2)
    keys = red.keys()
    posts=[]

    if group_name.encode() in red.keys():
        posts = json.loads(red.get(group_name)) # type: ignore
        for post in posts:
            if post['post_title'] == post_title:
                stdlog('post already existing')
                print(post)
                return
    newpost = posttemplate(post_title, description, str(datetime.today()))
    stdlog('adding new post: ' + 'group: ' + group_name + ' title: ' + post_title)
    posts.append(newpost)
    red.set(group_name, json.dumps(posts))

    # Notification zone
    red = redis.Redis(unix_socket_path=get_socket_path('cache'), db=1)
    keywords = red.get('keywords')
    matching = []
    if keywords is not None:
        listkeywords = keywords.decode().splitlines()
        for keyword in listkeywords:
             if keyword.lower() in post_title.lower() or keyword.lower() in description.lower():
                 matching.append(keyword)
        if matching:
            alertingnotify(emailconfig, group_name, post_title, description, matching)
            alertdb = redis.Redis(unix_socket_path=get_socket_path('cache'), db=12)
            uuidkey = str(uuid.uuid4())
            value = {'type': 'group', 'group_name': group_name, 'post_title': post_title, 'description': description, 'matching': matching}
            alertdb.set(uuidkey,json.dumps(value))
            alertdb.expire(uuidkey, 60 * 60 * 24)

    if rocketconfig['enable'] == True:
        rocketnotify(rocketconfig, group_name, post_title, description)
    if twitterconfig['enable'] == True:
        twitternotify(twitterconfig, group_name, post_title)
    if mispconfig['enable'] == True:
        try:
            groupred = redis.Redis(unix_socket_path=get_socket_path('cache'), db=0)
            for key in groupred.keys():
                if key.decode() == group_name:
                       groupinfo = json.loads(groupred.get(key)) # type: ignore
            galaxyname = groupinfo['ransomware_galaxy_value']
        except:
            galaxyname = None
        mispevent(mispconfig, group_name, post_title, description, galaxyname)

def main():
    modules = glob.glob(join(dirname('ransomlook/parsers/'), "*.py"))
    __all__ = [ basename(f)[:-3] for f in modules if isfile(f) and not f.endswith('__init__.py')]
    for parser in __all__:
        module = importlib.import_module(f'ransomlook.parsers.{parser}')
        print('\nParser : '+parser)

        try:
            for entry in module.main():
                appender(entry, parser)
        except Exception as e:
            print("Error with : " + parser)
            print(e)
            pass


if __name__ == '__main__':
    main()

