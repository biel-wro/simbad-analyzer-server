FROM python:3.7.5-alpine3.9

WORKDIR /usr/analyzer-server/app
RUN pip install --upgrade pip
COPY ./requirements.txt /usr/analyzer-server/app
RUN pip install -r /usr/analyzer-server/app/requirements.txt

COPY ./src /usr/analyzer-server/app
