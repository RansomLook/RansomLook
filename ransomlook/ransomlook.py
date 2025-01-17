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
from pylacus import PyLacus
from pylacus import CaptureSettings
from lacuscore import LacusCore
import libtorrent as lt # type: ignore
import asyncio
import base64

from .default.config import get_config, get_homedir, get_socket_path

import valkey #type: ignore
from PIL import Image
from PIL.PngImagePlugin import PngInfo

from .sharedutils import striptld
from .sharedutils import siteschema
from .sharedutils import stdlog, errlog
from .sharedutils import createfile
from .sharedutils import format_bytes

# pylint: disable=W0703

valkeylacus = valkey.Valkey(unix_socket_path=get_socket_path('cache'), db=15)
lacus = LacusCore(valkeylacus,tor_proxy='socks5://127.0.0.1:9050')

def creategroup(location: str, fs: bool, private: bool, chat: bool, admin: bool, browser: str|None) -> Dict[str, object] :
    '''
    create a new group for a new provider - added to groups.json
    '''
    mylocation = siteschema(location, fs, private, chat, admin, browser)
    insertdata: dict[str, Optional[Any]] = {
        'captcha': bool(),
        'meta': None,
        'locations': [
            mylocation
        ] if location != '' else [],
        'profile': [],
        'ransomware_galaxy_value': ''
    }
    return insertdata

def checkexisting(provider: str, db: int) -> bool:
    '''
    check if group already exists within groups.json
    '''
    valkey_handle = valkey.Valkey(unix_socket_path=get_socket_path('cache'), db=db)
    if provider.encode() in valkey_handle.keys():
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
    valkey_handle = valkey.Valkey(unix_socket_path=get_socket_path('cache'), db=base)
    groups=[]
    running_capture = {}
    validationDate = datetime.now() - relativedelta(months=6)
    remote_lacus_url = None
    if get_config('generic', 'remote_lacus'):
        remote_lacus_config = get_config('generic', 'remote_lacus')
        if remote_lacus_config.get('enable'):
            remote_lacus_url = remote_lacus_config.get('url')
            lacus = PyLacus(remote_lacus_url)
            try:
                lacus.status()
            except:
                print('using local lacuscore')
                remote_lacus_url = None

    if not remote_lacus_url:
        lacus = LacusCore(valkeylacus,tor_proxy='socks5://127.0.0.1:9050') 

    for key in valkey_handle.keys():
        group = json.loads(valkey_handle.get(key)) 
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
            settings: CaptureSettings = {'url': host['slug'],
                        'general_timeout_in_sec':90,
                        'max_retries':1
                       }
            if 'header' in host:
                settings['headers']=host['header']
            if 'browser' in host and host['browser'] is not None:
                settings['browser']=host['browser']

            uuid = lacus.enqueue(settings = settings)
            running_capture[uuid]={'group':group['name'],'slug':host['slug']}
    if not remote_lacus_url:
        asyncio.run(run_captures())
    while running_capture:
        for key in list(running_capture): # type: ignore
            if lacus.get_capture_status(str(key)) == -1:
                group = json.loads(valkey_handle.get(running_capture[str(key)]['group'])) 
                for location in group['locations']:
                    if location['slug']==running_capture[str(key)]['slug']:
                        location.update({'available':False})
                        valkey_handle.set(running_capture[str(key)]['group'], json.dumps(group))
                        break
                running_capture.pop(str(key))
                continue
            if lacus.get_capture_status(str(key)) == 1:
                result = lacus.get_capture(str(key))
                name = str(running_capture[str(key)]['group'])
                group = json.loads(valkey_handle.get(name)) 
                for location in group['locations']:
                    if location['slug']==running_capture[str(key)]['slug']:
                        host=location
                        continue
                if result['status']=='error': # type: ignore
                    host.update({'available':False})
                    running_capture.pop(str(key))
                    valkey_handle.set(name, json.dumps(group))
                    continue
                if 'png' in result and not ('fixedfile' in host and host['fixedfile'] is True):
                    filename = name + '-' + createfile(host['slug']) + '.png'
                    namefile = os.path.join(get_homedir(), 'source/screenshots', filename)
                    with open(namefile, 'wb') as tosave:
                        if remote_lacus_url:
                            tosave.write((result['png'])) # type: ignore
                        else:
                            tosave.write(base64.b64decode(result['png'])) # type: ignore
                    targetImage = Image.open(namefile)
                    metadata = PngInfo()
                    metadata.add_text("Source", "RansomLook.io")
                    targetImage.save(namefile, pnginfo=metadata)
                    if get_config('generic', 'keepall'):
                        nowpng = datetime.now()
                        timestamp = nowpng.strftime("%Y-%m-%d_%H-%M-%S")
                        filename =  timestamp + '-' + createfile(host['slug']) + '.png'
                        folder = os.path.join(get_homedir(), 'source/screenshots/old', name)
                        if not os.path.exists(folder):
                            os.makedirs(folder)
                        file_path = os.path.join(folder, filename)
                        with open(file_path, 'wb') as tosave:
                            if remote_lacus_url:
                                tosave.write((result['png'])) # type: ignore
                            else:
                                tosave.write(base64.b64decode(result['png'])) # type: ignore

                if 'html' in result:
                    filename = name + '-' + striptld(host['slug']) + '.html'
                    namefile = os.path.join(os.getcwd(), 'source', filename)
                    with open(namefile, 'w') as tosave:
                        tosave.write(result['html']) # type: ignore
                    host.update({'available':True, 'title':result['har']['log']['pages'][0]['title'], # type: ignore
                             'lastscrape':result['har']['log']['pages'][0]['startedDateTime'].replace('T',' ').replace('Z',''), # type: ignore
                             'updated':result['har']['log']['pages'][0]['startedDateTime'].replace('T',' ').replace('Z','')}) # type: ignore

                else:
                    host.update({'available':False})
                valkey_handle.set(name, json.dumps(group))
                running_capture.pop(str(key))

        if not remote_lacus_url:
            asyncio.run(run_captures())
        else:
            time.sleep(10)

