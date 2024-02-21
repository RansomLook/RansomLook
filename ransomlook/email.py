#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
Alerting module
'''
import smtplib
import ssl
from email.message import EmailMessage

from .sharedutils import errlog
from .default import get_config

from typing import Dict, Any, List

def alertingnotify(config: Dict[str, Any], group: str, title: str, description: str, keyword: List[str]) -> None :
    '''
    Posting message to RocketChat
    '''
    message = """Hello,

A new post is matching your keywords:
"""
    smtp_auth = get_config('generic', 'email_smtp_auth')

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
