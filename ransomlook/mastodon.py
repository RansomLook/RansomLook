#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import mastodon
from mastodon import Mastodon

from .sharedutils import errlog

from typing import Dict, Any

def tootnotify(config: Dict[str, Any], group: str, title: str, siteurl: str) -> None :
    '''
    Posting message to Mastodon
    '''
    try:
        m = Mastodon(access_token=config['token'], api_base_url=config['url'])
        m.toot("New post from #" + group.title() + " : " + title.title() + "\nMore at : "+ siteurl + "/group/" + group.title().replace(" ","%20") + " #Ransomware")
    except:
        errlog('Can not toot :(')

def tootnotifyleak(config: Dict[str, Any], name: str) -> None :
    '''
    Posting message to Mastodon
    '''
    try:
        m = Mastodon(access_token=config['token'], api_base_url=config['url'])
        m.toot("New #leak detected : " + name.title())
    except:
        errlog('Can not toott :(')

