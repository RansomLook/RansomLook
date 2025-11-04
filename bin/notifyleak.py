#!/usr/bin/env python3
#from ransomlook import ransomlook
import json

import smtplib
import ssl
from email.message import EmailMessage

from typing import List, Dict

from datetime import date
from datetime import timedelta

import redis


from ransomlook.default.config import get_config, get_socket_path

def getnewbreach(date: str) -> List[Dict[str, str]] :
    '''
    check if a post already exists in posts.json
    '''
    red = redis.Redis(unix_socket_path=get_socket_path('cache'), db=4)
    notify = []
    for breaches in red.keys():
        breach = json.loads(red.get(breaches)) # type: ignore
        if breach['indexed'].split()[0] == date :
            notify.append(breach)
    return notify

def main() -> None :

    email_config = get_config('generic','email')
    smtp_auth = get_config('generic', 'email_smtp_auth')
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


