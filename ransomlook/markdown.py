#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import time
from datetime import datetime as dt

import glob
from os.path import dirname, basename, isfile, join


from .sharedutils import gcount
from .sharedutils import openjson
from .sharedutils import postcount
from .sharedutils import hostcount
from .sharedutils import groupcount
from .sharedutils import postssince
from .sharedutils import parsercount
from .sharedutils import onlinecount
from .sharedutils import postslast24h
from .sharedutils import poststhisyear
from .sharedutils import currentmonthstr
from .sharedutils import mounthlypostcount
from .sharedutils import countcaptchahosts
from .sharedutils import stdlog, dbglog, errlog, honk
from .plotting import trend_posts_per_day, plot_posts_by_group, pie_posts_by_group

from sharedutils import createfile

def suffix(d):
    return 'th' if 11<=d<=13 else {1:'st',2:'nd',3:'rd'}.get(d%10, 'th')

def custom_strftime(fmt, t):
    return t.strftime(fmt).replace('{S}', str(t.day) + suffix(t.day))

friendly_tz = custom_strftime('%B {S}, %Y', dt.now()).lower()

def writeline(file, line):
    '''write line to file'''
    with open(file, 'a') as f:
        f.write(line + '\n')
        f.close()

def groupreport():
    '''
    create a list with number of posts per unique group
    '''
    stdlog('generating group report')
    posts = openjson('data/posts.json')
    # count the number of posts by group_name within posts.json
    group_counts = gcount(posts)
    # sort the group_counts - descending
    sorted_group_counts = sorted(group_counts.items(), key=lambda x: x[1], reverse=True)
    stdlog('group report generated with %d groups' % len(sorted_group_counts))
    return sorted_group_counts

def mainpage():
    '''
    main markdown report generator - used with github pages
    '''
    stdlog('generating main page')
    uptime_sheet = 'docs/README.md'
    with open(uptime_sheet, 'w') as f:
        f.close()
    writeline(uptime_sheet, '')
    writeline(uptime_sheet, '_' + friendly_tz + '_')
    writeline(uptime_sheet, '')
    writeline(uptime_sheet, 'Currently tracking `' + str(groupcount()) + '` groups across `' + str(hostcount()) + '` relays & mirrors - _`' + str(onlinecount()) + '` currently online_')
    writeline(uptime_sheet, '')
    writeline(uptime_sheet, 'There have been `' + str(postslast24h()) + '` posts within the `last 24 hours`')
    writeline(uptime_sheet, '')
    writeline(uptime_sheet, 'There have been `' + str(mounthlypostcount()) + '` posts within the `month of ' + currentmonthstr() + '`')
    writeline(uptime_sheet, '')
    writeline(uptime_sheet, 'There have been `' + str(postssince(90)) + '` posts within the `last 90 days`')
    writeline(uptime_sheet, '')
    writeline(uptime_sheet, 'There have been `' + str(poststhisyear()) + '` posts within the `year of ' + str(dt.now().year) + '`')
    writeline(uptime_sheet, '')
    writeline(uptime_sheet, 'There have been `' + str(postcount()) + '` posts `since the dawn of ransomlook`')
    writeline(uptime_sheet, '')
    writeline(uptime_sheet, 'There are `' + str(parsercount()) + '` custom parsers indexing posts')

