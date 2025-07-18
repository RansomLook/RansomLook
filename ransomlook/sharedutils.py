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

import matplotlib.pyplot as plt
import plotly.express as px # type: ignore
import plotly.io as pio     # type: ignore
import pandas as pd

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

'''
Graphs
'''
def statsgroup(group: bytes) -> None :
    # Reset variables
    victim_counts: Dict[str, int] = {}
    dates = (Any)
    counts = (Any)

    red = redis.Redis(unix_socket_path=get_socket_path('cache'), db=2)
    post_data = json.loads(red.get(group)) # type: ignore
    # Count the number of victims per day
    for post in post_data:
        date = post['discovered'].split(' ')[0]
        victim_counts[date] = victim_counts.get(date, 0) + 1 

    # Sort the victim counts by date
    sorted_counts = sorted(victim_counts.items())

    # Extract the dates and counts for plotting
    dates, counts = zip(*sorted_counts) # type: ignore
    # Plot the graph
    plt.clf()
    # Create a new figure and axes for each group with a larger figure size
    px = 1/plt.rcParams['figure.dpi']
    if get_config("generic","darkmode"):
        fig,ax = plt.subplots(figsize=(1050*px, 750*px), facecolor='#272b30')
    else: 
        fig,ax = plt.subplots(figsize=(1050*px, 750*px))
    # plt.plot(dates, counts)
    color = '#505d6b'
    if get_config("generic","darkmode"):
        color ='#ddd'
    ax.bar(dates, counts, color = '#6ad37a') # type: ignore
    ax.set_xlabel('New daily discovery when parsing', color = color)
    ax.set_ylabel('Number of Victims', color = color)
    ax.set_title('Number of Victims for Group: ' + group.decode().title(), color = color)
    ax.tick_params(axis='x', bottom=False, labelbottom=False)
    if get_config("generic","darkmode"):
        #ax.set_xtick
        for pos in ['top', 'bottom', 'right', 'left']:
            ax.spines[pos].set_edgecolor(color)
        ax.tick_params(colors=color)
        ax.set_facecolor("#272b30")

    # Set the x-axis limits
    #ax.set_xlim(str(dates[0]), str(dates[-1:]))
    # Format y-axis ticks as whole numbers without a comma separator

    plt.tight_layout()

    # Save the graph as an image file
    plt.savefig(str(get_homedir()) +'/source/screenshots/stats/' + group.decode() + '.png')
    plt.close(fig)

def run_data_viz(days_filter: int) -> None:
    now = datetime.now()

    red = redis.Redis(unix_socket_path=get_socket_path('cache'), db=2)

    group_names = []
    timestamps = []
    for key in red.keys():
        posts = json.loads(red.get(key)) # type: ignore
        for post in posts:
            postdate = datetime.fromisoformat(post['discovered'])
            if (now - postdate).days < days_filter:
                group_names.append(key.decode())
                timestamps.append(post['discovered'])
    df = pd.DataFrame({'group_name': group_names, 'timestamp': timestamps})
    # Convert the timestamps into a datetime format
    df['timestamp'] = pd.to_datetime(df['timestamp'], format='mixed')

    # Group and sort the data by the number of postings in each group
    df_sorted = df.groupby(['group_name', 'timestamp']).size().reset_index(name='count')
    df_sorted = df_sorted.sort_values(by='count', ascending=False)

    # Use Plotly's Heatmap plot to create the density heatmap
    fig1 = px.density_heatmap(df_sorted, x='timestamp', y='group_name', z='count', title='Posting Frequency by group', width=1050, height=750)
    fig1.update_layout(font=dict(family='Roboto'))
    filename = join(get_homedir(),"source/screenshots/stats","density_heatmap_"+ str(days_filter)+".png")
    fig1.write_image(filename)

    # Use Plotly's Scatter plot to create the scatter plot
    fig2 = px.scatter(df_sorted, x='timestamp', y='group_name', color='group_name', title='Posting Frequency by group', color_continuous_scale='Plotly3', width=1050, height=750)
    #fig2 = px.scatter(df_sorted, x='group_name', y='count', title='Posting Frequency by Group', template='plotly_dark')
    filename = join(get_homedir(),"source/screenshots/stats","scatter_plot_"+ str(days_filter)+".png")
    fig2.write_image(filename)

    # Use Plotly's Bar plot to create the bar chart
    #fig4 = px.bar(df_sorted, x='group_name', y='count', color='count', title='Posting Frequency by Group', template='plotly_dark', color_continuous_scale='Portland')
    #fig4.show()

    # Group and sort the data by the number of postings in each group
    df_sorted = df.groupby('group_name').size().reset_index(name='count').sort_values(by='count', ascending=True)

    # Use Plotly's Pie plot to create the pie chart
    fig3 = px.pie(df_sorted, values='count', names='group_name', title='Posting Frequency by Group', width=1050, height=750)
    filename = join(get_homedir(),"source/screenshots/stats","pie_chart_"+ str(days_filter)+".png")
    fig3.write_image(filename)

    # Use Plotly's Scatter plot to visualize the data
    fig4 = px.bar(df_sorted, x='group_name', y='count', color='count', title='Posting Frequency by Group', color_continuous_scale='Portland',width=1050, height=750)
    filename = join(get_homedir(),"source/screenshots/stats","bar_chart_"+ str(days_filter)+".png")
    fig4.write_image(filename)

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
    red = redis.Redis(unix_socket_path=get_socket_path('cache'), db=db)
    groups = red.keys()
    host_count = 0
    for entry in groups:
        group = json.loads(red.get(entry)) # type: ignore
        for host in group['locations']:
            host_count += 1
    return host_count

def hostcountdls(db: int) -> int :
    red = redis.Redis(unix_socket_path=get_socket_path('cache'), db=db)
    groups = red.keys()
    host_count = 0
    for entry in groups:
        group = json.loads(red.get(entry)) # type: ignore
        for host in group['locations']:
            if (not 'chat' in host or host['chat'] is False) and (not 'fs' in host or host['fs'] is False) and (not 'admin' in host or host['admin'] is False):
                host_count += 1
    return host_count

def hostcountfs(db: int) -> int :
    red = redis.Redis(unix_socket_path=get_socket_path('cache'), db=db)
    groups = red.keys()
    host_count = 0
    for entry in groups:
        group = json.loads(red.get(entry)) # type: ignore
        for host in group['locations']:
            if 'fs' in host and host['fs'] is True:
                host_count += 1
    return host_count

def hostcountchat(db: int) -> int :
    red = redis.Redis(unix_socket_path=get_socket_path('cache'), db=db)
    groups = red.keys()
    host_count = 0
    for entry in groups:
        group = json.loads(red.get(entry)) # type: ignore
        for host in group['locations']:
            if 'chat' in host and host['chat'] is True:
                host_count += 1
    return host_count

def hostcountadmin(db: int) -> int :
    red = redis.Redis(unix_socket_path=get_socket_path('cache'), db=db)
    groups = red.keys()
    host_count = 0
    for entry in groups:
        group = json.loads(red.get(entry)) # type: ignore
        for host in group['locations']:
            if 'admin' in host and host['admin'] is True:
                host_count += 1
    return host_count

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
