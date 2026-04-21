#!/usr/bin/env python3
"""
🧅 👀 🦅 👹
ransomlook
does what it says on the tin
"""

import asyncio
import base64
import json
import os
import queue
import time
import urllib.parse
from datetime import datetime
from threading import Lock, Thread
from typing import Any

import libtorrent as lt  # type: ignore
import valkey
from dateutil.relativedelta import relativedelta
from lacuscore import LacusCore
from PIL import Image
from PIL.PngImagePlugin import PngInfo
from pylacus import CaptureSettings, PyLacus
from valkey import Valkey

from .default import DB_GROUPS, DB_HEALTH, DB_LACUS, DB_POSTS, DB_TASKS
from .default.config import get_config, get_homedir, get_socket_path
from .default.logging import get_logger
from .sharedutils import createfile, errlog, format_bytes, siteschema, stdlog, striptld

logger = get_logger("ransomlook")

# --- Health series config (per-mirror daily 0/1) ---

HEALTH_SERIES_LEN = int(os.environ.get("RL_HEALTH_SERIES_LEN", "90"))
HEALTH_DAY_THRESHOLD = float(os.environ.get("RL_HEALTH_DAY_THRESHOLD", "0.5"))
HEALTH_COUNTER_TTL_D = int(os.environ.get("RL_HEALTH_COUNTER_TTL_D", "120"))


def update_mirror_health(
    red_health: valkey.Valkey,
    group_name: str,
    loc: dict,  # type: ignore[type-arg]
    is_up: bool,
    series_len: int = HEALTH_SERIES_LEN,
    threshold: float = HEALTH_DAY_THRESHOLD,
    counter_ttl_days: int = HEALTH_COUNTER_TTL_D,
) -> None:
    """
    Aggregate checks into a daily 0/1 sample per mirror, robust to variable scrape frequency.
    Keys used:
      - health:cnt:<group>:<slug>:<YYYYMMDD>  (hash: up/total)
      - health:<group>:<slug>                 (JSON list of 0/1 per day, last N)
      - health:lastday:<group>:<slug>         (last written YYYYMMDD)
    """
    try:
        slug = (loc.get("slug") or "").strip()
        if not slug:
            return
        group = group_name if isinstance(group_name, str) else str(group_name)
        today = datetime.utcnow().strftime("%Y%m%d")
        # 1) daily counters
        hcnt_key = f"health:cnt:{group}:{slug}:{today}"
        pipe = red_health.pipeline()
        pipe.hincrby(hcnt_key, "total", 1)
        if is_up:
            pipe.hincrby(hcnt_key, "up", 1)
        pipe.expire(hcnt_key, counter_ttl_days * 86400)
        pipe.execute()  # type: ignore[no-untyped-call]
        # 2) aggregated day value
        counts = red_health.hgetall(hcnt_key) or {}
        up = int(counts.get(b"up", b"0"))  # type: ignore[union-attr]
        total = max(1, int(counts.get(b"total", b"1")))  # type: ignore[union-attr]
        day_val = 1 if (up / total) >= threshold else 0
        # 3) series
        series_key = f"health:{group}:{slug}"
        lastday_key = f"health:lastday:{group}:{slug}"
        raw = red_health.get(series_key) or b"[]"
        try:
            series = json.loads(raw)  # type: ignore[arg-type]
            if not isinstance(series, list):
                series = []
        except Exception:
            series = []
        last_day = red_health.get(lastday_key)
        last_day = last_day.decode() if last_day else None  # type: ignore[union-attr]
        if last_day == today:
            series[-1:] = [day_val] if series else [day_val]
        else:
            series.append(day_val)
            red_health.set(lastday_key, today)
        if len(series) > series_len:
            series = series[-series_len:]
        red_health.set(series_key, json.dumps(series))
    except Exception:
        # Never let health tracking break the scraper
        pass


# pylint: disable=W0703

