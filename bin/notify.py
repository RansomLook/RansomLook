#!/usr/bin/env python3
#from ransomlook import ransomlook
import json

import smtplib
import ssl
from email.message import EmailMessage

from typing import List, Any, Dict

from datetime import date
from datetime import timedelta

import valkey # type: ignore

from collections import defaultdict

from ransomlook.sharedutils import dbglog, stdlog
from ransomlook.default.config import get_config, get_socket_path

def getnewpost(date: str) -> Dict[str, List[str]] :
    '''
    check if a post already exists in posts.json
    '''
    valkey_handle = valkey.Valkey(unix_socket_path=get_socket_path('cache'), db=2)
    notify = defaultdict(list)
    for group in valkey_handle.keys():
        posts = json.loads(valkey_handle.get(group))
        for post in posts:
            if post['discovered'].split()[0] == date :
                notify[group.decode()].append(post['post_title'])
    ret =  dict(sorted(notify.items()))
    return ret

def main() -> None :

    email_config = get_config('generic','email')
    smtp_auth = get_config('generic', 'email_smtp_auth')
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
            with smtplib.SMTP(host=email_config['smtp_server'], port=email_config['smtp_port']) as server:
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


if __name__ == '__main__':
    main()


