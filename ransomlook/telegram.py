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

def threadscape(queuethread, lock):
    '''
    Thread used to scrape our website
    '''
    with sync_playwright() as play:
        while True:
            host = queuethread.get()
            stdlog('Starting : ' + host)
            try:
                browser = play.chromium.launch()
#proxy={"server": "socks5://127.0.0.1:9050"},
#                          args=['--unsafely-treat-insecure-origin-as-secure='+host['link']])
                context = browser.new_context(ignore_https_errors= True )
                page = context.new_page()
                link='https://t.me/s/'+host
                page.goto(link, wait_until='load', timeout = 60000)
                page.bring_to_front()
                page.wait_for_timeout(1000)
                page.mouse.move(x=500, y=400)
                page.wait_for_load_state('networkidle')
                page.mouse.wheel(delta_y=2000, delta_x=0)
                page.wait_for_load_state('networkidle')
                page.wait_for_timeout(1000)
                filename = host + '.html'
                name = os.path.join(os.getcwd(), 'source/telegram', filename)
                with open(name, 'w', encoding='utf-8') as sitesource:
                    sitesource.write(page.content())
                    sitesource.close()

                filename = host + '.png'
                name = os.path.join(get_homedir(), 'source/screenshots/telegram', filename)
                page.screenshot(path=name, full_page=True)
                lock.acquire()
                lock.release()
            except PlaywrightTimeoutError:
                stdlog('Timeout!')
            except Exception as exception:
                errlog(exception)
                errlog("error")
            browser.close()
            stdlog('leaving : ' + host)
            time.sleep(5)
            queuethread.task_done()

def scraper() -> None:
    '''main scraping function'''
    red = redis.Redis(unix_socket_path=get_socket_path('cache'), db=5)
    groups=[]
    for key in red.keys():
        group = json.loads(red.get(key))
        groups.append(group)
    lock = Lock()
    queuethread = queue.Queue() # type: ignore
    for _ in range(get_config('generic','thread')):
        thread1 = Thread(target=threadscape, args=(queuethread,lock), daemon=True)
        thread1.start()

    for key in red.keys():
        stdlog('ransomloook: ' + 'working on ' + key.decode())
        queuethread.put(key.decode())
    queuethread.join()
    time.sleep(5)
    stdlog('Writing result')


    #with open(file, 'w', encoding='utf-8') as groupsfile:
    #    json.dump(groups, groupsfile, ensure_ascii=False, indent=4)
    #    groupsfile.close()

def parser():
    '''parsing telegram'''
    print("ok")
