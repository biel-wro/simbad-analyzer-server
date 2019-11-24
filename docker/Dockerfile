FROM jsokolowski/simbad-analyzer-base:latest as base
WORKDIR /usr/analyzer-server/app

RUN apt-get update && apt-get -y install python3  python3-pip
RUN pip3 install --upgrade pip
COPY ./requirements.txt /usr/analyzer-server/app
RUN pip3 install -r /usr/analyzer-server/app/requirements.txt

COPY ./src /usr/analyzer-server/app
