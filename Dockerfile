FROM fedora:latest

MAINTAINER "Petr Hracek" <phracek@redhat.com>

RUN dnf update -y \
 && dnf -y --setopt=tsflags=nodocs install rebase-helper python-copr copr-cli && dnf -y clean all

ARG RH_VERSION=0.0.1
ARG RH_PACKAGE=foobar
ENV RH_VERSION ${RH_VERSION} RH_PACKAGE ${RH_PACKAGE}

RUN mkdir -p /rebase-helper

RUN git clone http://pkgs.fedoraproject.org/cgit/rpms/$RH_PACKAGE.git package_name 
VOLUME [ "/rebase-helper" ]
WORKDIR /package_name

RUN ls -la /
RUN ls -la /package_name

CMD cd /package_name && ls -la && rebase-helper $RH_VERSION --non-interactive -v

