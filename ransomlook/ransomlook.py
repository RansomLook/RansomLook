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
import time
from typing import Dict
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

from .default.config import get_config, get_homedir, get_socket_path

import redis

from .sharedutils import striptld
from .sharedutils import openjson
from .sharedutils import siteschema
from .sharedutils import stdlog, errlog
from .sharedutils import createfile

# pylint: disable=W0703

def creategroup(location: str) -> Dict[str, object] :
    '''
    create a new group for a new provider - added to groups.json
    '''
    mylocation = siteschema(location)
    insertdata = {
        'captcha': bool(),
        'meta': None,
        'locations': [
            mylocation
        ],
        'profile': []
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
            updated = json.loads(red.get(group))
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
        group = json.loads(red.get(key))
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
    if checkexisting(name):
        stdlog('ransomlook: ' + 'records for ' + name + \
            ' already exist, appending to avoid duplication')
        return appender(name, location, db)
    else:
        red = redis.Redis(unix_socket_path=get_socket_path('cache'), db=0)
        newrec = creategroup(location)
        red.set(name, json.dumps(newrec))
        stdlog('ransomlook: ' + 'record for ' + name + ' added to groups.json')
        return 0

def appender(name: str, location: str, db: int) -> int:
    '''
    handles the addition of new mirrors and relays for the same site
    to an existing group within groups.json
    '''
    red = redis.Redis(unix_socket_path=get_socket_path('cache'), db=0)
    group = json.loads(red.get(name))
    success = bool()
    for loc in group['locations']:
        if location == loc['slug']:
            errlog('cannot append to non-existing provider or the location already exists')
            return 2
    group['locations'].append(siteschema(location))
    red.set(name, json.dumps(group))
    return 1