redislacus = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_LACUS)
lacus = LacusCore(redislacus, tor_proxy="socks5://127.0.0.1:9050")  # type: ignore[arg-type]


def creategroup(
    location: str, fs: bool, private: bool, chat: bool, admin: bool, browser: str | None, init_script: str | None
) -> dict[str, object]:
    """
    create a new group for a new provider - added to groups.json
    """
    mylocation = siteschema(location, fs, private, chat, admin, browser, init_script)
    insertdata: dict[str, Any | None] = {
        "captcha": False,
        "meta": None,
        "locations": [mylocation] if location != "" else [],
        "profile": [],
        "ransomware_galaxy_value": "",
    }
    return insertdata


def checkexisting(provider: str, db: int) -> bool:
    """
    check if group already exists within groups.json
    """
    red = valkey.Valkey(unix_socket_path=get_socket_path("cache"), db=db)
    return bool(red.exists(provider))


async def run_captures() -> None:
    max_captures_to_consume = get_config("generic", "thread")
    captures = set()
    async for capture_task in lacus.consume_queue(max_captures_to_consume):
        captures.add(capture_task)  # adds the task to the set
        capture_task.add_done_callback(captures.discard)  # remove the task from the set when done

    await asyncio.gather(*captures)  # wait for all tasks to complete


