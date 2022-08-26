# RansomLook

## Install 
Shoud be something like that, installing base system: 
```bash
sudo apt-get update
sudo apt-get -y upgrade
sudo apt-get -y install wget python3-dev git python3-venv python3-pip python-is-python3 tor
sudo apt-get -y install libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 libxkbcommon0 libxdamage1 libgbm1 libpango-1.0-0 libcairo2 libatspi2.0-0
sudo apt-get -y install libxcomposite1 libxfixes3 libxrandr2 libasound2 libwayland-client0
```


You need poetry installed, see the [install guide](https://python-poetry.org/docs/).


Installing Ransomlook
```bash
git clone https://github.com/FafnerKeyZee/RansomLook/
cd ransomlook
echo RANSOMLOOK_HOME="'`pwd`'" > .env
poetry install
echo poetry run playwright install
``` 

## Using it

### Adding a group
```bash
poetry run add groupename url
``` 

### Scraping all the groups & markets
```bash
poetry run scrape
``` 

### Parsing the data
```bash
poetry run parse
``` 

### Generating website
```bash
poetry run markdown
``` 

### Sending an email contenaining all the posts found the previous days
```bash
poetry run notify
```

## Nginx configuration
``` 
server {
	listen 80 default_server;
	listen [::]:80 default_server;


	root /home/user/ransomlook/docs/;

	index index.html index.htm index.nginx-debian.html;

	server_name _;

	location / {
		try_files $uri $uri/ =404;
	}

        location /screenshots/ {
                alias /home/user/ransomlook/source/screenshots/;
                autoindex on;
	}

}

``` 