def indexpage():
    index_sheet = 'docs/status.md'
    with open(index_sheet, 'w') as f:
        f.close()
    groups = openjson('data/groups.json')
    writeline(index_sheet, '## 📚 Group status')
    writeline(index_sheet, '')
    header = '| Group | Page title | Server status | Last seen | Location | Screen |'
    writeline(index_sheet, header)
    writeline(index_sheet, '|---|---|---|---|---|---|')
    groups.sort(key=lambda x: x["name"].lower())
    for group in groups:
        group['locations'].sort(key=lambda x: x['available'], reverse=True)
        for host in group['locations']:
            if host['available'] is True:
                statusemoji = '<center>⬆️ </center>'
                #statusemoji = '🟢'
                lastseen = ''
            elif host['available'] is False:
                # iso timestamp converted to yyyy/mm/dd
                lastseen = host['lastscrape'].split(' ')[0]
                statusemoji = '<center>⬇️ </center>'
                #statusemoji = '🔴'
            if host['title'] is not None:
                title = host['title'].replace('|', '-')
            else:
                title = ''
            screen = ''
            screenfile = 'screenshots/' + group['name'] + '-' + createfile(host['slug']) + '.png'
            if os.path.exists('source/' + screenfile):
                screen = '<a href="' +  screenfile + '">Screen</a>'
            line = '| [' + group['name'].title().replace(" ","") + '](/profiles?id=' + group['name'] + ') | ' + title + ' | ' + statusemoji + ' | ' + lastseen + ' | ' + host['fqdn'] + ' | ' + screen + ' |'
            writeline(index_sheet, line)

    groups = openjson('data/markets.json')
    writeline(index_sheet, '## 📚 Forums & Markets status')
    writeline(index_sheet, '')
    header = '| Group | Page title | Server status | Last seen | Location | Screen |'
    writeline(index_sheet, header)
    writeline(index_sheet, '|---|---|---|---|---|---|')
    groups.sort(key=lambda x: x["name"].lower())
    for group in groups:
        group['locations'].sort(key=lambda x: x['available'], reverse=True)
        for host in group['locations']:
            if host['available'] is True:
                statusemoji = '<center>⬆️ </center>'
                #statusemoji = '🟢'
                lastseen = ''
            elif host['available'] is False:
                # iso timestamp converted to yyyy/mm/dd
                lastseen = host['lastscrape'].split(' ')[0]
                statusemoji = '<center>⬇️ </center>'
                #statusemoji = '🔴'
            if host['title'] is not None:
                title = host['title'].replace('|', '-')
            else:
                title = ''
            screen = ''
            screenfile = 'screenshots/' + group['name'] + '-' + createfile(host['slug']) + '.png'
            if os.path.exists('source/' + screenfile):
                screen = '<a href="' +  screenfile + '">Screen</a>'
            line = '| [' + group['name'].title().replace(" ","")  + '](/#/markets?id=' + group['name'].replace(" ","-") + ') | ' + title + ' | ' + statusemoji + ' | ' + lastseen + ' | ' + host['fqdn'] + ' | ' + screen + ' |'
            writeline(index_sheet, line)

def sidebar():
    '''
    create a sidebar markdown report
    '''
    stdlog('generating sidebar')
    sidebar = 'docs/_sidebar.md'
    # delete contents of file
    with open(sidebar, 'w') as f:
        f.close()
    writeline(sidebar, '- [Home](README.md)')
    writeline(sidebar, '- [Recent posts](recentposts.md)')
    writeline(sidebar, '- [Status](status.md)')
    writeline(sidebar, '- [Group profiles](profiles.md)')
    writeline(sidebar, '- [Forums & Market](markets.md)')
    writeline(sidebar, '- [Stats & graphs](stats.md)')

    stdlog('sidebar generated')

def statspage():
    '''
    create a stats page in markdown containing the matplotlib graphs
    '''
    stdlog('generating stats page')
    statspage = 'docs/stats.md'
    # delete contents of file
    with open(statspage, 'w') as f:
        f.close()
    writeline(statspage, '')
    writeline(statspage, '_Timestamp association commenced october 21"_')
    writeline(statspage, '')
    writeline(statspage, '![](graphs/postsbyday.png)')
    writeline(statspage, '')
    writeline(statspage, '![](graphs/postsbygroup.png)')
    writeline(statspage, '')
    writeline(statspage, '![](graphs/grouppie.png)')
    stdlog('stats page generated')

def recentposts(top):
    '''
    create a list the last X posts (most recent)
    '''
    stdlog('finding recent posts')
    posts = openjson('data/posts.json')
    # sort the posts by timestamp - descending
    sorted_posts = sorted(posts, key=lambda x: x['discovered'], reverse=True)
    # create a list of the last X posts
    recentposts = []
    for post in sorted_posts:
        recentposts.append(post)
        if len(recentposts) == top:
            break
    stdlog('recent posts generated')
    return recentposts

