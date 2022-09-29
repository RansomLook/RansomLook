
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

from typing import Dict, List, Tuple, Any

from ransomlook.default.config import get_homedir, get_socket_path

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

def openjson(file: str) -> List :
    '''
    opens a file and returns the json as a dict
    '''
    try:
        filename=file
        with open(str(get_homedir())+'/'+filename, encoding='utf-8') as jsonfile:
            data = json.load(jsonfile)
    except:
        data = []
    return data

def honk(msg: Any) -> None :
    '''critical error logging with termination'''
    logging.critical(msg)
    sys.exit()

'''
Graphs
'''
def gcount(posts: List) -> Dict[str, int]:
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
        grouppost = json.loads(red.get(group))
        post_count+=len(grouppost)
    return post_count

def groupcount() -> int :
    red = redis.Redis(unix_socket_path=get_socket_path('cache'), db=0)
    groups = red.keys()
    return len(groups)

def hostcount() -> int :
    red = redis.Redis(unix_socket_path=get_socket_path('cache'), db=0)
    groups = red.keys()
    host_count = 0
    for entry in groups:
        group = json.loads(red.get(entry))
        for host in group['locations']:
            host_count += 1
    return host_count

def postssince(days: int) -> int :
    '''returns the number of posts within the last x days'''
    post_count = 0
    red = redis.Redis(unix_socket_path=get_socket_path('cache'), db=2)
    groups = red.keys()
    for entry in groups:
        posts = json.loads(red.get(entry))
        for post in posts:
            datetime_object = datetime.strptime(post['discovered'], '%Y-%m-%d %H:%M:%S.%f')
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
        posts = json.loads(red.get(entry))
        for post in posts:
            datetime_object = datetime.strptime(post['discovered'], '%Y-%m-%d %H:%M:%S.%f')
            if datetime_object.year == current_year:
                post_count += 1
    return post_count

def postslast24h() -> int :
    '''returns the number of posts within the last 24 hours'''
    post_count = 0
    red = redis.Redis(unix_socket_path=get_socket_path('cache'), db=2)
    groups = red.keys()
    for entry in groups:
        posts = json.loads(red.get(entry))
        for post in posts:
            datetime_object = datetime.strptime(post['discovered'], '%Y-%m-%d %H:%M:%S.%f')
            if datetime_object > datetime.now() - timedelta(hours=24):
                post_count += 1
    return post_count

def parsercount() -> int :
    modules = glob.glob(join(dirname(str(get_homedir())+'/'+'ransomlook/parsers/'), "*.py"))
    __all__ = [ basename(f)[:-3] for f in modules if isfile(f) and not f.endswith('__init__.py')]
    return len(__all__)

def onlinecount() -> int :
    red = redis.Redis(unix_socket_path=get_socket_path('cache'), db=0)
    groups = red.keys()
    online_count = 0
    for entry in groups:
        group = json.loads(red.get(entry))
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
        posts = json.loads(red.get(entry))
        for post in posts:
            datetime_object = datetime.strptime(post['discovered'], '%Y-%m-%d %H:%M:%S.%f')
            if datetime_object > month_first_day:
                post_count += 1
    return post_count

def countcaptchahosts() -> int :
    '''returns a count on the number of groups that have captchas'''
    red = redis.Redis(unix_socket_path=get_socket_path('cache'), db=0)
    groups = red.keys()
    captcha_count = 0
    for entry in groups:
        group = json.loads(red.get(entry))
        if group['captcha'] is True:
            online_count += 1
    return captcha_count

'''
Ransomlook
'''
def siteschema(location) -> Dict :
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
        'updated': None,
        'lastscrape': '2021-05-01 00:00:00.000000'
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
