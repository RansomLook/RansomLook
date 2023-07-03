#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import mastodon # type: ignore
from mastodon import Mastodon

from .sharedutils import errlog

def tootnotify(config, group, title, siteurl) -> None :
    '''
    Posting message to Mastodon
    '''
    try:
        m = Mastodon(access_token=config['token'], api_base_url=config['url'])
        m.toot("New post from " + group.title() + " : " + title.title() + "\nMore at : "+ siteurl + "/group/" + group.title())
    except:
        errlog('Can not toot :(')

def tootnotifyleak(config, name) -> None :
    '''
    Posting message to Mastodon
    '''
    try:
        m = Mastodon(access_token=config['token'], api_base_url=config['url'])
        m.toot("New leak detected : " + name.title())
    except:
        errlog('Can not toott :(')

