#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
🧅 👀 🦅 👹
ransomlook
does what it says on the tin
'''
import os
import json
import argparse
import queue
from threading import Thread, Lock
from datetime import datetime
import time
from typing import List, Dict
from .default.config import get_config

from .sharedutils import striptld
from .sharedutils import openjson
from .sharedutils import siteschema
from .sharedutils import stdlog, dbglog, errlog, honk
from .sharedutils import createfile

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

def creategroup(name: str, location: str) -> Dict[str, object] :
    '''
    create a new group for a new provider - added to groups.json
    '''
    mylocation = siteschema(location)
    insertdata = {
        'name': name,
        'captcha': bool(),
        'meta': None,
        'locations': [
            mylocation
        ],
        'profile': list()
    }
    return insertdata

def checkexisting(provider: str) -> bool:
    '''
    check if group already exists within groups.json
    '''
    groups = openjson("data/groups.json")
    for group in groups:
        if group['name'] == provider:
            return True
    return False


def threadscape(q, lock):
    with sync_playwright() as p:
        while True:
            host, group = q.get()
            stdlog('Starting : ' + host['fqdn']+ ' --------- ' + group)
            host['available'] = bool()
            '''
            only scrape onion v3 unless using headless browser, not long before this will not be possible
            https://support.torproject.org/onionservices/v2-deprecation/
            '''
            try:
               browser = p.chromium.launch(proxy={"server": "socks5://127.0.0.1:9050"})
               context = browser.new_context(ignore_https_errors= True )
               page = context.new_page()
               if 'timeout' in host and host['timeout'] is not None:
                  entry = page.goto(host['slug'], wait_until='load', timeout = host['timeout']*1000)
               else:
                  entry = page.goto(host['slug'], wait_until='load', timeout = 120000)
               page.bring_to_front()
               page.wait_for_timeout(5000) 
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
               name = os.path.join(os.getcwd(), 'source/screenshots', filename)
               saved = page.screenshot(path=name, full_page=True)
               lock.acquire()
               host['available'] = True
               host['title'] = page.title()
               host['lastscrape'] = str(datetime.today())
               host['updated'] = str(datetime.today())
               lock.release()
            except PlaywrightTimeoutError:
               stdlog('Timeout!')
            except Exception as e:
               errlog(e)
               errlog("error")
            browser.close()
            stdlog('leaving : ' + host['fqdn']+ ' --------- ' + group)
            q.task_done()


def scraper(file: str) -> None:
    '''main scraping function'''
    groups = openjson(file)
    lock = Lock()
    q = queue.Queue() # type: ignore
    for numthread in range(get_config('generic','thread')):
        t1 = Thread(target=threadscape, args=(q,lock), daemon=True)
        t1.start()
    for group in groups:
        stdlog('ransomloook: ' + 'working on ' + group['name'])
        # iterate each location/mirror/relay
        for host in group['locations']:
            data=[host,group['name']]
            q.put(data)
    q.join()
    time.sleep(5)
    stdlog('Writing result')
    with open(file, 'w', encoding='utf-8') as groupsfile:
        json.dump(groups, groupsfile, ensure_ascii=False, indent=4)
        groupsfile.close()

def adder(name: str, location: str) -> None:
    '''
    handles the addition of new providers to groups.json
    '''
    if checkexisting(name):
        stdlog('ransomlook: ' + 'records for ' + name + ' already exist, appending to avoid duplication')
        appender(name, location)
    else:
        groups = openjson("data/groups.json")
        newrec = creategroup(name, location)
        groups.append(dict(newrec))
        with open('data/groups.json', 'w', encoding='utf-8') as groupsfile:
            json.dump(groups, groupsfile, ensure_ascii=False, indent=4)
        stdlog('ransomlook: ' + 'record for ' + name + ' added to groups.json')

def appender(name: str, location: str) -> None:
    '''
    handles the addition of new mirrors and relays for the same site
    to an existing group within groups.json
    '''
    groups = openjson("data/groups.json")
    success = bool()
    for group in groups:
        if group['name'] == name:
            for loc in group['locations']:
                 if location == loc['slug']:
                     errlog('cannot append to non-existing provider or the location already exists')
                     return
            group['locations'].append(siteschema(location))
            success = True
    if success:
        with open('data/groups.json', 'w', encoding='utf-8') as groupsfile:
            json.dump(groups, groupsfile, ensure_ascii=False, indent=4)
    else:
        errlog('cannot append to non-existing provider or the location already exists')
