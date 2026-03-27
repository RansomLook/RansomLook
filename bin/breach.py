#!/usr/bin/env python3
import argparse
import json
import logging

import requests
import valkey
from bs4 import BeautifulSoup

from ransomlook.default import DB_LEAKS, get_config, get_socket_path
from ransomlook.default.logging import get_logger
from ransomlook.mastodon import tootnotifyleak
from ransomlook.rocket import rocketnotifyleak

logger = get_logger("breach")


def main() -> None:
    parser = argparse.ArgumentParser(description="Check for new data breaches")
    parser.add_argument("--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"], default=None, help="Override log level")
    args = parser.parse_args()

    if args.log_level:
        level = getattr(logging, args.log_level)
        logging.getLogger().setLevel(level)
        for handler in logging.getLogger().handlers:
            handler.setLevel(level)
    url = "https://leak-lookup.com/breaches/stats"
    source = "https://leak-lookup.com/breaches"

    red = valkey.Valkey(unix_socket_path=get_socket_path("cache"), db=DB_LEAKS)
    keys = red.keys()
    res = requests.get(source)
    soup = BeautifulSoup(res.text, "html.parser")
    divs_name = soup.find("table", {"id": "datatables-indexed-breaches"})
    tbody = divs_name.find("tbody")  # type: ignore[union-attr]
    trs = tbody.find_all("tr")  # type: ignore[union-attr]
    rocketconfig = get_config("generic", "rocketchat")
    mastodonconfig = get_config("generic", "mastodon")
    for tr in trs:
        tds = tr.find_all("td")
        data = tds[3].div.div.a["data-id"]
        if data.encode() in keys:  # type: ignore[operator]
            continue
        x = requests.post(url, data={"id": data})
        datas = x.json()
        fields = BeautifulSoup(datas["columns"], "html.parser")
        spans = fields.find_all("span")
        columns = []
        for span in spans:
            columns.append(span.text.strip())
        datas["columns"] = columns
        datas["meta"] = ""
        datas["location"] = []
        red.set(data, json.dumps(datas))
        if rocketconfig["enable"] == True:
            rocketnotifyleak(rocketconfig, datas)
        if mastodonconfig["enable"] == True:
            tootnotifyleak(mastodonconfig, datas["name"])
    logger.info("done")
