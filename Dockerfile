FROM fedora:latest

MAINTAINER "Petr Hracek" <phracek@redhat.com>

RUN dnf update -y \
 && dnf -y --setopt=tsflags=nodocs install rebase-helper python-copr copr-cli && dnf -y clean all

ARG RH_VERSION=0.0.1
ARG RH_PACKAGE=foobar
ENV RH_VERSION ${RH_VERSION} RH_PACKAGE ${RH_PACKAGE}

RUN mkdir -p /rebase_helper

RUN git clone http://pkgs.fedoraproject.org/cgit/rpms/$RH_PACKAGE.git package_name 
VOLUME [ "/rebase_helper" ]
WORKDIR /package_name

CMD cd /package_name && rebase-helper $RH_VERSION --non-interactive -v --results-dir /rebase_helper

