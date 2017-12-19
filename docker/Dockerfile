FROM rebasehelper/base-image:fedora-latest

COPY docker/entrypoint.sh /entrypoint.sh

WORKDIR /build
COPY . .

RUN python3 setup.py install --prefix=/usr && rm -rf build

WORKDIR /rebase
VOLUME /rebase

ENTRYPOINT ["/entrypoint.sh"]
