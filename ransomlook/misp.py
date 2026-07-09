#!/usr/bin/env python3
"""
Misp module
"""

from datetime import datetime
from typing import Any

from pymisp import MISPEvent, MISPObject, PyMISP

from .sharedutils import errlog


def mispevent(config: dict[str, Any], group: str, title: str, description: str, galaxyname: str) -> None:
    """
    Creating a new event into misp
    """
    try:
        misp = PyMISP(url=config["url"], key=config["apikey"], ssl=config["tls_verify"])

    except Exception as e:
        errlog(f"Can not connect to MISP: {e}")

    misp_object = MISPObject("ransomware-group-post")
    misp_object.add_attribute("title", title)
    misp_object.add_attribute("date", str(datetime.now()))
    if description is not None:
        misp_object.add_attribute("description", description)
    event = MISPEvent()
    event.info = group.title() + " new post : " + title
    event.add_object(misp_object)
    if config["publish"]:
        event.publish()
    if galaxyname is not None and galaxyname != "":
        event.add_tag('misp-galaxy:Ransomware="' + galaxyname + '"')
    misp.add_event(event, pythonify=True)


def push_event(config: dict[str, Any], event: MISPEvent) -> None:
    """
    Create or update (upsert by uuid) an event on the MISP instance.
    Used by the local feed so the pushed event shares the feed event uuid and
    gets updated whenever the victim is completed (screenshot, edit, ...).
    """
    try:
        misp = PyMISP(url=config["url"], key=config["apikey"], ssl=config["tls_verify"])
        if config.get("publish"):
            event.publish()
        existing = misp.get_event(event.uuid, pythonify=True)
        if isinstance(existing, MISPEvent):
            misp.update_event(event)
        else:
            misp.add_event(event, pythonify=True)
    except Exception as e:
        errlog("Can not push event to MISP: " + str(e))


def delete_event(config: dict[str, Any], event_uuid: str) -> None:
    """
    Delete an event from the MISP instance by uuid.
    """
    try:
        misp = PyMISP(url=config["url"], key=config["apikey"], ssl=config["tls_verify"])
        misp.delete_event(event_uuid)
    except Exception as e:
        errlog("Can not delete event from MISP: " + str(e))