def scraper(base: int, only_names: list[str] | None = None) -> None:
    """main scraping function"""
    red = valkey.Valkey(unix_socket_path=get_socket_path("cache"), db=base)
    # Health DB connection
    try:
        red_health = valkey.Valkey(unix_socket_path=get_socket_path("cache"), db=DB_HEALTH)
    except Exception:
        red_health = None
    groups = []
    running_capture = {}
    validationDate = datetime.now() - relativedelta(months=6)
    remote_lacus_url = None
    if get_config("generic", "remote_lacus"):
        remote_lacus_config = get_config("generic", "remote_lacus")
        if remote_lacus_config.get("enable"):
            remote_lacus_url = remote_lacus_config.get("url")
            lacus = PyLacus(remote_lacus_url)
            try:
                lacus.status()
            except Exception:
                logger.debug("using local lacuscore")
                remote_lacus_url = None

    if not remote_lacus_url:
        lacus = LacusCore(redislacus, tor_proxy="socks5://127.0.0.1:9050")  # type: ignore

    only_set = {n.lower() for n in only_names} if only_names else None
    all_names: list[str] = []
    for key in red.keys():  # type: ignore[union-attr]
        name = key.decode()
        all_names.append(name)
        if only_set and name.lower() not in only_set:
            continue
        group = json.loads(red.get(key))  # type: ignore[arg-type]
        group["name"] = name
        groups.append(group)
    if only_set and not groups:
        tokens = {tok for s in only_set for tok in s.split() if tok}
        near = sorted({n for n in all_names if any(tok in n.lower() for tok in tokens)})
        hint = ", ".join(near) if near else "(no similar name found)"
        logger.warning(
            "No matching %s in DB %d for %s. Closest names: %s",
            "market(s)" if base == 3 else "group(s)",
            base,
            sorted(only_set),
            hint,
        )
    for group in groups:
        stdlog("ransomloook: " + "working on " + group["name"])
        # iterate each location/mirror/relay
        for host in group["locations"]:
            try:
                if not datetime.strptime(host["updated"], "%Y-%m-%d %H:%M:%S.%f") > validationDate:
                    logger.debug("Skipping %s", host["fqdn"])
                    continue
            except Exception:
                logger.error("Error with : %s", host["slug"])
                continue
            settings: CaptureSettings = {"url": host["slug"], "general_timeout_in_sec": 90, "max_retries": 1}
            if "header" in host:
                settings["headers"] = host["header"]
            if "browser" in host and host["browser"] is not None:
                settings["browser"] = host["browser"]
            if "init_script" in host and host["init_script"] is not None:
                settings["init_script"] = host["init_script"]

            uuid = lacus.enqueue(settings=settings)
            running_capture[uuid] = {"group": group["name"], "slug": host["slug"]}
    if not remote_lacus_url:
        asyncio.run(run_captures())
    while running_capture:
        for key in list(running_capture):
            if lacus.get_capture_status(str(key)) == -1:
                group = json.loads(red.get(running_capture[str(key)]["group"]))  # type: ignore[arg-type]
                for location in group["locations"]:
                    if location["slug"] == running_capture[str(key)]["slug"]:
                        location.update({"available": False})
                        if red_health:
                            try:
                                update_mirror_health(red_health, group["name"], location, False)
                            except Exception:
                                pass
                        red.set(running_capture[str(key)]["group"], json.dumps(group))
                        break
                running_capture.pop(str(key))
                continue
            if lacus.get_capture_status(str(key)) == 1:
                result = lacus.get_capture(str(key))
                name = str(running_capture[str(key)]["group"])
                group = json.loads(red.get(name))  # type: ignore[arg-type]
                for location in group["locations"]:
                    if location["slug"] == running_capture[str(key)]["slug"]:
                        host = location
                        continue
                # if result['status']=='error': # type: ignore
                #    host.update({'available':False})
                #    running_capture.pop(str(key))
                #    red.set(name, json.dumps(group))
                #    continue
                if "png" in result and not ("fixedfile" in host and host["fixedfile"] is True):
                    filename = name + "-" + createfile(host["slug"]) + ".png"
                    namefile = os.path.join(get_homedir(), "source/screenshots", filename)
                    with open(namefile, "wb") as tosave:
                        if remote_lacus_url:
                            tosave.write(result["png"])  # type: ignore
                        else:
                            tosave.write(base64.b64decode(result["png"]))  # type: ignore
                    targetImage = Image.open(namefile)
                    metadata = PngInfo()
                    metadata.add_text("Source", "RansomLook.io")
                    targetImage.save(namefile, pnginfo=metadata)
                    if get_config("generic", "keepall"):
                        nowpng = datetime.now()
                        timestamp = nowpng.strftime("%Y-%m-%d_%H-%M-%S")
                        filename = timestamp + "-" + createfile(host["slug"]) + ".png"
                        folder = os.path.join(get_homedir(), "source/screenshots/old", name)
                        if not os.path.exists(folder):
                            os.makedirs(folder)
                        file_path = os.path.join(folder, filename)
                        with open(file_path, "wb") as tosave:
                            if remote_lacus_url:
                                tosave.write(result["png"])  # type: ignore
                            else:
                                tosave.write(base64.b64decode(result["png"]))  # type: ignore
                if "html" in result:
                    filename = name + "-" + striptld(host["slug"]) + ".html"
                    namefile = os.path.join(os.getcwd(), "source", filename)
                    with open(namefile, "w", encoding="utf-8") as tosave:
                        tosave.write(result["html"])  # type: ignore
                    host.update(
                        {
                            "available": True,
                            "title": result["har"]["log"]["pages"][0]["title"],  # type: ignore[index]
                            "lastscrape": result["har"]["log"]["pages"][0]["startedDateTime"]  # type: ignore[index]
                            .replace("T", " ")
                            .replace("Z", ""),
                            "updated": result["har"]["log"]["pages"][0]["startedDateTime"]  # type: ignore[index]
                            .replace("T", " ")
                            .replace("Z", ""),
                        }
                    )
                    if red_health:
                        try:
                            update_mirror_health(red_health, name, host, True)
                        except Exception:
                            pass
                elif "har" in result and "log" in result["har"] and "entries" in result["har"]["log"]:  # type: ignore
                    try:
                        html = result["har"]["log"]["entries"][0]["response"]["content"]["text"]  # type: ignore
                        filename = name + "-" + striptld(host["slug"]) + ".html"
                        namefile = os.path.join(os.getcwd(), "source", filename)
                        with open(namefile, "w", encoding="utf-8") as tosave:
                            tosave.write(html)
                        host.update(
                            {
                                "available": True,
                                "title": result["har"]["log"]["pages"][0]["title"],  # type: ignore[index]
                                "lastscrape": result["har"]["log"]["pages"][0]["startedDateTime"]  # type: ignore[index]
                                .replace("T", " ")
                                .replace("Z", ""),
                                "updated": result["har"]["log"]["pages"][0]["startedDateTime"]  # type: ignore[index]
                                .replace("T", " ")
                                .replace("Z", ""),
                            }
                        )
                        if red_health:
                            try:
                                update_mirror_health(red_health, name, host, True)
                            except Exception:
                                pass
                    except Exception:
                        host.update({"available": False})
                        if red_health:
                            try:
                                update_mirror_health(red_health, name, host, False)
                            except Exception:
                                pass
                else:
                    host.update({"available": False})
                    if red_health:
                        try:
                            update_mirror_health(red_health, name, host, False)
                        except Exception:
                            pass
                red.set(name, json.dumps(group))
                running_capture.pop(str(key))

        if not remote_lacus_url:
            asyncio.run(run_captures())
        else:
            time.sleep(10)


