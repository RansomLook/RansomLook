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

def getnewbreach(date: str) -> Dict :
    '''
    check if a post already exists in posts.json
    '''
    red = redis.Redis(unix_socket_path=get_socket_path('cache'), db=4)
    notify = []
    for breaches in red.keys():
        breach = json.loads(red.get(breaches))
        if breach['indexed'].split()[0] == date :
            notify.append(breach)
    return notify

def main() -> None :

    email_config = get_config('generic','email')
    newposts = getnewbreach(str(date.today() - timedelta(days =1)))
    if newposts == []:
        print('No new post')
        return
    message = '''Hello

Please find the list of databreach detected on : '''
    message += str((date.today() - timedelta(days =1)).strftime("%d-%m-%Y"))+'.\n'
    for entry in newposts:
        message+="\n"+entry['name']+" :\n"
        message+="Size             : "+ entry['size'] +"\n"
        message+="Records          : "+ entry['records'] +"\n"
        message+="Compromised data : "+ str(entry['columns']) +"\n"

    message += "\nBest regards,\n\nRansomlook Team"

    fromaddr = email_config['from']
    toaddrs = email_config['to']
    subject = "DataBreach detected"
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


