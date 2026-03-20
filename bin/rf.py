import json

import requests
import valkey

from ransomlook.default import DB_RF
from ransomlook.default.config import get_config, get_socket_path
from ransomlook.default.logging import get_logger
from ransomlook.rocket import rocketnotifyrf

logger = get_logger("rf")


def main() -> None:

    red = valkey.Valkey(unix_socket_path=get_socket_path("cache"), db=DB_RF)
    keys = red.keys()

    rocketconfig = get_config("generic", "rocketchat")

    rftoken = get_config("generic", "rf")

    header = {"x-RFToken": rftoken, "Content-Type": "application/json"}

    query = {"names": [""], "limit": 10000}

    r_details = requests.post(
        "https://api.recordedfuture.com/identity/metadata/dump/search", headers=header, json=query
    )
    temp = r_details.json()

    for entry in temp["dumps"]:
        next = False
        for key in keys:  # type: ignore[union-attr]
            if entry["name"] == key.decode():
                next = True
                continue
        if next == False:
            red.set(entry["name"], json.dumps(entry))
            if rocketconfig["enable"] == True:
                rocketnotifyrf(rocketconfig, entry)


if __name__ == "__main__":
    main()