def adder(
    name: str,
    location: str,
    db: int,
    fs: bool = False,
    private: bool = False,
    chat: bool = False,
    admin: bool = False,
    browser: str | None = None,
    init_script: str | None = None,
) -> int:
    """
    handles the addition of new providers to groups.json
    """
    if checkexisting(name.strip(), db):
        stdlog("ransomlook: " + "records for " + name + " already exist, appending to avoid duplication")
        if location.strip() != "":
            return appender(name.strip(), location.strip(), db, fs, private, chat, admin, browser, init_script)
        return 0
    else:
        red = valkey.Valkey(unix_socket_path=get_socket_path("cache"), db=db)
        newrec = creategroup(location.strip(), fs, private, chat, admin, browser, init_script)
        red.set(name.strip(), json.dumps(newrec))
        stdlog("ransomlook: " + "record for " + name + " added to groups.json")
        return 0


def appender(
    name: str,
    location: str,
    db: int,
    fs: bool,
    private: bool,
    chat: bool,
    admin: bool,
    browser: str | None,
    init_script: str | None,
) -> int:
    """
    handles the addition of new mirrors and relays for the same site
    to an existing group within groups.json
    """
    red = valkey.Valkey(unix_socket_path=get_socket_path("cache"), db=db)
    group = json.loads(red.get(name.strip()))  # type: ignore[arg-type]
    success = False
    for loc in group["locations"]:
        if location == loc["slug"]:
            errlog("cannot append to non-existing provider or the location already exists")
            return 2
    group["locations"].append(siteschema(location, fs, private, chat, admin, browser, init_script))
    red.set(name.strip(), json.dumps(group))
    return 1


