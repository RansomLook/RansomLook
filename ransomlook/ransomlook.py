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
import urllib.parse
import time
from typing import Dict
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

import libtorrent as lt # type: ignore

from .default.config import get_config, get_homedir, get_socket_path

import redis
from PIL import Image
from PIL.PngImagePlugin import PngInfo

from .sharedutils import striptld
from .sharedutils import openjson
from .sharedutils import siteschema
from .sharedutils import stdlog, errlog
from .sharedutils import createfile
from .sharedutils import format_bytes

# pylint: disable=W0703

def creategroup(location: str) -> Dict[str, object] :
    '''
    create a new group for a new provider - added to groups.json
    '''
    mylocation = siteschema(location)
    insertdata: dict = {
        'captcha': bool(),
        'meta': None,
        'locations': [
            mylocation
        ],
        'profile': [],
        'ransomware_galaxy_value': ''
    }
    return insertdata

def checkexisting(provider: str) -> bool:
    '''
    check if group already exists within groups.json
    '''
    red = redis.Redis(unix_socket_path=get_socket_path('cache'), db=0)
    if provider.encode() in red.keys():
        return True
    return False

def threadscape(queuethread, lock):
    '''
    Thread used to scrape our website
    '''
    with sync_playwright() as play:
        while True:
            host, group, base = queuethread.get()
            stdlog('Starting : ' + host['fqdn']+ ' --------- ' + group)
            host['available'] = bool()
            try:
                if group in ['blackbasta', 'clop', 'metaencryptor']:
                    browser = play.firefox.launch(proxy={"server": "socks5://127.0.0.1:9050"},
                          args=['--unsafely-treat-insecure-origin-as-secure='+host['slug']])
                else:
                    browser = play.chromium.launch(proxy={"server": "socks5://127.0.0.1:9050"},
                          args=['--unsafely-treat-insecure-origin-as-secure='+host['slug']])
                context = browser.new_context(ignore_https_errors= True )
                page = context.new_page()
                if 'timeout' in host and host['timeout'] is not None:
                    page.goto(host['slug'], wait_until='load', timeout = host['timeout']*1000)
                else:
                    page.goto(host['slug'], wait_until='load', timeout = 120000)
                page.bring_to_front()
                delay = host['delay']*1000 if ( 'delay' in host and host['delay'] is not None ) \
                    else 15000
                page.wait_for_timeout(delay)
                page.mouse.move(x=500, y=400)
                page.wait_for_load_state('networkidle')
                page.mouse.wheel(delta_y=2000, delta_x=0)
                page.wait_for_load_state('networkidle')
                page.wait_for_timeout(5000)
                filename = group + '-' + striptld(host['slug']) + '.html'
                name = os.path.join(os.getcwd(), 'source', filename)
                with open(name, 'w', encoding='utf-8') as sitesource:
                    sitesource.write(page.content())
                    sitesource.close()

                filename = group + '-' + createfile(host['slug']) + '.png'
                name = os.path.join(get_homedir(), 'source/screenshots', filename)
                page.screenshot(path=name, full_page=True)
                targetImage = Image.open(name)
                metadata = PngInfo()
                metadata.add_text("Source", "RansomLook.io")
                targetImage.save(name, pnginfo=metadata)
                lock.acquire()
                host['available'] = True
                host['title'] = page.title()
                host['lastscrape'] = str(datetime.today())
                host['updated'] = str(datetime.today())
                lock.release()
            except PlaywrightTimeoutError:
                stdlog('Timeout!')
            except Exception as exception:
                errlog(exception)
                errlog("error")
            browser.close()
            stdlog('leaving : ' + host['fqdn']+ ' --------- ' + group)
            red = redis.Redis(unix_socket_path=get_socket_path('cache'), db=base)
            updated = json.loads(red.get(group)) # type: ignore
            for loc in updated['locations']:
                if loc['slug'] == host['slug']:
                    loc.update(host)
            red.set(group, json.dumps(updated))
            time.sleep(5)
            queuethread.task_done()

def scraper(base: int) -> None:
    '''main scraping function'''
    red = redis.Redis(unix_socket_path=get_socket_path('cache'), db=base)
    groups=[]
    for key in red.keys():
        group = json.loads(red.get(key)) # type: ignore
        group['name'] = key.decode()
        groups.append(group)
    groups.sort(key=lambda x: len(x['locations']), reverse=True)
    lock = Lock()
    queuethread = queue.Queue() # type: ignore
    for _ in range(get_config('generic','thread')):
        thread1 = Thread(target=threadscape, args=(queuethread,lock), daemon=True)
        thread1.start()

    for group in groups:
        stdlog('ransomloook: ' + 'working on ' + group['name'])
        # iterate each location/mirror/relay
        for host in group['locations']:
            data=[host,group['name'],base]
            queuethread.put(data)
    queuethread.join()
    time.sleep(5)
    stdlog('Writing result')


    #with open(file, 'w', encoding='utf-8') as groupsfile:
    #    json.dump(groups, groupsfile, ensure_ascii=False, indent=4)
    #    groupsfile.close()

