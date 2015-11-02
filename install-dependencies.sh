#!/bin/sh

package="rpm"
version="4.12.0.1"

filename="${package}-${version}.tar.bz2"
url="http://rpm.org/releases/rpm-4.12.x/$filename"

builddir="$HOME/rpm_build"


# determine python version
################################################################################
python_version="$(python -c 'import sys; sys.stdout.write(sys.version[0])')"

if [ "$python_version" = "3" ]; then
    python="python3"
else
    python="python"
fi


# install dependencies
################################################################################
sudo apt-get -qq update || exit 1
sudo apt-get -y install \
    build-essential \
    libtool \
    autoconf \
    automake \
    autopoint \
    zlib1g-dev \
    libbz2-dev \
    libpopt-dev \
    libxml2-dev \
    libarchive-dev \
    libreadline-dev \
    libselinux1-dev \
    libsepol1-dev \
    libcap-dev \
    libdbus-1-dev \
    libsqlite3-dev \
    ${python}-all-dev \
    bzip2 \
    pkg-config \
    libnspr4-dev \
    libnss3-dev \
    liblzma-dev \
    xz-utils \
    libmagic-dev \
    libelf-dev \
    libdw-dev \
    libdb-dev \
    liblua5.2-dev \
    libselinux-dev \
    libsemanage-dev \
    || exit 1


# switch to builddir
################################################################################
mkdir -p "$builddir"
cd "$builddir"


# download and extract sources
################################################################################
wget -O "$filename" "$url" || exit 1
rm -rf "${package}-${version}"
tar -xf $filename || exit 1


# build and install binaries and libraries
################################################################################
cd "${package}-${version}"

libpython="$(pkg-config --libs $python)"
libpython="${libpython#-l}"

sed -i "s/\\[python\\\${PYTHON_VERSION} python\\]/[$libpython]/" configure.ac || exit 1
sed -i "s/\\[lua >= 5\\.1\\]/[lua5.2 >= 5.2]/" configure.ac || exit 1

autoreconf -i -f || exit 1
./configure \
    --build=x86_64-linux-gnu \
    --prefix=/usr \
    --includedir=/usr/include \
    --mandir=/usr/share/man \
    --infodir=/usr/share/info \
    --sysconfdir=/etc \
    --localstatedir=/var \
    --libdir=/usr/lib/x86_64-linux-gnu \
    --libexecdir=/usr/lib/x86_64-linux-gnu \
    --disable-maintainer-mode \
    --disable-dependency-tracking \
    --datadir=/usr/share \
    --with-external-db \
    --with-lua \
    --with-debian \
    --with-vendor=debian \
    --with-cap \
    --with-selinux \
    --enable-shared \
    --enable-python \
    LDFLAGS="-Wl,-z,relro -Wl,--as-needed" \
    CPPFLAGS="-D_FORTIFY_SOURCE=2 $(pkg-config --cflags nss)" \
    PYTHON="/usr/bin/$python" \
    || exit 1

make || exit 1
sudo make install || exit 1


# initialize rpm database
################################################################################
sudo rpm --initdb || exit 1


# build and install python modules
################################################################################
cd "python"

$VIRTUAL_ENV/bin/python setup.py install --prefix=$VIRTUAL_ENV || exit 1
