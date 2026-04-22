# RansomLook

RansomLook is a tool to monitor Ransomware groups and markets and extract their victims.

## Features

- Based on ransomwatch https://github.com/joshhighet/ransomwatch,
  - Important changes have been done:
    - All data are stored into Valkey
    - Scraping is multithreaded
    - Scraping is done with Playwright and screenshots are taken at the same time
    - Parsers are now using BeautifulSoup and are independent
    - If you create a local account, you will be able to add/edit/delete groups using the web interface
    - All website is done using Flask so no need to regenerate any MD file
    - Mail alerting for posts containing your keywords
- Details about the groups with data from malpedia.
- Daily notification by email.
- Notification on RocketChat when a new post is created.
- Dataleak monitoring
- Threat actor tracking with relations (groups, forums, peers) and wanted status
- Monitoring Cryptocurrencies with transaction tracking via [Breadcrumbs One](https://www.breadcrumbs.app/) API
- Ransomnotes, from ThreatLabs (@Threatlabz)
- [MISP](https://www.misp-project.org/) integration with the support of the [MISP ransomware galaxy](https://www.misp-galaxy.org/ransomware/)
- Full REST API with interactive Swagger documentation at `/doc`
- Cryptocurrency enrichment with [Breadcrumbs](https://www.breadcrumbs.app/)], an API key is requiered.
- Torrent swarm health tracking (magnets referenced in posts): seeders, leechers and peer samples. Peer IPs are enriched via [CIRCL](https://www.circl.lu/) IP ASN History + BGP Ranking.
- English / French UI with a cookie-based switcher.

# Install guide

Note that is is *strongly* recommended to use Ubuntu 24.04.

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

## Service management

```bash
poetry run start           # Start backend (Valkey) + website
poetry run stop            # Stop website + backend
poetry run shutdown        # Graceful shutdown of all services
poetry run start_website   # Start only the web interface (Gunicorn)
poetry run run_backend     # Start only the Valkey backend
poetry run update --yes    # System update, fetch deps, integrity checks
```

With the default configuration, the web interface is available at `http://127.0.0.1:8000`.

## Core pipeline

These should be scheduled via cron (recommended: every 2 hours).

```bash
# Make sure Tor is running first
sudo systemctl enable --now tor

poetry run scrape          # Scrape all group/market sites (DB 0 + 3)
poetry run parse           # Run all parsers to extract posts from scraped data
poetry run screen          # Take screenshots of group sites via Lacus/Playwright
```

## Data enrichment

```bash
poetry run notify          # Send email notifications for new posts
poetry run notifyleak      # Send email notifications for new leaks
poetry run breach          # Scrape leak-lookup.com for new data breaches (DB 4)
poetry run cryptocur       # Sync cryptocurrency addresses from ransomwhe.re (DB 7)
poetry run update_crypto_tx # Fetch/update transactions via Breadcrumbs One API (DB 7)
poetry run rf              # Fetch Recorded Future channel data (DB 10)
poetry run notes           # Import/update ransom notes from ThreatLabz repo (DB 11)
poetry run torrent         # Fetch torrent information from ransomware groups
poetry run torrent-health  # Scan BitTorrent swarms for each tracked magnet (DB 13)
poetry run enrich-ips      # Enrich observed peer IPs via CIRCL (cached 7 days)
```

## Cron setup

Example crontab (`crontab -e`):

```cron
# Core pipeline: scrape → parse → screenshot (every 2 hours)
0 */2 * * * cd /path/to/RansomLook && poetry run scrape && poetry run parse && poetry run screen

# Notifications (daily morning recap)
0 8 * * * cd /path/to/RansomLook && poetry run notify && poetry run notifyleak

# Data enrichment (daily)
0 4 * * * cd /path/to/RansomLook && poetry run breach
0 5 * * * cd /path/to/RansomLook && poetry run cryptocur && poetry run update_crypto_tx
0 6 * * * cd /path/to/RansomLook && poetry run rf && poetry run notes

# Torrent swarm health (every 6 hours, adaptive per-swarm)
0 */6 * * * cd /path/to/RansomLook && flock -n /tmp/rl-torrent.lock poetry run torrent-health

# CIRCL IP enrichment (daily, keeps the admin page instant)
30 3 * * * cd /path/to/RansomLook && flock -n /tmp/rl-enrich.lock poetry run enrich-ips
```

## Adding groups

We recommend using the admin GUI, but you can also use the CLI:

```bash
poetry run add GROUPNAME URLTOCHECK DATABASE-NUMBER
```

- `DATABASE-NUMBER`: `0` for ransomware group, `3` for market/forum
- If a parser exists in `RansomLook/parsers/`, the group name must match the `.py` filename

## Tools (`tools/`)

### Import data from a remote instance

```bash
# Import all databases (0=Groups, 2=Posts, 3=Markets, 4=Leaks, 5=Actors, 10=RF)
poetry run tools/import_from_instance.py --api-key "YOUR_API_KEY"

# Or use an environment variable
export RANSOMLOOK_API_KEY="YOUR_API_KEY"
poetry run tools/import_from_instance.py

# Custom instance + specific databases only
poetry run tools/import_from_instance.py --url https://my-instance/api --api-key "KEY" --db 0 2 5
```

An API key is required (generate one in **Admin > API Keys** on the remote instance).

### Other tools

```bash
poetry run tools/malpedia.py               # Enrich group metadata with Malpedia descriptions
poetry run tools/import_groups.py          # Seed DB from data/groups.json + data/markets.json
poetry run tools/getpreviousscreen.py      # Retrieve archived screenshots
poetry run tools/validate_config_files.py  # Validate config/generic.json structure
poetry run tools/3rdparty.py               # Download third-party JS/CSS (Plotly, etc.)
poetry run tools/generate_sri.py           # Regenerate SRI hashes for static assets
python3 tools/crypto_export.py             # Export crypto addresses to CSV
python3 tools/crypto_export.py --chain bitcoin -o btc.csv  # Bitcoin only
python3 tools/cryptostats.py               # Display per-group crypto address/tx counts
```

### Test seed scripts

```bash
poetry run tools/seed_actors.py          # Populate sample threat actors for testing
poetry run tools/seed_alert_keywords.py  # Populate sample alert keywords for testing
poetry run tools/seed_audit_logs.py      # Populate sample audit log entries for testing
```

# API

RansomLook exposes a REST API with interactive Swagger documentation available at `/doc`.

### Authentication

Most read endpoints are public. The **export** endpoint requires an API key passed via the `Authorization` header.

API keys are managed in **Admin > API Keys** through the web interface.

### Namespaces

| Namespace | Base path | Description |
|-----------|-----------|-------------|
| **Stats** | `/api/stats`, `/api/hot`, `/api/search`, `/api/health`, `/api/compare` | Platform statistics, trending groups, cross-entity search, mirror health, side-by-side comparison |
| **GenericAPI** | `/api/` | Groups, markets, posts, recent/last/period queries, export |
| **Actors** | `/api/actors/` | Threat actor profiles, relations (groups, forums, peers), wanted status |
| **Crypto** | `/api/crypto/` | Cryptocurrency groups, wallets by blockchain, transactions, stats, recent tx |
| **Notes** | `/api/notes/` | Ransom notes by group, recent notes, note details |
| **Leaks** | `/api/leaks/` | Data breach records |
| **RecordedFuture** | `/api/rf/` | Recorded Future channel data |

### Export

Bulk database export for reimport or offline analysis:

```
GET /api/export/<db>
Authorization: YOUR_API_KEY
```

| DB | Content |
|----|---------|
| 0 | Groups (ransomware group metadata and locations) |
| 2 | Posts (victim posts across all groups) |
| 3 | Markets (market / forum metadata and locations) |
| 4 | Leaks (data breach records) |
| 5 | Actors (threat actor profiles and relations) |
| 10 | Recorded Future (RF channel data) |

Private entries are automatically filtered from groups (0), markets (3) and actors (5).

# License

Copyright (C) 2022-2026 [Fafner \[\_KeyZee\_\]](https://github.com/FafnerKeyZee)

Copyright (C) 2022-2026 [Alexandre Dulaunoy](https://github.com/adulau/)

Copyright (C) 2023-2026 [Tammy Harper](https://www.linkedin.com/in/tammyharper11)

Copyright (C) 2026 [Katya Kandratovich](https://www.linkedin.com/in/katya-k-440175b7/)

Copyright (C) 2022-2026 [CERT-AG](https://cert-ag.com/) - CERT AG

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