def adder(name: str, location: str, db: int, fs: bool=False, private: bool=False, chat: bool=False, admin: bool=False, browser: str|None=None) -> int:
    '''
    handles the addition of new providers to groups.json
    '''
    if checkexisting(name.strip(), db):
        stdlog('ransomlook: ' + 'records for ' + name + \
            ' already exist, appending to avoid duplication')
        if location.strip() != "":
            return appender(name.strip(), location.strip(), db, fs, private, chat, admin, browser)
        return 0
    else:
        valkey_handle = valkey.Valkey(unix_socket_path=get_socket_path('cache'), db=db)
        newrec = creategroup(location.strip(), fs, private, chat, admin, browser)
        valkey_handle.set(name.strip(), json.dumps(newrec))
        stdlog('ransomlook: ' + 'record for ' + name + ' added to groups.json')
        return 0

def appender(name: str, location: str, db: int, fs: bool, private: bool, chat: bool, admin: bool, browser: str|None) -> int:
    '''
    handles the addition of new mirrors and relays for the same site
    to an existing group within groups.json
    '''
    valkey_handle = valkey.Valkey(unix_socket_path=get_socket_path('cache'), db=db)
    group = json.loads(valkey_handle.get(name.strip())) 
    success = bool()
    for loc in group['locations']:
        if location == loc['slug']:
            errlog('cannot append to non-existing provider or the location already exists')
            return 2
    group['locations'].append(siteschema(location, fs, private, chat, admin, browser))
    valkey_handle.set(name.strip(), json.dumps(group))
    return 1

