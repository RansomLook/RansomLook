#!/usr/bin/env python3
#from ransomlook import ransomlook
import importlib
from os.path import dirname, basename, isfile, join
import json
import glob
import sys



import redis

from ransomlook.default.config import get_socket_path

from ransomlook.sharedutils import dbglog, stdlog, errlog

from typing import Dict, Optional

def posttemplate(victim: str, description: str, link: str, timestamp: str) -> Dict[str, Optional[str]]:
    '''
    assuming we have a new post - form the template we will use for the new entry in posts.json
    '''
    schema = {
        'post_title': victim,
        'discovered': timestamp,
        'description' : description,
        'link' : link,
        'screen' : None
    }
    stdlog('new post: ' + victim)
    dbglog(schema)
    return schema

def appender(entry, group_name: str) -> None: # type: ignore
    '''
    append a new post to posts.json
    '''
    if type(entry) is str :
       post_title = entry
       link = ''
    else :
       post_title=entry['title']
       entry['description']
       if 'link' in entry:
           link = entry['link']
       else:
           link = None
       if 'magnet' in entry:
           magnet = entry['magnet']
       else:
           magnet = None
    if len(post_title) == 0:
        errlog('post_title is empty')
        return
    # limit length of post_title to 90 chars
    if len(post_title) > 90:
        post_title = post_title[:90]
 
    if link is not None and link != '':
        screenred = redis.Redis(unix_socket_path=get_socket_path('cache'), db=1)
        if 'toscan'.encode() not in screenred.keys():
           toscan=[]
        else: 
           toscan = json.loads(screenred.get('toscan')) # type: ignore
        toscan.append({'group': group_name, 'title': entry['title'], 'slug': entry['slug'], 'link': entry['link']})
        screenred.set('toscan', json.dumps(toscan))
    # preparing to torrent
    if magnet is not None and magnet != '':
        torrentred = redis.Redis(unix_socket_path=get_socket_path('cache'), db=1)
        if 'totorrent'.encode() not in torrentred.keys():
           totorrent=[]
        else: 
           totorrent = json.loads(torrentred.get('totorrent')) # type: ignore
        totorrent.append({'group': group_name, 'title': entry['title'], 'magnet': entry['magnet']})
        torrentred.set('totorrent', json.dumps(totorrent))

def main() -> None:
    if len(sys.argv) != 2:
        modules = glob.glob(join(dirname('ransomlook/parsers/'), "*.py"))
        __all__ = [ basename(f)[:-3] for f in modules if isfile(f) and not f.endswith('__init__.py')]
    else:
        __all__ = [sys.argv[1]]
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

