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

import smtplib
from email.message import EmailMessage

from .sharedutils import striptld
from .sharedutils import openjson
from .sharedutils import siteschema
from .sharedutils import stdlog, errlog
from .sharedutils import createfile

import requests, shutil

from bs4 import BeautifulSoup
from googletrans import Translator # type: ignore

import re

def alertingnotify(config, group, description, keyword, timestamp) -> None :
    '''
    Posting message to RocketChat
    '''
    translator = Translator()

    message = """Hello,
A new message in telegram is matching your keywords:
"""
    message += str(keyword) +'\n'
    message += 'Channel : ' + group.decode() +'\nTimestamp : ' + timestamp+ '\nMessage : ' + description
    if translator.detect(description).lang != 'en' :
        message += '\n\nTranslated : ' + translator.translate(description, dest='en').text
    fromaddr = config['from']
    toaddrs = config['to']
    subject = "[RansomLook] New post matching your keywords"
    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = fromaddr
    msg['To'] = ', '.join(toaddrs)
    msg.set_content(message)
    try:
        server = smtplib.SMTP(config['smtp_server'],config['smtp_port'])
        server.send_message(msg)
        server.quit()
    except smtplib.SMTPException as e:
        print(e)
    except Exception as e: print(e)

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
        group = json.loads(red.get(key)) # type: ignore
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

def parser():
    '''parsing telegram'''
    red = redis.Redis(unix_socket_path=get_socket_path('cache'), db=5)
    redmessage = redis.Redis(unix_socket_path=get_socket_path('cache'), db=6)
    redmatch = redis.Redis(unix_socket_path=get_socket_path('cache'), db=1)
    emailconfig = get_config('generic', 'email')

    keywords = redmatch.get('keywords')
    listkeywords = []
    if keywords is not None:
        listkeywords = keywords.decode().splitlines()

    for key in red.keys():
        try:
           html_doc='source/telegram/'+ key.decode() + '.html'
           file=open(html_doc,'r')
           soup = BeautifulSoup(file,'html.parser')
           titletag = soup.find('title')
           title = titletag.string # type: ignore
           data = json.loads(red.get(key)) # type: ignore
           data['meta']=title
           red.set(key, json.dumps(data))
           tgpost =  soup.find_all('div', {'class' : 'tgme_widget_message'})
           if key in redmessage.keys():
               posts = json.loads(redmessage.get(key)) # type: ignore
           else:
               posts={}
           for content in tgpost:
               try:
                   message = content.find('div', {'class':'tgme_widget_message_text'})
                   if message is not None:
                       message = message.text
                   imgs=[]
                   imglist = content.find_all('a',{'class':'tgme_widget_message_photo_wrap'})
                   for img in imglist:
                       imagelink= re.findall(r"https://cdn4.*.*.jpg", img['style'])[0]
                       image= img["href"].split('/')[-1]
                       response = requests.get(imagelink, stream=True)
                       imgs.append(image)
                       with open('source/screenshots/telegram/img/'+key.decode()+'-'+image+'.jpg','wb') as out_file:
                           shutil.copyfileobj(response.raw, out_file)
                       del response
                   timestamp = content.find('time', {'class' : 'time'})['datetime']
                   matching = []
                   if timestamp not in posts:
                      posts.update({timestamp:{'message':message,'image':imgs}})
                      for keyword in listkeywords:
                          if keyword.lower() in message.lower():
                              matching.append(keyword)
                      if matching :
                          alertingnotify(emailconfig, key, message, matching, timestamp)
               except Exception as e:
                   print(e)
                   print(img)
                   print('error with the channel:'+key.decode())
           redmessage.set(key,json.dumps(posts))
        except:
           print('error with :'+key.decode())
           continue
    print("ok")

def teladder(name, link):
    red = redis.Redis(unix_socket_path=get_socket_path('cache'), db=5)
    try:
        data = {
            'name': name,
            'meta': None,
            'link': link
        }
        red.set(name, json.dumps(data))
        return 1
    except:
        return 0
