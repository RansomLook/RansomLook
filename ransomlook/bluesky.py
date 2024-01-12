#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import requests
from .sharedutils import errlog
from datetime import datetime, timezone

from typing import Dict

def blueskynotify(config: Dict['str','str'], group: str, title: str, siteurl: str) -> None :
    '''
    Posting message to bluesky
    '''
    try:
        BLUESKY_HANDLE = config['BLUESKY_HANDLE']
        BLUESKY_APP_PASSWORD = config['BLUESKY_APP_PASSWORD']
        url = config['url']
        resp = requests.post(url,
                   json={"identifier": BLUESKY_HANDLE, "password": BLUESKY_APP_PASSWORD},
               )
        resp.raise_for_status()
        session = resp.json()
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        text= "New post from #" + group.title() + " : " + title.title() + "\nMore at : "
        startoffset = len(text)
        uri = siteurl + "/group/" + group.title().replace(" ","%20")
        text+= uri
        endoffset = len(text)
        text+= " #Ransomware"

        # Required fields that each post must include
        post = {
            "$type": "app.bsky.feed.post",
            "text": text,
            "createdAt": now,
            "facets": [{
                        "index": {
                          "byteStart": startoffset,
                          "byteEnd": endoffset,
                         },
                         "features": [{
                           "$type": "app.bsky.richtext.facet#link",
                           "uri": uri,
                          }],
                      }],
        }
        resp = requests.post("https://bsky.social/xrpc/com.atproto.repo.createRecord",
                   headers={"Authorization": "Bearer " + session["accessJwt"]},
                   json={
                       "repo": session["did"],
                       "collection": "app.bsky.feed.post",
                       "record": post,
                      },
               )
    except:
        errlog('Can not post :(')


