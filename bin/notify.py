#!/usr/bin/env python3
#from ransomlook import ransomlook
import json

import smtplib
from email.message import EmailMessage

from typing import List, Any, Dict

from datetime import date
from datetime import timedelta

import redis

from collections import defaultdict

from ransomlook.sharedutils import dbglog, stdlog
from ransomlook.default.config import get_config, get_socket_path

def getnewpost(date: str) -> Dict :
    '''
    check if a post already exists in posts.json
    '''
    red = redis.Redis(unix_socket_path=get_socket_path('cache'), db=2)
    notify = defaultdict(list)
    for group in red.keys():
        posts = json.loads(red.get(group))
        for post in posts:
            if post['discovered'].split()[0] == date :
                notify[group.decode()].append(post['post_title'])
    notify =  dict(sorted(notify.items()))
    return notify

def main() -> None :

    email_config = get_config('generic','email')
    
    newposts = getnewpost(str(date.today() - timedelta(days =1)))
    if newposts == {}:
        print('No new post')
        return
    message = email_config['message_head']
    message += str((date.today() - timedelta(days =1)).strftime("%d-%m-%Y"))+'.\n'

    for key in newposts:
        message+="\n"+key+" :\n"
        for entry in newposts[key]:
            message+="* "+ entry +"\n"

    message += email_config['message_foot']

    fromaddr = email_config['from']
    toaddrs = email_config['to']
    toaddrsbcc = email_config['to_bcc']
    subject = email_config['subject']
    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = fromaddr
    msg['To'] = ', '.join(toaddrs)
    msg['Bcc'] = ', '.join(toaddrsbcc)
    msg.set_content(message)
    try:
         server = smtplib.SMTP(email_config['smtp_server'],email_config['smtp_port'])
         server.send_message(msg)
         server.quit()
    except smtplib.SMTPException as e:
        print(e)


if __name__ == '__main__':
    main()


