#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
🧅 👀 🦅 👹
ransomlook
does what it says on the tin
'''
import os
import json
import queue
from threading import Thread, Lock
from datetime import datetime
from dateutil.relativedelta import relativedelta
import urllib.parse
import time
from typing import Dict, Any, Optional
from redis import Redis
from lacuscore import LacusCore
import libtorrent as lt # type: ignore
import asyncio
import base64

from .default.config import get_config, get_homedir, get_socket_path

import redis
from PIL import Image
from PIL.PngImagePlugin import PngInfo

from .sharedutils import striptld
from .sharedutils import siteschema
from .sharedutils import stdlog, errlog
from .sharedutils import createfile
from .sharedutils import format_bytes

# pylint: disable=W0703

redislacus = Redis(unix_socket_path=get_socket_path('cache'), db=15)
lacus = LacusCore(redislacus,tor_proxy='socks5://127.0.0.1:9050')

def creategroup(location: str) -> Dict[str, object] :
    '''
    create a new group for a new provider - added to groups.json
    '''
    mylocation = siteschema(location)
    insertdata: dict[str, Optional[Any]] = {
        'captcha': bool(),
        'meta': None,
        'locations': [
            mylocation
        ],
        'profile': [],
        'ransomware_galaxy_value': ''
    }
    return insertdata

def checkexisting(provider: str, db: int) -> bool:
    '''
    check if group already exists within groups.json
    '''
    red = redis.Redis(unix_socket_path=get_socket_path('cache'), db=db)
    if provider.encode() in red.keys():
        return True
    return False

async def run_captures() -> None: 
    max_captures_to_consume = get_config('generic','thread')
    captures = set()
    for capture_task in lacus.consume_queue(max_captures_to_consume):
        captures.add(capture_task)  # adds the task to the set
        capture_task.add_done_callback(captures.discard)  # remove the task from the set when done

    await asyncio.gather(*captures)  # wait for all tasks to complete

def scraper(base: int) -> None:
    '''main scraping function'''
    red = redis.Redis(unix_socket_path=get_socket_path('cache'), db=base)
    groups=[]
    uuids=[]
    validationDate = datetime.now() - relativedelta(months=6)
    for key in red.keys():
        group = json.loads(red.get(key)) # type: ignore
        group['name'] = key.decode()
        groups.append(group)
    for group in groups:
        stdlog('ransomloook: ' + 'working on ' + group['name'])
        # iterate each location/mirror/relay
        for host in group['locations']:
            try :
                if (not datetime.strptime(host['updated'], '%Y-%m-%d %H:%M:%S.%f') > validationDate) :
                    print('Skipping '+ host['fqdn'])
                    continue
            except:
                print('Error with : '+ host['slug'])
                continue
            uuid = lacus.enqueue(url=host['slug'])
            host.update({'uuid':uuid})
            uuids.append(uuid)
    asyncio.run(run_captures())
    while uuids:
        for group in groups:
            for host in group['locations']:
                if 'uuid' in host:
                    if lacus.get_capture_status(host['uuid']) == -1:
                        uuids.remove(uuid)
                        name=group['name']
                        del host['uuid']
                        del group['name']
                        host.update({'available':False})
                        red.set(name, json.dumps(group))
                        group['name']=name
                    if lacus.get_capture_status(host['uuid']) == 1:
                        result = lacus.get_capture(host['uuid'])
                        uuids.remove(host['uuid'])
                        del host['uuid']
                        if result['status']=='error': # type: ignore
                            host.update({'available':False})
                            name=group['name']
                            del group['name']
                            red.set(name, json.dumps(group))
                            group['name']=name
                            red.set(group['name'], json.dumps(host))
                            continue
                        if 'png' in result:
                            filename = group['name'] + '-' + createfile(host['slug']) + '.png'
                            name = os.path.join(get_homedir(), 'source/screenshots', filename)
                            with open(name, 'wb') as tosave:
                                tosave.write(base64.b64decode(result['png'])) # type: ignore
                            targetImage = Image.open(name)
                            metadata = PngInfo()
                            metadata.add_text("Source", "RansomLook.io")
                            targetImage.save(name, pnginfo=metadata)

                        if 'html' in result:
                            filename = group['name'] + '-' + striptld(host['slug']) + '.html'
                            name = os.path.join(os.getcwd(), 'source', filename)
                            with open(name, 'w') as tosave:
                                tosave.write(result['html']) # type: ignore
                        if 'har' in result:
                            out = False
                            for entry in result['har']['log']['entries']: # type: ignore
                                if entry['response']['status'] == -1:
                                    host.update({'available':False})
                                    name= group['name']
                                    del group['name']
                                    red.set(name, json.dumps(group))
                                    group['name']=name
                                    out = True
                            if not out:
                                host.update({'available':True, 'title':result['har']['log']['pages'][0]['title'], # type: ignore
                                     'lastscrape':result['har']['log']['pages'][0]['startedDateTime'].replace('T',' ').replace('Z',''), # type: ignore
                                     'updated':result['har']['log']['pages'][0]['startedDateTime'].replace('T',' ').replace('Z','')}) # type: ignore
                        else:
                            host.update({'available':False})
                        name= group['name']
                        del group['name']
                        red.set(name, json.dumps(group))
                        group['name']=name

        asyncio.run(run_captures())


def adder(name: str, location: str, db: int) -> int:
    '''
    handles the addition of new providers to groups.json
    '''
    if checkexisting(name.strip(), db):
        stdlog('ransomlook: ' + 'records for ' + name + \
            ' already exist, appending to avoid duplication')
        return appender(name.strip(), location.strip(), db)
    else:
        red = redis.Redis(unix_socket_path=get_socket_path('cache'), db=db)
        newrec = creategroup(location.strip())
        red.set(name.strip(), json.dumps(newrec))
        stdlog('ransomlook: ' + 'record for ' + name + ' added to groups.json')
        return 0

def appender(name: str, location: str, db: int) -> int:
    '''
    handles the addition of new mirrors and relays for the same site
    to an existing group within groups.json
    '''
    red = redis.Redis(unix_socket_path=get_socket_path('cache'), db=db)
    group = json.loads(red.get(name.strip())) # type: ignore
    success = bool()
    for loc in group['locations']:
        if location == loc['slug']:
            errlog('cannot append to non-existing provider or the location already exists')
            return 2
    group['locations'].append(siteschema(location))
    red.set(name.strip(), json.dumps(group))
    return 1

def screen() -> None:
    red = redis.Redis(unix_socket_path=get_socket_path('cache'), db=1)
    if 'toscan'.encode() not in red.keys():
        stdlog('No screen to do !')
        return
    redgroup = redis.Redis(unix_socket_path=get_socket_path('cache'), db=0)
    captures = json.loads(red.get('toscan')) # type: ignore
    uuids = []
    slugs = []
    for capture in captures:
        group = json.loads(redgroup.get(capture['group'].encode())) # type: ignore
        for host in group['locations']:
            if capture['slug'].removeprefix(capture['group']+'-').split('.')[0] in striptld(host['slug']):
                capture.update({'slug2' : urllib.parse.urljoin(host['slug'], str(capture['link']))})
                if capture['slug2'] not in slugs:
                   slugs.append(capture['slug2'])
                   uuid = lacus.enqueue(url=capture['slug2'])
                   capture.update({'uuid':uuid})
                   uuids.append(uuid)

    asyncio.run(run_captures())
    while uuids:
        for capture in captures:
            if 'uuid' in capture:
                if lacus.get_capture_status(capture['uuid']) == -1:
                    uuids.remove(capture['uuid'])
                    del capture['uuid']
                    continue

                if lacus.get_capture_status(capture['uuid']) == 1:
                        result = lacus.get_capture(capture['uuid'])
                        uuids.remove(capture['uuid'])
                        del capture['uuid']

                        if result['status']=='error' or 'error' in result: # type: ignore
                            red.set('toscan', json.dumps(captures))
                            continue
                        if 'png' in result and 'html' in result:
                            filenamepng = createfile(capture['title']) + '.png'
                            path = os.path.join(get_homedir(), 'source/screenshots', capture['group'])
                            if not os.path.exists(path):
                                os.mkdir(path)
                            namepng = os.path.join(path, filenamepng)
                            print(namepng)
                            with open(namepng, 'wb') as tosave:
                                tosave.write(base64.b64decode(result['png'])) # type: ignore
                            targetImage = Image.open(namepng)
                            metadata = PngInfo()
                            metadata.add_text("Source", "RansomLook.io")
                            targetImage.save(namepng, pnginfo=metadata)

                            filename = createfile(capture['title']) + '.html'
                            path = os.path.join(get_homedir(), 'source/', capture['group'])
                            if not os.path.exists(path):
                                os.mkdir(path)
                            name = os.path.join(path, filename)
                            with open(name, 'w') as tosave:
                                tosave.write(result['html']) # type: ignore
                            redpost = redis.Redis(unix_socket_path=get_socket_path('cache'), db=2)
                            updated = json.loads(redpost.get(capture['group'])) # type: ignore
                            for post in updated:
                                if post['post_title'] == capture['title']:
                                    post['screen'] = str(os.path.join('screenshots', capture['group'], filenamepng))
                                    post.update(post)
                            redpost.set(capture['group'], json.dumps(updated))
                            toscreen = json.loads(red.get('toscan')) # type: ignore
                            for idx, item in enumerate(toscreen):
                                if item['group'] == capture['group'] and item['title'] == capture['title']:
                                    toscreen.pop(idx)
                                    break
                            red.set('toscan', json.dumps(toscreen))
        asyncio.run(run_captures())

def threadtorrent(queuethread, lock) -> None: # type: ignore[no-untyped-def]
    while True:
        sess, torrent = queuethread.get()
        print(torrent)
        atp = lt.parse_magnet_uri(torrent['magnet'])
        atp.save_path = "."
        atp.flags = lt.torrent_flags.upload_mode
        torr = sess.add_torrent(atp)
        while not torr.status().has_metadata:
            time.sleep(1)
        torr.pause()
        tinf = torr.torrent_file()
        # Workaround for empty torrent_info.trackers() in
        # libtorrent-rasterbar-2.0.7:
        trn = 0
        for t in tinf.trackers(): trn += 1
        if trn == 0:
            for t in atp.trackers:
                tinf.add_tracker(t)
        files = ""
        for x in range(tinf.files().num_files()):
            files += format_bytes(tinf.files().file_size(x)) + '    ' + tinf.files().file_path(x) + '\n'
        filename = createfile(torrent['title']) + '.txt'
        path = os.path.join(get_homedir(), 'source/screenshots', torrent['group'])
        if not os.path.exists(path):
            os.mkdir(path)
        name = os.path.join(path, filename)
        with open(name, 'w', encoding='utf-8') as listing:
            listing.write(files)
            listing.close()

        # Saving torrent file
        path = os.path.join(get_homedir(), 'source/', torrent['group'])
        if not os.path.exists(path):
            os.mkdir(path)
        filetorrent = createfile(torrent['title']) + '.torrent'
        nametorrent = os.path.join(path, filetorrent)
        f = open(nametorrent, "wb")
        f.write(lt.bencode(lt.create_torrent(tinf).generate()))
        f.close()

        red = redis.Redis(unix_socket_path=get_socket_path('cache'), db=2)
        updated = json.loads(red.get(torrent['group'])) # type: ignore
        for post in updated:
            if post['post_title'] == torrent['title']:
                post['screen'] = str(os.path.join('screenshots', torrent['group'], filename))
                post.update(post)
        red.set(torrent['group'], json.dumps(updated))
        red = redis.Redis(unix_socket_path=get_socket_path('cache'), db=1)
        totorrent = json.loads(red.get('totorrent')) # type: ignore
        for idx, item in enumerate(totorrent):
            if item['group'] == torrent['group'] and item['title'] == torrent['title']:
                totorrent.pop(idx)
                break
        red.set('totorrent', json.dumps(totorrent))
        print('Done with: ' + torrent['title'])
        sess.remove_torrent(torr)
        queuethread.task_done()

def gettorrentinfo() -> None :
    red = redis.Redis(unix_socket_path=get_socket_path('cache'), db=1)
    if 'totorrent'.encode() not in red.keys():
        stdlog('No torrent to get !')
        return
    sess = lt.session()
    lock = Lock()
    queuethread = queue.Queue() # type: ignore
    for _ in range(get_config('generic','thread')):
        t = Thread(target=threadtorrent, args=(queuethread,lock), daemon=True)
        t.start()

    torrents = json.loads(red.get('totorrent')) # type: ignore
    for torrent in torrents:
        data = [sess,torrent]
        queuethread.put(data)
    queuethread.join()
    time.sleep(5)