def recentpage():
    '''create a markdown table for the last 100 posts based on the discovered value'''
    fetching_count = 100
    stdlog('generating recent posts page')
    recentpage = 'docs/recentposts.md'
    # delete contents of file
    with open(recentpage, 'w') as f:
        f.close()
    writeline(recentpage, '')
    writeline(recentpage, '_last `' + str(fetching_count) + '` posts_')
    writeline(recentpage, '')
    writeline(recentpage, '| Date | Title | Group |')
    writeline(recentpage, '|---|---|---|')
    # fetch the 100 most revent posts and add to ascending markdown table
    for post in recentposts(fetching_count):
        # show friendly date for discovered
        date = post['discovered'].split(' ')[0]
        # replace markdown tampering characters
        title = post['post_title'].replace('|', '-')
        group = post['group_name'].replace('|', '-')
        grouplink = '[' + group.title() + '](/profiles?id=' + group + ')'
        line = '| ' + date + ' | `' + title + '` | ' + grouplink + ' |'
        writeline(recentpage, line)
    stdlog('recent posts page generated')

def profilepage():
    '''
    create a profile page for each group in their unique markdown files within docs/profiles
    '''
    stdlog('generating profile pages')
    profilepage = 'docs/profiles.md'
    # delete contents of file
    modules = glob.glob(join(dirname('ransomlook/parsers/'), "*.py"))
    parserlist = [ basename(f)[:-3].split('.')[0] for f in modules if isfile(f) and not f.endswith('__init__.py')]
    with open(profilepage, 'w') as f:
        f.close()
    writeline(profilepage, '')
    groups = openjson('data/groups.json')
    groups.sort(key=lambda x: x["name"].lower())
    for group in groups:
        writeline(profilepage, '## ' + group['name'].title())
        writeline(profilepage, '')
        if group['captcha'] is True:
            writeline(profilepage, ':warning: _has a captcha_')
            writeline(profilepage, '')
        if group['name'] in parserlist:
            writeline(profilepage, '_parsing : `enabled`_')
            writeline(profilepage, '')
        else:
            writeline(profilepage, '_parsing : `disabled`_')
            writeline(profilepage, '')
        # add notes if present
        if group['meta'] is not None:
            writeline(profilepage, '_`' + group['meta'] + '`_')
            writeline(profilepage, '')
        if group['profile'] is not None:
            for profile in group['profile']:
                writeline(profilepage, '- ' + profile)
                writeline(profilepage, '')
        writeline(profilepage, '| Page Title | Available | Tor version | Last visit | Fqdn | Screen')
        writeline(profilepage, '|---|---|---|---|---|---|')        
        for host in group['locations']:
            # convert date to ddmmyyyy hh:mm
            date = host['lastscrape'].split(' ')[0]
            date = date.split('-')
            date = date[2] + '/' + date[1] + '/' + date[0]
            time = host['lastscrape'].split(' ')[1]
            time = time.split(':')
            time = time[0] + ':' + time[1]
            screen = ''
            screenfile = 'screenshots/' + group['name'] + '-' + createfile(host['slug']) + '.png'
            if os.path.exists('source/' + screenfile):
                screen = '<a href="' +  screenfile + '" rel="noopener noreferrer" target="_blank">Screen</a>'
            if host['available']== True:
                statusemoji = '<center>⬆️ </center>'
                #statusemoji = '🟢'
            else:
                statusemoji = '<center>⬇️ </center>'
                #statusemoji = '🔴'
            if host['title'] is not None:
                line = '| ' + host['title'].replace('|', '-') + ' | ' + statusemoji +  ' | ' + str(host['version']) + ' | ' + time + ' ' + date + ' | `' + host['fqdn'] + '` | ' + screen + ' |'
                writeline(profilepage, line)
            else:
                line = '| none | ' + statusemoji +  ' | ' + str(host['version']) + ' | ' + time + ' ' + date + ' | `' + host['fqdn'] + '` | ' + screen + ' |'
                writeline(profilepage, line)
        posts = openjson('data/posts.json')
        haspost=0
        sorted_posts = sorted(posts, key=lambda x: x['discovered'], reverse=True)
        for post in sorted_posts:
            if post['group_name'] == group['name']:
                if haspost==0:
                    haspost=1
                    writeline(profilepage, '')
                    writeline(profilepage, '| post | date |')
                    writeline(profilepage, '|---|---|')
                date = post['discovered'].split(' ')[0]
                date = date.split('-')
                date = date[2] + '/' + date[1] + '/' + date[0]
                line = '| ' + '`' + post['post_title'].replace('|', '') + '`' + ' | ' + date + ' |'
                writeline(profilepage, line)
        writeline(profilepage, '')
    stdlog('profile page generation complete')

