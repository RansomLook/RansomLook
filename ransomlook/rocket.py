#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
RocketChat module
'''
from rocketchat_API.rocketchat import RocketChat # type: ignore
from .sharedutils import errlog
from typing import Dict, Any

def rocketnotify(config: Dict[str, Any], group: str, title: str, description: str) -> None :
    '''
    Posting message to RocketChat
    '''
    try:
        rocket = RocketChat(user_id=config['user_id'], auth_token=config['auth_token'], \
            server_url=config['server'], ssl_verify=config['ssl_verify'])
        rocket.chat_post_message('New post from '+group+' : '+ title + ' => ' + description, room_id=config['channel_name'])
    except:
        errlog('Can not connect to Rocket')

def rocketnotifyleak(config: Dict[str, Any], datas: Dict[str, Any]) -> None :
    try:
        rocket = RocketChat(user_id=config['user_id'], auth_token=config['auth_token'], \
            server_url=config['server'], ssl_verify=config['ssl_verify'])
        rocket.chat_post_message('New DataBreach leak detected ' + datas['name'] + " : " + str(datas['columns']), room_id=config['channel_name'])
    except:
        errlog('Can not connect to Rocket')

def rocketnotifyrf(config: Dict[str, Any], datas: Dict[str, str]) -> None :
    try:
        rocket = RocketChat(user_id=config['user_id'], auth_token=config['auth_token'], \
            server_url=config['server'], ssl_verify=config['ssl_verify'])
        rocket.chat_post_message('New Recorded Future Dump ' + datas['name'] + " : " + datas['description'], room_id=config['channel_name'])
    except:
        errlog('Can not connect to Rocket')

