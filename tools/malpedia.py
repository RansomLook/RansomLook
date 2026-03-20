#!/usr/bin/env python3
import json

import requests
import valkey

from ransomlook.default import DB_GROUPS, get_config, get_socket_path

red = valkey.Valkey(unix_socket_path=get_socket_path("cache"), db=DB_GROUPS)

malpedia = get_config("generic", "malpedia")
if malpedia == "":
    print("No APIKEY for Malpedia")
    exit(0)

response = requests.get(
    "https://malpedia.caad.fkie.fraunhofer.de/api/get/families", headers={"Authorization": "apitoken " + malpedia}
)
if response.status_code != 200:
    print(response.text)
    exit(0)

families = json.loads(response.text)

keys = red.keys()
for family in families:
    names = []
    names.append(families[family]["common_name"])
    names.extend(families[family]["alt_names"])
    names = [x.lower() for x in names]
    for key in keys:  # type: ignore[union-attr]
        if key.decode().lower() in names:
            for alter in families[family]["alt_names"]:
                print(alter)
            for url in families[family]["urls"]:
                print(url)
            group = json.loads(red.get(key))  # type: ignore[arg-type]
            group["meta"] = families[family]["description"]
            group["profile"].extend(families[family]["urls"])
            red.set(key, json.dumps(group))