def marketpage():
    '''
    create a profile page for each group in their unique markdown files within docs/profiles
    '''
    stdlog('generating profile pages')
    marketpage = 'docs/markets.md'
    modules = glob.glob(join(dirname('ransomlook/parsers/'), "*.py"))
    parserlist = [ basename(f)[:-3].split('.')[0] for f in modules if isfile(f) and not f.endswith('__init__.py')]
    # delete contents of file
    with open(marketpage, 'w') as f:
        f.close()
    writeline(marketpage, '')
    groups = openjson('data/markets.json')
    groups.sort(key=lambda x: x["name"].lower())
    for group in groups:
        writeline(marketpage, '## ' + group['name'].title())
        writeline(marketpage, '')
        if group['captcha'] is True:
            writeline(marketpage, ':warning: _has a captcha_')
            writeline(marketpage, '')
        if group['name'] is parserlist:
            writeline(marketpage, '_parsing : `enabled`_')
            writeline(marketpage, '')
        else:
            writeline(marketpage, '_parsing : `disabled`_')
            writeline(marketpage, '')
        # add notes if present
        if group['meta'] is not None:
            writeline(marketpage, '_`' + group['meta'] + '`_')
            writeline(marketpage, '')
        if group['profile'] is not None:
            for profile in group['profile']:
                writeline(marketpage, '- ' + profile)
                writeline(marketpage, '')
        writeline(marketpage, '| Page Title | Available | Tor version | Last visit | Fqdn | Screen')
        writeline(marketpage, '|---|---|---|---|---|---|')        
        for host in group['locations']:
            # convert date to ddmmyyyy hh:mm
            date = host['lastscrape'].split(' ')[0]
            date = date.split('-')
            date = date[2] + '/' + date[1] + '/' + date[0]
            time = host['lastscrape'].split(' ')[1]
            time = time.split(':')
            time = time[0] + ':' + time[1]
            screen = ''
            screenfile = 'screenshots/' + group['name'] +'-' + createfile(host['slug']) + '.png'
            if os.path.exists('source/' + screenfile):
                screen = '<a href="' +  screenfile + '" rel="noopener noreferrer" target="_blank">Screen</a>'
            if host['available']== True:
                statusemoji = '<center>⬆️ </center>'
                #statusemoji = '🟢'
            else:
                statusemoji = '<center>⬇️ </center>'
                #statusemoji = '🔴'
            if host['title'] is not None:
                line = '| ' + host['title'].replace('|', '-') + ' | ' + statusemoji +  ' | ' + str(host['version']) + ' | ' + time + ' ' + date + ' | `' + host['fqdn'] + '` | ' + screen + ' |'
                writeline(marketpage, line)
            else:
                line = '| none | ' + statusemoji +  ' | ' + str(host['version']) + ' | ' + time + ' ' + date + ' | `' + host['fqdn'] + '` | ' + screen + ' |'
                writeline(marketpage, line)
        posts = openjson('data/posts.json')
        haspost=0
        sorted_posts = sorted(posts, key=lambda x: x['discovered'], reverse=True)
        for post in sorted_posts:
            if post['group_name'] == group['name']:
                if haspost==0:
                    haspost=1
                    writeline(marketpage, '')
                    writeline(marketpage, '| post | date |')
                    writeline(marketpage, '|---|---|')
                date = post['discovered'].split(' ')[0]
                date = date.split('-')
                date = date[2] + '/' + date[1] + '/' + date[0]
                line = '| ' + '`' + post['post_title'].replace('|', '') + '`' + ' | ' + date + ' |'
                writeline(marketpage, line)
        writeline(marketpage, '')
    stdlog('profile page generation complete')

def main():
    stdlog('generating doco')
    mainpage()
    indexpage()
    sidebar()
    recentpage()
    statspage()
    profilepage()
    marketpage()
    # if posts.json has been modified within the last 45 mins, assume new posts discovered and recreate graphs
    if os.path.getmtime('data/posts.json') > (time.time() - (45 * 60)):
        stdlog('posts.json has been modified within the last 45 mins, assuming new posts discovered and recreating graphs')
        trend_posts_per_day()
        plot_posts_by_group()
        pie_posts_by_group()
    else:
        stdlog('posts.json has not been modified within the last 45 mins, assuming no new posts discovered')
