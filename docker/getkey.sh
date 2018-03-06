#!/bin/sh

# try to get GPG package signing key of an upcoming Fedora release
# to prevent package installation failures

. /etc/os-release

version="$((VERSION_ID + 1))"
filename="RPM-GPG-KEY-fedora-${version}-primary"
url="https://pagure.io/fedora-repos/raw/master/f/${filename}"
destination="/etc/pki/rpm-gpg/${filename}"

if [ ! -f "${destination}" ] && curl --head --fail --url "${url}"; then
    curl --url "${url}" --output "${destination}"
    rpm --import "${destination}"
fi
