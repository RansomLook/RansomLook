#!/usr/bin/env python3
import valkey
import requests
from collections import defaultdict
import json

from ransomlook.default import get_socket_path, get_config



def main() -> None:
    print("Getting CryptoCurrency Transactions")
    response =  requests.get('https://api.ransomwhe.re/export')
    if response.status_code != 200:
        print(response.text)
        exit(0)
    crypto = response.json()
    cryptolist= defaultdict(list)
    for account in crypto["result"]:
        cryptolist[account['family']].append(account)

    valkey_handle = valkey.Valkey(unix_socket_path=get_socket_path('cache'), db=7)
    for key in cryptolist:
        valkey_handle.set(key, json.dumps(cryptolist[key]))

if __name__ == '__main__':
    main()

