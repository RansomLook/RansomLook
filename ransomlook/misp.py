#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
Misp module
'''
from pymisp import MISPObject, MISPEvent, PyMISP, MISPGalaxy # type: ignore[attr-defined]
from .sharedutils import errlog
from datetime import datetime
import json

from typing import Dict, Any

def mispevent(config: Dict[str, Any], group: str, title: str, description: str, galaxyname: str) -> None :
    '''
    Creating a new event into misp
    '''
    try:
        misp = PyMISP(url=config['url'], key=config['apikey'], ssl=config['tls_verify'])

    except Exception as e:
        errlog(f'Can not connect to MISP: {e}')

    misp_object = MISPObject('ransomware-group-post')
    misp_object.add_attribute('title', title)
    misp_object.add_attribute('date',str(datetime.now()))
    if description is not None:
        misp_object.add_attribute('description', description)
    event = MISPEvent()
    event.info = group.title() + ' new post : ' + title
    event.add_object(misp_object)
    if config['publish']:
        event.publish() # type: ignore[no-untyped-call]
    if galaxyname != None and galaxyname != "" :
        event.add_tag('misp-galaxy:Ransomware=\"'+galaxyname+'\"')
    pushedevent = misp.add_event(event, pythonify=True )
