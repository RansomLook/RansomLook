#!/usr/bin/env python3
#from ransomlook import ransomlook
import json

import smtplib
from email.message import EmailMessage

from datetime import date
from datetime import timedelta

from collections import defaultdict

from ransomlook.sharedutils import openjson
from ransomlook.sharedutils import dbglog, stdlog
from ransomlook.default.config import get_config

def getnewpost(date):
    '''
    check if a post already exists in posts.json
    '''
    posts = openjson('data/posts.json')
    notify = defaultdict(list)
    for post in posts:
        if post['discovered'].split()[0] == date :
            notify[post['group_name']].append(post['post_title'])
    return notify

def main():

    email_config = get_config('generic','email')
    
    newposts = getnewpost(str(date.today() - timedelta(days =1)))
    if newposts == {}:
        print('No new post')
        return
    message = u"""\
Hello,

Please check the new entries in RansomLook: 
"""
    for key in newposts:
        message+="\n"+key+" :\n"
        for entry in newposts[key]:
            message+="* "+ entry +"\n"

    message += "\nBest regards"

    fromaddr = email_config['from']
    toaddrs = email_config['to']
    subject = 'New Notification from RansomLook'

    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = fromaddr
    msg['To'] = ', '.join(toaddrs)
    msg.set_content(message)
    try:
         server = smtplib.SMTP(email_config['smtp_server'],email_config['smtp_port'])
         server.send_message(msg)
         server.quit()
    except smtplib.SMTPException as e:
        print(e)


if __name__ == '__main__':
    main()


