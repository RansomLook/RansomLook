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
from typing import Dict, List, Any
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from playwright_stealth import Stealth # type: ignore

from .default.config import get_config, get_homedir, get_socket_path

import uuid
import redis

import smtplib
import ssl
from email.message import EmailMessage

from .sharedutils import striptld
from .sharedutils import siteschema
from .sharedutils import stdlog, errlog
from .sharedutils import createfile

import requests, shutil

from bs4 import BeautifulSoup
from googletrans import Translator # type: ignore

import re

def alertingnotify(config: Dict[str, Any], group: bytes, description: str, keyword: List[str], timestamp: str) -> None :
    '''
    Posting message to RocketChat
    '''
    translator = Translator()

    smtp_auth = get_config('generic', 'email_smtp_auth')
    message = """Hello,
A new message in telegram is matching your keywords:
"""
    message += str(keyword) +'\n'
    message += 'Channel : ' + group.decode() +'\nTimestamp : ' + timestamp+ '\nMessage : ' + description
    if translator.detect(description).lang != 'en' :
        try :
            message += '\n\nTranslated : ' + translator.translate(description, dest='en').text
        except :
            message += '\n\nError while translating'
    fromaddr = config['from']
    toaddrs = config['to']
    subject = "[RansomLook] New post matching your keywords"
    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = fromaddr
    msg['To'] = ', '.join(toaddrs)
    msg.set_content(message)
    try:
            with smtplib.SMTP(host=config['smtp_server'], port=config['smtp_port']) as server:
                if smtp_auth['auth']:
                    if 'smtp_use_tls' in smtp_auth:
                        print('please change the config name from smtp_use_tls to smtp_use_starttls')
                    if smtp_auth.get('smtp_use_tls') is True or smtp_auth['smtp_use_starttls']:
                        if smtp_auth['verify_certificate'] is False:
                            ssl_context = ssl.create_default_context()
                            ssl_context.check_hostname = False
                            ssl_context.verify_mode = ssl.CERT_NONE
                            server.starttls(context=ssl_context)
                        else:
                            server.starttls()
                    server.login(smtp_auth['smtp_user'], smtp_auth['smtp_pass'])
                server.send_message(msg)
                server.quit()
    except smtplib.SMTPException as e:
        print(e)
    except Exception as e: print(e)

def threadscape(queuethread, lock): # type: ignore
    '''
    Thread used to scrape our website
    '''
    #with sync_playwright() as play:
    with Stealth().use_sync(sync_playwright()) as play:
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

def parser() -> None:
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
                       imagelink= re.findall(r"https://cdn?.*.*.jpg", img['style'])[0]
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
                      for keywordfull in listkeywords:
                          keyword = keywordfull.split('|')[0]
                          if keyword.lower() in message.lower():
                              matching.append(keyword)
                      if matching :
                          alertingnotify(emailconfig, key, message, matching, timestamp)
                          alertdb = redis.Redis(unix_socket_path=get_socket_path('cache'), db=12)
                          uuidkey = str(uuid.uuid4())
                          value = {'type': 'telegram', 'group_name': key.decode(), 'description': message, 'matching': matching}
                          alertdb.set(uuidkey,json.dumps(value))
                          alertdb.expire(uuidkey, 60 * 60 * 24)
               except Exception as e:
                   print('error with the channel:'+key.decode())
           redmessage.set(key,json.dumps(posts))
        except:
           print('error with :'+key.decode())
           continue

def teladder(name: str, link: str) -> int:
    red = redis.Redis(unix_socket_path=get_socket_path('cache'), db=5)
    try:
        data = {
            'name': name.strip(),
            'meta': None,
            'link': link.strip()
        }
        red.set(name, json.dumps(data))
        return 1
    except:
        return 0
