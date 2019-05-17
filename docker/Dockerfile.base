ARG BASE_IMAGE=fedora:latest
FROM ${BASE_IMAGE}

RUN echo -e "deltarpm=0\ninstall_weak_deps=0\ntsflags=nodocs" >> /etc/dnf/dnf.conf \
  # update GPG keys first in case some of them are missing
  && dnf -y --nogpgcheck update fedora-gpg-keys || true \
  # workaround conflict between coreutils and coreutils-single
  && dnf -y --allowerasing install coreutils fedora-release \
  && dnf -y update \
  && dnf -y install \
    python36 \
    python38 \
    python3 \
    python3-devel \
    python3-tox \
    redhat-rpm-config \
    libxml2-devel \
    libxslt-devel \
    licensecheck \
    xz-devel \
    krb5-devel \
    git \
    rpm-build \
    mock \
    rpmlint \
    libabigail \
    pkgdiff \
    dnf \
    dnf-plugins-core \
    # needed by rpm-py-installer
    rpm-devel \
    # necessary for rpmbuild
    @buildsys-build \
  && dnf clean all
