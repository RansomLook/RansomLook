#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import logging
from datetime import datetime
from datetime import timedelta
import glob
from os.path import dirname, basename, isfile, join
import sys
import redis

from typing import Dict, List, Tuple, Any, Optional

from ransomlook.default.config import get_homedir, get_socket_path, get_config

import tldextract
from urllib.parse import urlparse, urlsplit

logging.basicConfig(
    format='%(asctime)s,%(msecs)d %(levelname)-8s %(message)s',
    datefmt='%Y-%m-%d:%H:%M:%S',
    level=logging.INFO
    )

def stdlog(msg: Any) -> None :
    '''standard infologging'''
    logging.info(msg)

def dbglog(msg: Any) -> None :
    '''standard debug logging'''
    logging.debug(msg)

def errlog(msg: Any) -> None :
    '''standard error logging'''
    logging.error(msg)

def honk(msg: Any) -> None :
    '''critical error logging with termination'''
    logging.critical(msg)
    sys.exit()


def gcount(posts: List[Dict[str, Any]]) -> Dict[str, int]:
    group_counts: Dict[str, int] = {}
    for post in posts:
        if post['group_name'] in group_counts:
            group_counts[post['group_name']] += 1
        else:
            group_counts[post['group_name']] = 1
    return group_counts

'''
markdown
'''
def postcount() -> int :
    post_count = 0
    red = redis.Redis(unix_socket_path=get_socket_path('cache'), db=2)
    for group in red.keys():
        grouppost = json.loads(red.get(group)) # type: ignore
        post_count+=len(grouppost)
    return post_count

def groupcount(db: int) -> int :
    red = redis.Redis(unix_socket_path=get_socket_path('cache'), db=db)
    groups = red.keys()
    return len(groups)

def hostcount(db: int) -> int :
    hosts = []
    red = redis.Redis(unix_socket_path=get_socket_path('cache'), db=db)
    groups = red.keys()
    for entry in groups:
        group = json.loads(red.get(entry)) # type: ignore
        for host in group['locations']:
            hosts.append(host['fqdn'])
    return len(set(hosts))

def hostcountdls(db: int) -> int :
    red = redis.Redis(unix_socket_path=get_socket_path('cache'), db=db)
    groups = red.keys()
    hosts = []
    for entry in groups:
        group = json.loads(red.get(entry)) # type: ignore
        for host in group['locations']:
            if ('chat' not in host or host['chat'] is False) and ('fs' not in host or host['fs'] is False) and ('admin' not in host or host['admin'] is False):
                hosts.append(host['fqdn'])
    return len(set(hosts))

def hostcountfs(db: int) -> int :
    red = redis.Redis(unix_socket_path=get_socket_path('cache'), db=db)
    groups = red.keys()
    hosts =[]
    for entry in groups:
        group = json.loads(red.get(entry)) # type: ignore
        for host in group['locations']:
            if 'fs' in host and host['fs'] is True:
                hosts.append(host['fqdn'])
    return len(set(hosts))

def hostcountchat(db: int) -> int :
    red = redis.Redis(unix_socket_path=get_socket_path('cache'), db=db)
    groups = red.keys()
    hosts = []
    for entry in groups:
        group = json.loads(red.get(entry)) # type: ignore
        for host in group['locations']:
            if 'chat' in host and host['chat'] is True:
                hosts.append(host['fqdn'])
    return len(set(hosts))

def hostcountadmin(db: int) -> int :
    red = redis.Redis(unix_socket_path=get_socket_path('cache'), db=db)
    groups = red.keys()
    hosts = []
    for entry in groups:
        group = json.loads(red.get(entry)) # type: ignore
        for host in group['locations']:
            if 'admin' in host and host['admin'] is True:
                hosts.append(host['fqdn'])
    return len(set(hosts))

def postssince(days: int) -> int :
    '''returns the number of posts within the last x days'''
    post_count = 0
    red = redis.Redis(unix_socket_path=get_socket_path('cache'), db=2)
    groups = red.keys()
    for entry in groups:
        posts = json.loads(red.get(entry)) # type: ignore
        for post in posts:
            try:
                datetime_object = datetime.strptime(post['discovered'], '%Y-%m-%d %H:%M:%S.%f')
            except:
                datetime_object = datetime.strptime(post['discovered'], '%Y-%m-%d %H:%M:%S')
            if datetime_object > datetime.now() - timedelta(days=days):
                post_count += 1
    return post_count

def poststhisyear() -> int :
    '''returns the number of posts within the current year'''
    current_year = datetime.now().year
    post_count = 0
    red = redis.Redis(unix_socket_path=get_socket_path('cache'), db=2)
    groups = red.keys()
    for entry in groups:
        posts = json.loads(red.get(entry)) # type: ignore
        for post in posts:
            try:
                datetime_object = datetime.strptime(post['discovered'], '%Y-%m-%d %H:%M:%S.%f')
            except:
                datetime_object = datetime.strptime(post['discovered'], '%Y-%m-%d %H:%M:%S')
            if datetime_object.year == current_year:
                post_count += 1
    return post_count

