#!/usr/bin/env python3
import redis
import os
from ransomlook.default import get_socket_path, get_config

from ransomlook.rocket import rocketnotifyleak
from ransomlook.twitter import twitternotifyleak
from ransomlook.mastodon import mastodonnotifyleak

from bs4 import BeautifulSoup
import requests
import json

url = 'https://leak-lookup.com/breaches/stats'
source = 'https://leak-lookup.com/breaches'

red = redis.Redis(unix_socket_path=get_socket_path('cache'), db=4)
keys = red.keys()
res = requests.get(source)
soup=BeautifulSoup(res.text,'html.parser')
divs_name=soup.find('table', {"id": "datatables-indexed-breaches"})
tbody = divs_name.find('tbody') # type: ignore
trs = tbody.find_all('tr') # type: ignore
rocketconfig = get_config('generic','rocketchat')
twitterconfig = get_config('generic','twitter')
mastodonconfig = get_config('generic','mastodon')
for tr in trs:
  tds= tr.find_all('td')
  data = tds[3].div.div.a['data-id']
  if data.encode() in keys:
    continue
  x = requests.post(url, data={'id':data})
  datas=x.json()
  fields = BeautifulSoup(datas['columns'],'html.parser')
  spans = fields.find_all('span')
  columns=[]
  for span in spans:
    columns.append(span.text.strip())
  datas['columns']=columns
  datas['meta']=''
  datas['location']=[]
  red.set(data,json.dumps(datas))
  if rocketconfig['enable'] == True:
    rocketnotifyleak(rocketconfig, datas)
  if twitterconfig['enable'] == True:
    twitternotifyleak(twitterconfig, datas['name'])
  if mastodonconfig['enable'] == True:
    tootnotifyleak(mastodonconfig, datas['name'])
print('done')
