FROM ubuntu:22.04
ENV LC_ALL=C.UTF-8
ENV LANG=C.UTF-8
ENV TZ=Etc/UTC
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

RUN apt-get update
RUN apt-get -y upgrade
RUN apt-get -y install wget python3-dev git python3-venv python3-pip python-is-python3 tor
RUN apt-get -y install libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 libxkbcommon0 libxdamage1 libgbm1 libpango-1.0-0 libcairo2 libatspi2.0-0
RUN apt-get -y install libxcomposite1 libxfixes3 libxrandr2 libasound2 libwayland-client0
RUN pip3 install poetry

WORKDIR ransomlook

COPY ransomlook ransomlook/
COPY bin bin/
COPY pyproject.toml .
COPY poetry.lock .

RUN echo RANSOMLOOK_HOME="'`pwd`'" > .env
RUN poetry install
RUN poetry run playwright install
