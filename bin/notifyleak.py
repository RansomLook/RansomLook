#!/usr/bin/env python3
import argparse
import json
import logging
import smtplib
import ssl
from datetime import date, timedelta
from email.message import EmailMessage

import valkey

from ransomlook.default import DB_LEAKS
from ransomlook.default.config import get_config, get_socket_path
from ransomlook.default.logging import get_logger

logger = get_logger("notifyleak")


def getnewbreach(date: str) -> list[dict[str, str]]:
    """
    check if a post already exists in posts.json
    """
    red = valkey.Valkey(unix_socket_path=get_socket_path("cache"), db=DB_LEAKS)
    notify = []
    for breaches in red.keys():  # type: ignore[union-attr]
        breach = json.loads(red.get(breaches))  # type: ignore[arg-type]
        if breach["indexed"].split()[0] == date:
            notify.append(breach)
    return notify


def main() -> None:
    parser = argparse.ArgumentParser(description="Send email notifications for new data breaches")
    parser.add_argument("--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"], default=None, help="Override log level")
    args = parser.parse_args()

    if args.log_level:
        level = getattr(logging, args.log_level)
        logging.getLogger().setLevel(level)
        for handler in logging.getLogger().handlers:
            handler.setLevel(level)

    email_config = get_config("generic", "email")
    smtp_auth = get_config("generic", "email_smtp_auth")
    newposts = getnewbreach(str(date.today() - timedelta(days=1)))
    if newposts == []:
        logger.info("No new post")
        return
    message = """Hello

Please find the list of databreach detected on : """
    message += str((date.today() - timedelta(days=1)).strftime("%d-%m-%Y")) + ".\n"
    for entry in newposts:
        message += "\n" + entry["name"] + " :\n"
        message += "Size             : " + entry["size"] + "\n"
        message += "Records          : " + entry["records"] + "\n"
        message += "Compromised data : " + str(entry["columns"]) + "\n"

    message += "\nBest regards,\n\nRansomlook Team"

    fromaddr = email_config["from"]
    toaddrs = email_config["to"]
    subject = "DataBreach detected"
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = fromaddr
    msg["To"] = ", ".join(toaddrs)
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
