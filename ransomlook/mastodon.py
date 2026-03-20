#!/usr/bin/env python3
from typing import Any

from mastodon import Mastodon

from .sharedutils import errlog


def tootnotify(config: dict[str, Any], group: str, title: str, siteurl: str) -> None:
    """
    Posting message to Mastodon
    """
    try:
        m = Mastodon(access_token=config["token"], api_base_url=config["url"])
        m.toot(
            "New post from #"
            + group.title()
            + " : "
            + title.title()
            + "\nMore at : "
            + siteurl
            + "/group/"
            + group.title().replace(" ", "%20")
            + " #Ransomware"
        )
    except Exception:
        errlog("Can not toot :(")


def tootnotifyleak(config: dict[str, Any], name: str) -> None:
    """
    Posting message to Mastodon
    """
    try:
        m = Mastodon(access_token=config["token"], api_base_url=config["url"])
        m.toot("New #leak detected : " + name.title())
    except Exception:
        errlog("Can not toott :(")
