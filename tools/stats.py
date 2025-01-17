#!/usr/bin/env python3
import valkey # type: ignore
import os
from ransomlook.default import get_socket_path, get_config

import json
import csv
import datetime

from typing import Dict

f = open('stats.csv','w')
header = ['Group', '01', '02', '03', '04', '05', '06', '07', '08', '09', '10', '11', '12']
writer = csv.writer(f)
writer.writerow(header)


valkey_handle = valkey.Valkey(unix_socket_path=get_socket_path('cache'), db=2)

postnum: Dict[bytes, Dict[str, int]] = {}
for key in valkey_handle.keys():
    postnum[key]={}
    posts =json.loads(valkey_handle.get(key)) 
    for post in posts:
        if post['discovered'][:7] not in postnum[key]:
            postnum[key][post['discovered'][:7]]=1
        else :
            postnum[key][post['discovered'][:7]]+=1

    row = []
    row.append(key.decode())

    for i in range(1,13):
        x = datetime.datetime(2022, i,1).strftime("%Y-%m")
        if x in postnum[key] :
            row.append(str(postnum[key][x]))
        else :
            row.append('0')
    writer.writerow(row)
