ARG DOCKER_IMAGE=fedora:latest
FROM ${DOCKER_IMAGE}

WORKDIR /build
COPY . .

ENV PY_COLORS=1

RUN echo -e "deltarpm=0\ninstall_weak_deps=0\ntsflags=nodocs" >> /etc/dnf/dnf.conf

RUN dnf -y update
RUN dnf -y install \
  python2 \
  python2-devel \
  python3 \
  python3-devel \
  python2-rpm \
  python3-rpm \
  python2-tox \
  python3-tox \
  # python2-pip is not available on F25.
  python-pip \
  python3-pip \
  python2-setuptools \
  python3-setuptools \
  gcc \
  redhat-rpm-config \
  libxml2-devel \
  libxslt-devel \
  xz-devel \
  git \
  rpm-build \
  mock \
  rpmlint \
  libabigail \
  pkgdiff \
  dnf \
  dnf-plugins-core \
  # needed by rpm-py-installer.
  rpm-devel \
  && dnf clean all

CMD ["/usr/bin/tox"]
