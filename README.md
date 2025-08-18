# RansomLook

RansomLook is tool to monitor Ransomware groups and markets and extract their victims.

## Features

- Based on ransomwatch https://github.com/joshhighet/ransomwatch,
  - Important changes have been done:
    - All data are stored into valkey
    - Scraping is multithreaded
    - Scraping is done with PlayWright and screenshots are taken at the same time
    - Parsers are now using BeautilfulSoup and are independant
    - If you create a local account, you will be able to add/edit/delete groups using the web interface
    - All website is done using Flask so no need to regenerate any MD file
    - Mail alerting for posts containing your keywords
- Details about the groups with data from malpedia.
- Daily notification by email.
- Notification on RocketChat when a new post is created.
- Telegram monitoring
- Dataleak monitoring
- Monitoring Cryptocurrencies, data are from: https://ransomwhe.re
- [MISP](https://www.misp-project.org/) integration with the support of the [MISP ransomware galaxy](https://www.misp-galaxy.org/ransomware/)
- Ransomnotes, from ThreatLabs (@Threatlabz) 

# Install guide

Note that is is *strongly* recommended to use Ubuntu 22.04.

## System dependencies

You need poetry 2.1.0 installed.
```bash
curl -sSL https://install.python-poetry.org | python3 -
``` 

## Prerequisites

### Valkey

[Valkey](https://valkey.io/): Valkey is an open source (BSD) high-performance key/value datastore that supports a variety workloads such as caching, message queues, and can act as a primary database. Valkey can run as either a standalone daemon or in a cluster, with options for replication and high availability.

NOTE: Valkey should be installed from the source, and the repository must be in the same directory as the one you will be cloning RansomLook into.

In order to compile and test Valkey, you will need a few packages:

```bash
sudo apt-get update
sudo apt install build-essential tcl
```

```bash
git clone https://github.com/valkey-io/valkey
cd valkey
git checkout 8.0
make
# Optionally, you can run the tests:
make test
cd ..
```

### Clone RansomLook

Do the usual:

```bash
git clone https://github.com/RansomLook/RansomLook.git
```

### Ready to install RansomLook ?

And at this point, you should be in a directory that contains `valkey` and `RansomLook`.

Make sure it is the case by running `ls valkey RansomLook`. If you see `No such file or directory`,
one of them is missing and you need to fix the installation.

The directory tree must look like that:

```
.
├── valkey  => compiled valkey
└── RansomLook => not installed RansomLook yet
```

## Installation

### System dependencies (requires root)

```bash
sudo apt install python3-dev
sudo apt install libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 libxkbcommon0 libxdamage1 libgbm1 libpango-1.0-0 libcairo2 libatspi2.0-0 libxcomposite1 libxfixes3 libxrandr2 libasound2 libwayland-client0 
sudo apt install libgtk-3-0 libpangocairo-1.0-0 libcairo-gobject2 libgdk-pixbuf2.0-0 libx11-xcb1 libxcursor1
sudo apt install tor ffmpeg
```

### RansomLook installation

From the directory you cloned RansomLook to, run:

```bash
cd RansomLook  # if you're not already in the directory
poetry install
```

Initialize the `.env` file:

```bash
echo RANSOMLOOK_HOME="`pwd`" >> .env
```

Get web dependencies (css, font, js)
```bash
poetry run tools/3rdparty.py
poetry run tools/generate_sri.py
```
Be aware that those are version-constrained because [SubResource Integrity (SRI)](https://developer.mozilla.org/en-US/docs/Web/Security/Subresource_Integrity) is used (set in website/web/sri.txt).

### Configuration

Copy the config file:

```bash
cp config/generic.json.sample config/generic.json
```

And configure it accordingly to your needs.

### Update and launch

Run the following command to fetch the required javascript deps and run RansomLook.

```bash
poetry run update --yes
```

With the default configuration, you can access the web interface on `http://0.0.0.0:8000`.

# Usage

Start the tool (as usual, from the directory):

```bash
poetry run start
```

You can stop it with

```bash
poetry run stop
```

With the default configuration, you can access the web interface on `http://127.0.0.1:8000`.

# Commands

### Import data from the main instance 'https://www.ransomlook.io'

This command will copy the DB of the official instance.
```bash
poetry run tools/import_from_instance.py
```

### Populate descriptions and profiles from malpedia

```bash
poetry run tools/malpedia.py
```

### Add a group (we recommand to use the GUI in admin)

```bash
poetry run add GROUPNAME URLTOCHECK DATABASE-NUMBER
```

NB: if a parser exists in RansomLook/parsers/ be sure that GROUPNAME is the same of the .py file

NB: DATABASE-NUMBER must be 0 or 3, depending if you are adding a Ransomware blog or a Market place.

### Scrape all groups

```bash
sudo systemctl status tor # check if tor is running
sudo systemctl enable tor # active tor for next boots
sudo systemctl start tor # start tor if not running
poetry run scrape
```

### Parse all groups

```bash
poetry run parse
```

### Scrape for new dataleak

```bash
poetry run tools/breach.py
```

### Scrape and parse for Telegram messages

```bash
poetry run telegram
```

It's recommanded to create a cron job to scrape and parse all groups every 2 hours.

# License

Copyright (C) 2022-2025 [Fafner \[\_KeyZee\_\]](https://github.com/FafnerKeyZee)

Copyright (C) 2022-2025 [Alexandre Dulaunoy](https://github.com/adulau/)

Copyright (C) 2023-2025 [Tammy Harper](https://www.linkedin.com/in/tammyharper11)

Copyright (C) 2022-2025 [CERT-AG](https://cert-ag.com/) - CERT AG

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published
by the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.

# Usage of the API and License

All content provided by **ransomlook.io** — including the website, API responses, and datasets — is made available under the [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/) license.  

You are free to share and adapt the material for any purpose, even commercially, provided that appropriate credit is given.

