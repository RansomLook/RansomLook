#!/usr/bin/env python3
import argparse
import json
import logging
import smtplib
import ssl
from collections import defaultdict
from datetime import date, timedelta
from email.message import EmailMessage

import valkey

from ransomlook.default import DB_POSTS
from ransomlook.default.config import get_config, get_socket_path
from ransomlook.default.logging import get_logger

logger = get_logger("notify")


def getnewpost(date: str) -> dict[str, list[str]]:
    """
    check if a post already exists in posts.json
    """
    red = valkey.Valkey(unix_socket_path=get_socket_path("cache"), db=DB_POSTS)
    notify = defaultdict(list)
    for group in red.keys():  # type: ignore[union-attr]
        posts = json.loads(red.get(group))  # type: ignore[arg-type]
        for post in posts:
            if post["discovered"].split()[0] == date:
                notify[group.decode()].append(post["post_title"])
    ret = dict(sorted(notify.items()))
    return ret


def main() -> None:
    parser = argparse.ArgumentParser(description="Send email notifications for new ransomware posts")
    parser.add_argument("--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"], default=None, help="Override log level")
    args = parser.parse_args()

    if args.log_level:
        level = getattr(logging, args.log_level)
        logging.getLogger().setLevel(level)
        for handler in logging.getLogger().handlers:
            handler.setLevel(level)

    email_config = get_config("generic", "email")
    smtp_auth = get_config("generic", "email_smtp_auth")
    newposts = getnewpost(str(date.today() - timedelta(days=1)))
    if newposts == {}:
        logger.info("No new post")
        return
    message = email_config["message_head"]
    message += str((date.today() - timedelta(days=1)).strftime("%d-%m-%Y")) + ".\n"

    for key in newposts:
        message += "\n" + key + " :\n"
        for entry in newposts[key]:
            message += "* " + entry + "\n"

    message += email_config["message_foot"]

    fromaddr = email_config["from"]
    toaddrs = email_config["to"]
    toaddrsbcc = email_config["to_bcc"]
    subject = email_config["subject"]
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = fromaddr
    msg["To"] = ", ".join(toaddrs)
    msg["Bcc"] = ", ".join(toaddrsbcc)
    msg.set_content(message)
    try:
        with smtplib.SMTP(host=email_config["smtp_server"], port=email_config["smtp_port"]) as server:
            if smtp_auth["auth"]:
                if "smtp_use_tls" in smtp_auth:
                    logger.info("please change the config name from smtp_use_tls to smtp_use_starttls")
                if smtp_auth.get("smtp_use_tls") is True or smtp_auth["smtp_use_starttls"]:
                    if smtp_auth["verify_certificate"] is False:
                        ssl_context = ssl.create_default_context()
                        ssl_context.check_hostname = False
                        ssl_context.verify_mode = ssl.CERT_NONE
                        server.starttls(context=ssl_context)
                    else:
                        server.starttls()
                server.login(smtp_auth["smtp_user"], smtp_auth["smtp_pass"])
            server.send_message(msg)
            server.quit()
    except smtplib.SMTPException as e:
        logger.error(e)


if __name__ == "__main__":
    main()
