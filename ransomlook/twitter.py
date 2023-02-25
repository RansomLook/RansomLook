#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import json
import queue
from threading import Thread, Lock
from datetime import datetime
import time
from typing import Dict
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

from .default.config import get_config, get_homedir, get_socket_path

import tweepy # type: ignore

from .sharedutils import striptld
from .sharedutils import openjson
from .sharedutils import siteschema
from .sharedutils import stdlog, errlog
from .sharedutils import createfile

from bs4 import BeautifulSoup

import redis

def twitternotify(config, group, title) -> None :
    '''
    Posting message to Twitter
    '''
    try:
        client = tweepy.Client(
             consumer_key=config['consumer_key'], consumer_secret=config['consumer_secret'],
             access_token=config['access_token'], access_token_secret=config['access_token_secret']
        )
        client.create_tweet(text="New post from " + group.title() + " : " + title.title())
    except:
        errlog('Can not tweet :(')

def twitternotifyleak(config, name) -> None :
    '''
    Posting message to Twitter
    '''
    try:
        client = tweepy.Client(
             consumer_key=config['consumer_key'], consumer_secret=config['consumer_secret'],
             access_token=config['access_token'], access_token_secret=config['access_token_secret']
        )
        client.create_tweet(text="New data breach detected " + name.title())
    except:
        errlog('Can not tweet :(')

def parser() -> None :
    red = redis.Redis(unix_socket_path=get_socket_path('cache'), db=8)
    redmessage = redis.Redis(unix_socket_path=get_socket_path('cache'), db=9)
    for key in red.keys():
        #try:
           html_doc='source/twitter/'+ key.decode() + '.html'
           file=open(html_doc,'r')
           soup = BeautifulSoup(file,'html.parser')
           profile = json.loads(red.get(key)) # type: ignore
           name =  soup.find('div',{'data-testid':'UserName'}) 
           profile['displayname'] = name.div.div.div.text # type: ignore
           description = soup.find('div', {'data-testid':'UserDescription'})
           if description != None:
               profile['meta'] = description.text # type: ignore
           location = soup.find('span',{'data-testid':'UserLocation'})
           if location != None:
               profile['location'] = location.text # type: ignore
           website = soup.find('a',{'data-testid':'UserUrl'})
           if website != None:
               profile['link'] = website.text # type: ignore
           join_date =soup.find('span',{'data-testid':'UserJoinDate'}).text # type: ignore
           profile['joindate'] = join_date
           profile['following'] = soup.find('span', text = "Following").parent.span.text # type: ignore
           profile['followers'] = soup.find('span', text = "Followers").parent.span.text # type: ignore
           red.set(key,json.dumps(profile))
           tweets = soup.find_all('article',{'data-testid':'tweet'})
           if key in redmessage.keys():
               posts = json.loads(redmessage.get(key)) # type: ignore
           else:
               posts={}
           for tweet  in tweets:
               author = tweet.find('div',{'data-testid':'User-Names'}).find('span').text
               timestamp = tweet.find('div',{'data-testid':'User-Names'}).find('time')['datetime']
               message = tweet.find('div',{'data-testid':'tweetText'}).text
               if timestamp not in posts:
                   posts.update({timestamp:[author,message]})
           redmessage.set(key,json.dumps(posts))

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
                context = browser.new_context(ignore_https_errors= True )
                page = context.new_page()
                link='https://www.twitter.com/'+host
                page.goto(link, wait_until='load', timeout = 60000)
                page.bring_to_front()
                page.wait_for_timeout(1000)
                page.mouse.move(x=500, y=400)
                page.wait_for_load_state('networkidle')
                page.mouse.wheel(delta_y=2000, delta_x=0)
                page.wait_for_load_state('networkidle')
                page.wait_for_timeout(1000)
                filename = host + '.html'
                name = os.path.join(os.getcwd(), 'source/twitter', filename)
                with open(name, 'w', encoding='utf-8') as sitesource:
                    sitesource.write(page.content())
                    sitesource.close()

                filename = host + '.png'
                name = os.path.join(get_homedir(), 'source/screenshots/twitter', filename)
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
    red = redis.Redis(unix_socket_path=get_socket_path('cache'), db=8)
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


def twiadder(name, link):
    red = redis.Redis(unix_socket_path=get_socket_path('cache'), db=8)
    try:
        data = {
            'name': name,
            'meta': None,
            'link': None,
            'displayname': None,
            'location': None,
            'joindate': None,
            'followers': None,
            'following': None
        }
        red.set(name, json.dumps(data))
        return 1
    except:
        return 0