def adder(name: str, location: str, db: int) -> int:
    '''
    handles the addition of new providers to groups.json
    '''
    if checkexisting(name.strip()):
        stdlog('ransomlook: ' + 'records for ' + name + \
            ' already exist, appending to avoid duplication')
        return appender(name.strip(), location, db)
    else:
        red = redis.Redis(unix_socket_path=get_socket_path('cache'), db=0)
        newrec = creategroup(location)
        red.set(name.strip(), json.dumps(newrec))
        stdlog('ransomlook: ' + 'record for ' + name + ' added to groups.json')
        return 0

def appender(name: str, location: str, db: int) -> int:
    '''
    handles the addition of new mirrors and relays for the same site
    to an existing group within groups.json
    '''
    red = redis.Redis(unix_socket_path=get_socket_path('cache'), db=0)
    group = json.loads(red.get(name.strip())) # type: ignore
    success = bool()
    for loc in group['locations']:
        if location == loc['slug']:
            errlog('cannot append to non-existing provider or the location already exists')
            return 2
    group['locations'].append(siteschema(location))
    red.set(name.strip(), json.dumps(group))
    return 1

def threadscreen(queuethread, lock) -> None:
    with sync_playwright() as play:
        while True:
            host, group, title = queuethread.get()
            stdlog('Starting : ' + host['slug']+ ' --------- ' + group)
            try:
                browser = play.firefox.launch(proxy={"server": "socks5://127.0.0.1:9050"},
                    args=['--unsafely-treat-insecure-origin-as-secure='+host['slug']])
                context = browser.new_context(ignore_https_errors= True )
                page = context.new_page()
                if 'timeout' in host and host['timeout'] is not None:
                    page.goto(host['slug'], wait_until='load', timeout = host['timeout']*1000)
                else:
                    page.goto(host['slug'], wait_until='load', timeout = 120000)
                page.bring_to_front()
                delay = host['delay']*1000 if ( 'delay' in host and host['delay'] is not None ) \
                    else 15000
                page.wait_for_timeout(delay)
                page.mouse.move(x=500, y=400)
                page.wait_for_load_state('networkidle')
                page.mouse.wheel(delta_y=2000, delta_x=0)
                page.wait_for_load_state('networkidle')
                page.wait_for_timeout(5000)
                filename = createfile(title) + '.html'
                path = os.path.join(get_homedir(), 'source/', group)
                if not os.path.exists(path):
                    os.mkdir(path)
                name = os.path.join(path, filename)
                with open(name, 'w', encoding='utf-8') as sitesource:
                    sitesource.write(page.content())
                    sitesource.close()

                filename = createfile(title) + '.png'
                path = os.path.join(get_homedir(), 'source/screenshots', group)
                if not os.path.exists(path):
                    os.mkdir(path)
                name = os.path.join(path, filename)
                page.screenshot(path=name, full_page=True)
                targetImage = Image.open(name)
                metadata = PngInfo()
                metadata.add_text("Source", "RansomLook.io")
                targetImage.save(name, pnginfo=metadata)
                lock.acquire()
                red = redis.Redis(unix_socket_path=get_socket_path('cache'), db=2)
                updated = json.loads(red.get(group)) # type: ignore
                for post in updated:
                    if post['post_title'] == title:
                        post['screen'] = str(os.path.join('screenshots', group, filename))
                        post.update(post)
                red.set(group, json.dumps(updated))
                redtoscreen = redis.Redis(unix_socket_path=get_socket_path('cache'), db=1)
                toscreen = json.loads(redtoscreen.get('toscan')) # type: ignore
                for idx, item in enumerate(toscreen):
                    if item['group'] == group and item['title'] == title:
                        toscreen.pop(idx)
                        break
                redtoscreen.set('toscan', json.dumps(toscreen))
                lock.release()
            except PlaywrightTimeoutError:
                stdlog('Timeout!')
            except Exception as exception:
                errlog(exception)
                errlog("error")
            browser.close()
            time.sleep(5)
            queuethread.task_done()

def screen() -> None:
    red = redis.Redis(unix_socket_path=get_socket_path('cache'), db=1)
    if 'toscan'.encode() not in red.keys():
        stdlog('No screen to do !')
        return
    lock = Lock()
    queuethread = queue.Queue() # type: ignore
    for _ in range(get_config('generic','thread')):
        thread1 = Thread(target=threadscreen, args=(queuethread,lock), daemon=True)
        thread1.start()

    captures = json.loads(red.get('toscan')) # type: ignore
    redgroup = redis.Redis(unix_socket_path=get_socket_path('cache'), db=0)
    toscan =[]
    for capture in captures:
        group = json.loads(redgroup.get(capture['group'].encode())) # type: ignore
        for host in group['locations']:
            if capture['slug'].removeprefix(capture['group']+'-').split('.')[0] in striptld(host['slug']):
                host['slug'] = urllib.parse.urljoin(host['slug'], capture['link'])
                if host['slug'] not in toscan:
                    toscan.append(host['slug'])
                    data=[host,capture['group'],capture['title']]
                    queuethread.put(data)
    queuethread.join()
    time.sleep(5)

def threadtorrent(queuethread, lock) -> None:
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