def screen() -> None:
    red = valkey.Valkey(unix_socket_path=get_socket_path("cache"), db=DB_TASKS)
    if b"toscan" not in red.keys():  # type: ignore[operator]
        stdlog("No screen to do !")
        return
    redgroup = valkey.Valkey(unix_socket_path=get_socket_path("cache"), db=DB_GROUPS)
    captures = json.loads(red.get("toscan"))  # type: ignore[arg-type]
    stdlog("Found %s captures to process" % len(captures))
    remote_lacus_url = None
    if get_config("generic", "remote_lacus"):
        remote_lacus_config = get_config("generic", "remote_lacus")
        if remote_lacus_config.get("enable"):
            remote_lacus_url = remote_lacus_config.get("url")
            stdlog("Trying remote Lacus at %s" % remote_lacus_url)
            lacus = PyLacus(remote_lacus_url)
            try:
                lacus.status()
                stdlog("Remote Lacus connected")
            except Exception:
                stdlog("Remote Lacus unavailable, falling back to local LacusCore")
                remote_lacus_url = None

    if not remote_lacus_url:
        stdlog("Using local LacusCore with Tor proxy")
        lacus = LacusCore(redislacus, tor_proxy="socks5://127.0.0.1:9050")  # type: ignore

    uuids = []
    slugs = []
    stdlog("Enqueuing captures...")
    for capture in captures:
        group = json.loads(redgroup.get(capture["group"].encode()))  # type: ignore[arg-type]
        for host in group["locations"]:
            try:
                if capture["slug"].removeprefix(capture["group"] + "-").split(".")[0] in striptld(host["slug"]):
                    if "private" in host and host["private"] is True:
                        continue
                    capture.update({"slug2": urllib.parse.urljoin(host["slug"], str(capture["link"]))})
                    if capture["slug2"] not in slugs:
                        slugs.append(capture["slug2"])
                        settings: CaptureSettings = {
                            "url": capture["slug2"],
                            "general_timeout_in_sec": 90,
                            "max_retries": 1,
                        }
                        if "header" in host:
                            settings["headers"] = host["header"]
                        if "browser" in host and host["browser"] is not None:
                            settings["browser"] = host["browser"]
                        if "init_script" in host and host["init_script"] is not None:
                            settings["init_script"] = host["init_script"]
                        uuid = lacus.enqueue(settings=settings)
                        capture.update({"uuid": uuid})
                        uuids.append(uuid)
                        stdlog("Enqueued: %s → %s" % (capture["group"], capture["slug2"]))
            except Exception:
                logger.debug("capture group: %s", capture["group"].encode())
                logger.debug("capture slug: %s", capture["slug"])

    stdlog("Enqueued %s captures" % len(uuids))
    if not remote_lacus_url:
        stdlog("Running local captures (this may take a while)...")
        asyncio.run(run_captures())
    stdlog("Waiting for %s captures to complete..." % len(uuids))
    while uuids:
        for capture in captures:
            if "uuid" in capture:
                if lacus.get_capture_status(capture["uuid"]) == -1:
                    uuids.remove(capture["uuid"])
                    del capture["uuid"]
                    continue
                if lacus.get_capture_status(capture["uuid"]) == 1:
                    time.sleep(1)
                    result = lacus.get_capture(capture["uuid"])
                    stdlog("Capture done: %s/%s — %s [%s]" % (capture["group"], capture["title"], result.get("status", "?"), len(uuids) - 1))
                    uuids.remove(capture["uuid"])
                    del capture["uuid"]
                    if "png" in result and "html" in result:
                        filenamepng = createfile(capture["title"]) + ".png"
                        path = os.path.join(get_homedir(), "source/screenshots", capture["group"])
                        if not os.path.exists(path):
                            os.mkdir(path)
                        namepng = os.path.join(path, filenamepng)
                        with open(namepng, "wb") as tosave:
                            if remote_lacus_url:
                                tosave.write(result["png"])  # type: ignore
                            else:
                                tosave.write(base64.b64decode(result["png"]))  # type: ignore
                        targetImage = Image.open(namepng)
                        metadata = PngInfo()
                        metadata.add_text("Source", "RansomLook.io")
                        targetImage.save(namepng, pnginfo=metadata)

                        filename = createfile(capture["title"]) + ".html"
                        path = os.path.join(get_homedir(), "source/", capture["group"])
                        if not os.path.exists(path):
                            os.mkdir(path)
                        name = os.path.join(path, filename)
                        with open(name, "w", encoding="utf-8") as tosave:
                            tosave.write(result["html"])  # type: ignore
                        redpost = valkey.Valkey(unix_socket_path=get_socket_path("cache"), db=DB_POSTS)
                        updated = json.loads(redpost.get(capture["group"]))  # type: ignore[arg-type]
                        for post in updated:
                            if post["post_title"] == capture["title"]:
                                post["screen"] = str(os.path.join("screenshots", capture["group"], filenamepng))
                                post.update(post)
                        redpost.set(capture["group"], json.dumps(updated))
                        toscreen = json.loads(red.get("toscan"))  # type: ignore[arg-type]
                        for idx, item in enumerate(toscreen):
                            if item["group"] == capture["group"] and item["title"] == capture["title"]:
                                toscreen.pop(idx)
                                break
                        red.set("toscan", json.dumps(toscreen))
        if not remote_lacus_url:
            asyncio.run(run_captures())
        else:
            time.sleep(10)