def postslast24h() -> int :
    '''returns the number of posts within the last 24 hours'''
    post_count = 0
    red = redis.Redis(unix_socket_path=get_socket_path('cache'), db=2)
    groups = red.keys()
    for entry in groups:
        posts = json.loads(red.get(entry)) # type: ignore
        for post in posts:
            try :
                datetime_object = datetime.strptime(post['discovered'], '%Y-%m-%d %H:%M:%S.%f')
            except:
                datetime_object = datetime.strptime(post['discovered'], '%Y-%m-%d %H:%M:%S')
            if datetime_object > datetime.now() - timedelta(hours=24):
               post_count += 1
    return post_count

def parsercount() -> int :
    modules = glob.glob(join(dirname(str(get_homedir())+'/'+'ransomlook/parsers/'), "*.py"))
    __all__ = [ basename(f)[:-3] for f in modules if isfile(f) and not f.endswith('__init__.py')]
    return len(__all__)

def onlinecount(db: int) -> int :
    red = redis.Redis(unix_socket_path=get_socket_path('cache'), db=db)
    groups = red.keys()
    online_count = 0
    for entry in groups:
        group = json.loads(red.get(entry)) # type: ignore
        for host in group['locations']:
            if host['available'] is True:
                online_count += 1
    return online_count

def currentmonthstr() -> str :
    '''
    return the current, full month name in lowercase
    '''
    return datetime.now().strftime('%B').lower()

def mounthlypostcount() -> int :
    '''
    returns the number of posts within the current month
    '''
    post_count = 0
    red = redis.Redis(unix_socket_path=get_socket_path('cache'), db=2)
    groups = red.keys()
    date_today = datetime.now()
    month_first_day = date_today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    for entry in groups:
        posts = json.loads(red.get(entry)) # type: ignore
        for post in posts:
            try:
                datetime_object = datetime.strptime(post['discovered'], '%Y-%m-%d %H:%M:%S.%f')
            except:
                datetime_object = datetime.strptime(post['discovered'], '%Y-%m-%d %H:%M:%S')
            if datetime_object > month_first_day:
                post_count += 1
    return post_count

def countcaptchahosts() -> int :
    '''returns a count on the number of groups that have captchas'''
    red = redis.Redis(unix_socket_path=get_socket_path('cache'), db=0)
    groups = red.keys()
    captcha_count = 0
    for entry in groups:
        group = json.loads(red.get(entry)) # type: ignore
        if group['captcha'] is True:
            captcha_count += 1
    return captcha_count

'''
Ransomlook
'''
def siteschema(location: str, fs: bool, private: bool, chat: bool, admin: bool, browser: str|None, init_script: str|None) -> Dict[str, Optional[Any]] :
    '''
    returns a dict with the site schema
    '''
    if not location.startswith('http'):
        dbglog('sharedutils: ' + 'assuming we have been given an fqdn and appending protocol')
        location = 'http://' + location
    schema = {
        'fqdn': getapex(location),
        'title': None,
        'timeout': None,
        'delay': None,
        'version': getonionversion(location)[0],
        'slug': location,
        'available': False,
        'updated': str(datetime.today()),
        'fs': fs,
        'chat': chat,
        'admin': admin,
        'browser': browser,
        'init_script': init_script,
        'private': private,
        'lastscrape': 'Never'
    }
    dbglog('sharedutils: ' + 'schema - ' + str(schema))
    return schema

def getapex(slug: str) -> str :
    '''
    returns the domain for a given webpage/url slug
    '''
    stripurl = tldextract.extract(slug)
    print(stripurl)
    if stripurl.subdomain:
        return stripurl.subdomain + '.' + stripurl.domain + '.' + stripurl.suffix
    else:
        return stripurl.domain + '.' + stripurl.suffix

def getonionversion(slug: str) -> Tuple[int, str]:
    '''
    returns the version of an onion service (v2/v3)
    https://support.torproject.org/onionservices/v2-deprecation
    '''
    version = None
    stripurl = tldextract.extract(slug)
    location = stripurl.domain + '.' + stripurl.suffix
    stdlog('sharedutils: ' + 'checking for onion version - ' + str(location))
    if len(stripurl.domain) == 16:
        stdlog('sharedutils: ' + 'v2 onionsite detected')
        version = 2
    elif len(stripurl.domain) == 56:
        stdlog('sharedutils: ' + 'v3 onionsite detected')
        version = 3
    else:
        stdlog('sharedutils: ' + 'unknown onion version, assuming clearnet')
        version = 0
    return version, location

def striptld(slug: str) -> str :
    '''
    strips the tld from a url
    '''
    #stripurl = tldextract.extract(slug)
    #return stripurl.domain
    parsed = urlparse(slug)
    scheme = "%s://" % parsed.scheme
    return parsed.geturl().replace(scheme, '', 1).replace('/','-')

def createfile(slug: str) -> str :
    schema = urlsplit(slug)
    filename = schema.netloc+''.join(schema.path.split('/'))
    return ''.join(filename.split('.'))

def format_bytes(size: int) -> str :
    # 2**10 = 1024
    power = 2**10
    n = 0
    power_labels = {0 : 'B', 1: 'KB', 2: 'MB', 3: 'GB', 4: 'TB'}
    while size > power:
        size /= power # type: ignore
        n += 1
    return f"{size:.2f} {power_labels[n]}"
