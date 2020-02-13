FROM docker:latest

RUN apk update \
  && apk add --no-cache git make python py-pip py-setuptools \
  && pip install --no-cache-dir docker-compose