def screen() -> None:
    valkey_handle = valkey.Valkey(unix_socket_path=get_socket_path('cache'), db=1)
    if 'toscan'.encode() not in valkey_handle.keys():
        stdlog('No screen to do !')
        return
    valkey_group_handle = valkey.Valkey(unix_socket_path=get_socket_path('cache'), db=0)
    captures = json.loads(valkey_handle.get('toscan')) 
    remote_lacus_url = None
    if get_config('generic', 'remote_lacus'):
        remote_lacus_config = get_config('generic', 'remote_lacus')
        if remote_lacus_config.get('enable'):
            remote_lacus_url = remote_lacus_config.get('url')
            lacus = PyLacus(remote_lacus_url)
            try:
                lacus.status()
            except:
                print('using local lacuscore')
                remote_lacus_url = None

    if not remote_lacus_url:
        lacus = LacusCore(valkeylacus,tor_proxy='socks5://127.0.0.1:9050') 

    uuids = []
    slugs = []
    for capture in captures:
        group = json.loads(valkey_group_handle.get(capture['group'].encode())) 
        for host in group['locations']:
          try:
            if capture['slug'].removeprefix(capture['group']+'-').split('.')[0] in striptld(host['slug']):
                capture.update({'slug2' : urllib.parse.urljoin(host['slug'], str(capture['link']))})
                if capture['slug2'] not in slugs:
                   slugs.append(capture['slug2'])
                   settings: CaptureSettings = {'url': capture['slug2'],
                        'general_timeout_in_sec':90,
                        'max_retries':1
                       }
                   if 'header' in host:
                       settings['headers']=host['header']
                   if 'browser' in host and host['browser'] is not None:
                       settings['browser']=host['browser']

                   uuid = lacus.enqueue(settings=settings)
                   capture.update({'uuid':uuid})
                   uuids.append(uuid)
          except:
            print(capture['group'].encode())
            print(capture['slug'])

    if not remote_lacus_url:
        asyncio.run(run_captures())
    print(uuids)
    while uuids:
        for capture in captures:
            if 'uuid' in capture:
                if lacus.get_capture_status(capture['uuid']) == -1:
                    uuids.remove(capture['uuid'])
                    del capture['uuid']
                    continue
                if lacus.get_capture_status(capture['uuid']) == 1:
                        time.sleep(1)
                        print(capture['uuid'])
                        result = lacus.get_capture(capture['uuid'])
                        print(result['status'])
                        uuids.remove(capture['uuid'])
                        del capture['uuid']

                        if result['status']=='error' or 'error' in result: 
                            valkey_handle.set('toscan', json.dumps(captures))
                            continue
                        if 'png' in result and 'html' in result:
                            filenamepng = createfile(capture['title']) + '.png'
                            path = os.path.join(get_homedir(), 'source/screenshots', capture['group'])
                            if not os.path.exists(path):
                                os.mkdir(path)
                            namepng = os.path.join(path, filenamepng)
                            print(namepng)
                            with open(namepng, 'wb') as tosave:
                                if remote_lacus_url:
                                    tosave.write((result['png'])) # type: ignore
                                else:
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
                            valkey_post_handle = valkey.Valkey(unix_socket_path=get_socket_path('cache'), db=2)
                            updated = json.loads(valkey_post_handle.get(capture['group'])) 
                            for post in updated:
                                if post['post_title'] == capture['title']:
                                    post['screen'] = str(os.path.join('screenshots', capture['group'], filenamepng))
                                    post.update(post)
                            valkey_post_handle.set(capture['group'], json.dumps(updated))
                            toscreen = json.loads(valkey_handle.get('toscan')) 
                            for idx, item in enumerate(toscreen):
                                if item['group'] == capture['group'] and item['title'] == capture['title']:
                                    toscreen.pop(idx)
                                    break
                            valkey_handle.set('toscan', json.dumps(toscreen))
        if not remote_lacus_url:
            asyncio.run(run_captures())
        else:
            time.sleep(10)

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

        valkey_handle = valkey.Valkey(unix_socket_path=get_socket_path('cache'), db=2)
        updated = json.loads(valkey_handle.get(torrent['group'])) 
        for post in updated:
            if post['post_title'] == torrent['title']:
                post['screen'] = str(os.path.join('screenshots', torrent['group'], filename))
                post.update(post)
        valkey_handle.set(torrent['group'], json.dumps(updated))
        valkey_handle = valkey.Valkey(unix_socket_path=get_socket_path('cache'), db=1)
        totorrent = json.loads(valkey_handle.get('totorrent')) 
        for idx, item in enumerate(totorrent):
            if item['group'] == torrent['group'] and item['title'] == torrent['title']:
                totorrent.pop(idx)
                break
        valkey_handle.set('totorrent', json.dumps(totorrent))
        print('Done with: ' + torrent['title'])
        sess.remove_torrent(torr)
        queuethread.task_done()

def gettorrentinfo() -> None :
    valkey_handle = valkey.Valkey(unix_socket_path=get_socket_path('cache'), db=1)
    if 'totorrent'.encode() not in valkey_handle.keys():
        stdlog('No torrent to get !')
        return
    sess = lt.session()
    lock = Lock()
    queuethread = queue.Queue() # type: ignore
    for _ in range(get_config('generic','thread')):
        t = Thread(target=threadtorrent, args=(queuethread,lock), daemon=True)
        t.start()

    torrents = json.loads(valkey_handle.get('totorrent')) 
    for torrent in torrents:
        data = [sess,torrent]
        queuethread.put(data)
    queuethread.join()
    time.sleep(5)
