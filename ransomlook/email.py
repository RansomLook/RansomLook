#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
Alerting module
'''
import smtplib
from email.message import EmailMessage

from .sharedutils import errlog

def alertingnotify(config, group, title, description, keyword) -> None :
    '''
    Posting message to RocketChat
    '''
    message = """Hello,

A new post is matching your keywords:
"""
    message += str(keyword) +'\n'
    message += group + '\n' + title + '\n' + description 
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
