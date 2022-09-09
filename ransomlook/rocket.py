#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
RocketChat module
'''
from rocketchat_API.rocketchat import RocketChat # type: ignore

def rocketnotify(config, group, post) -> None :
    '''
    Posting message to RocketChat
    '''
    rocket = RocketChat(user_id=config['user_id'], auth_token=config['auth_token'], \
        server_url=config['server'], ssl_verify=config['ssl_verify'])
    rocket.chat_post_message('New post from '+group+' : '+post, room_id=config['channel_name'])
