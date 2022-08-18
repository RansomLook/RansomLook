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
from datetime import datetime

# local imports

#import parsers
#import geckodrive
#from markdown import main as markdown

from sharedutils import striptld
from sharedutils import openjson
from sharedutils import checktcp
from sharedutils import siteschema
from sharedutils import socksfetcher
from sharedutils import getsitetitle
from sharedutils import getonionversion
from sharedutils import sockshost, socksport
from sharedutils import stdlog, dbglog, errlog, honk

from sharedutils import createfile

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

def creategroup(name, location):
    '''
    create a new group for a new provider - added to groups.json
    '''
    location = siteschema(location)
    insertdata = {
        'name': name,
        'captcha': bool(),
        'parser': bool(),
        'geckodriver': bool(),
        'javascript_render': bool(),
        'meta': None,
        'locations': [
            location
        ],
        'profile': list()
    }
    return insertdata

def checkexisting(provider):
    '''
    check if group already exists within groups.json
    '''
    groups = openjson("data/groups.json")
    for group in groups:
        if group['name'] == provider:
            return True
    return False

def scraper():
    '''main scraping function'''
    groups = openjson("data/groups.json")
    # iterate each provider
    with sync_playwright() as p:
      for group in groups:
        stdlog('ransomloook: ' + 'working on ' + group['name'])
        # iterate each location/mirror/relay
        for host in group['locations']:
            host['available'] = bool()
            '''
            only scrape onion v3 unless using headless browser, not long before this will not be possible
            https://support.torproject.org/onionservices/v2-deprecation/
            '''
            try:
               browser = p.chromium.launch(proxy={"server": "socks5://127.0.0.1:9050"})
               context = browser.new_context(ignore_https_errors= True )
               page = context.new_page()
               entry = page.goto(host['slug'], wait_until='load')
               #page.screenshot(path="example.png", full_page=True)
               page.bring_to_front()
               page.wait_for_timeout(5000) 
               page.mouse.move(x=500, y=400)
               page.wait_for_load_state('networkidle')
               page.mouse.wheel(delta_y=2000, delta_x=0)
               page.wait_for_load_state('networkidle')
               page.wait_for_timeout(5000)
               filename = group['name'] + '-' + striptld(host['slug']) + '.html'
               name = os.path.join(os.getcwd(), 'source', filename)
               with open(name, 'w', encoding='utf-8') as sitesource:
                    sitesource.write(page.content())
                    sitesource.close()

               filename = group['name'] + '-' + createfile(host['slug']) + '.png'
               name = os.path.join(os.getcwd(), 'source/screenshots', filename)
               saved = page.screenshot(path=name, full_page=True)
               host['available'] = True
               host['title'] = page.title()
               host['lastscrape'] = str(datetime.today())            
               host['updated'] = str(datetime.today())
               with open('data/groups.json', 'w', encoding='utf-8') as groupsfile:
                   json.dump(groups, groupsfile, ensure_ascii=False, indent=4)
                   groupsfile.close()
            except PlaywrightTimeoutError:
               print("Timeout!")
            except Exception as e:
               print(e)
               print("error")
            browser.close()

def forumscraper():
    '''main scraping function'''
    groups = openjson("data/markets.json")
    # iterate each provider
    with sync_playwright() as p:
      for group in groups:
        stdlog('ransomlook: ' + 'working on ' + group['name'])
        # iterate each location/mirror/relay
        for host in group['locations']:
            stdlog('ransomlook: ' + 'scraping ' + host['slug'])
            host['available'] = bool()
            '''
            only scrape onion v3 unless using headless browser, not long before this will not be possible
            https://support.torproject.org/onionservices/v2-deprecation/
            '''
            try:
               browser = p.chromium.launch(proxy={"server": "socks5://127.0.0.1:9050"})
               context = browser.new_context(ignore_https_errors= True )
               page = context.new_page()
               entry = page.goto(host['slug'])
               #page.screenshot(path="example.png", full_page=True)
               filename = group['name'] + '-' + striptld(host['slug']) + '.html'
               name = os.path.join(os.getcwd(), 'source', filename)
               stdlog('ransomlook: ' + 'saving ' + name)
               with open(name, 'w', encoding='utf-8') as sitesource:
                    sitesource.write(page.content())
                    sitesource.close()

               filename = group['name'] + '-' + createfile(host['slug']) + '.png'
               name = os.path.join(os.getcwd(), 'source/screenshots', filename)
               saved = page.screenshot(path=name, full_page=True)
               stdlog('ransomlook: ' + 'saving ' + name)
               dbglog('ransomlook: ' + 'saving ' + name + ' successful')
               host['available'] = True
               host['title'] = page.title()
               host['lastscrape'] = str(datetime.today())            
               host['updated'] = str(datetime.today())
               dbglog('ransomlook: ' + 'scrape successful')
               with open('data/markets.json', 'w', encoding='utf-8') as groupsfile:
                   json.dump(groups, groupsfile, ensure_ascii=False, indent=4)
                   groupsfile.close()
            except PlaywrightTimeoutError:
               print("Timeout!")
            except Exception as e:
               print(e)
            browser.close()

def adder(name, location):
    '''
    handles the addition of new providers to groups.json
    '''
    if checkexisting(name):
        stdlog('ransomlook: ' + 'records for ' + name + ' already exist, appending to avoid duplication')
        appender(args.name, args.location)
    else:
        groups = openjson("data/groups.json")
        newrec = creategroup(name, location)
        groups.append(dict(newrec))
        with open('data/groups.json', 'w', encoding='utf-8') as groupsfile:
            json.dump(groups, groupsfile, ensure_ascii=False, indent=4)
        stdlog('ransomlook: ' + 'record for ' + name + ' added to groups.json')

def appender(name, location):
    '''
    handles the addition of new mirrors and relays for the same site
    to an existing group within groups.json
    '''
    groups = openjson("data/groups.json")
    success = bool()
    for group in groups:
        if group['name'] == name:
            group['locations'].append(siteschema(location))
            success = True
    if success:
        with open('data/groups.json', 'w', encoding='utf-8') as groupsfile:
            json.dump(groups, groupsfile, ensure_ascii=False, indent=4)
    else:
        errlog('cannot append to non-existing provider')