def threadtorrent(queuethread, lock) -> None:  # type: ignore[no-untyped-def]
    while True:
        sess, torrent = queuethread.get()
        logger.debug("processing torrent: %s", torrent)
        atp = lt.parse_magnet_uri(torrent["magnet"])
        atp.save_path = "."
        atp.flags = lt.torrent_flags.upload_mode
        torr = sess.add_torrent(atp)
        while not torr.status().has_metadata:
            time.sleep(1)
        torr.pause()
        tinf = torr.torrent_file()
        # Workaround for empty torrent_info.trackers() in
        # libtorrent-rasterbar-2.0.7:
        trn = 0
        for t in tinf.trackers():
            trn += 1
        if trn == 0:
            for t in atp.trackers:
                tinf.add_tracker(t)
        files = ""
        for x in range(tinf.files().num_files()):
            files += format_bytes(tinf.files().file_size(x)) + "    " + tinf.files().file_path(x) + "\n"
        filename = createfile(torrent["title"]) + ".txt"
        path = os.path.join(get_homedir(), "source/screenshots", torrent["group"])
        if not os.path.exists(path):
            os.mkdir(path)
        name = os.path.join(path, filename)
        with open(name, "w", encoding="utf-8") as listing:
            listing.write(files)
            listing.close()

        # Saving torrent file
        path = os.path.join(get_homedir(), "source/", torrent["group"])
        if not os.path.exists(path):
            os.mkdir(path)
        filetorrent = createfile(torrent["title"]) + ".torrent"
        nametorrent = os.path.join(path, filetorrent)
        f = open(nametorrent, "wb")
        f.write(lt.bencode(lt.create_torrent(tinf).generate()))
        f.close()

        red = valkey.Valkey(unix_socket_path=get_socket_path("cache"), db=DB_POSTS)
        updated = json.loads(red.get(torrent["group"]))  # type: ignore[arg-type]
        for post in updated:
            if post["post_title"] == torrent["title"]:
                post["screen"] = str(os.path.join("screenshots", torrent["group"], filename))
                post.update(post)
        red.set(torrent["group"], json.dumps(updated))
        red = valkey.Valkey(unix_socket_path=get_socket_path("cache"), db=DB_TASKS)
        totorrent = json.loads(red.get("totorrent"))  # type: ignore[arg-type]
        for idx, item in enumerate(totorrent):
            if item["group"] == torrent["group"] and item["title"] == torrent["title"]:
                totorrent.pop(idx)
                break
        red.set("totorrent", json.dumps(totorrent))
        logger.debug("Done with: %s", torrent["title"])
        sess.remove_torrent(torr)
        queuethread.task_done()


def gettorrentinfo() -> None:
    red = valkey.Valkey(unix_socket_path=get_socket_path("cache"), db=DB_TASKS)
    if b"totorrent" not in red.keys():  # type: ignore[operator]
        stdlog("No torrent to get !")
        return
    sess = lt.session()
    lock = Lock()
    queuethread = queue.Queue()  # type: ignore[var-annotated]
    for _ in range(get_config("generic", "thread")):
        t = Thread(target=threadtorrent, args=(queuethread, lock), daemon=True)
        t.start()

    torrents = json.loads(red.get("totorrent"))  # type: ignore[arg-type]
    for torrent in torrents:
        data = [sess, torrent]
        queuethread.put(data)
    queuethread.join()
    time.sleep(5)
