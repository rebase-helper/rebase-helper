Summary: A testing spec file
Name: test
Version: 1.0.2
Release: 1%{?dist}
License: GPL2+
Group: System Environment
URL: http://testing.org

# Note: non-current tarballs get moved to the history/ subdirectory,
# so look there if you fail to retrieve the version you want
Source0: ftp://ftp.test.org/test-%{version}.tar.xz
Source1: source-tests.sh
Source2: ftp://test.com/test-source.sh
Patch1: test-testing.patch
Patch2: test-testing2.patch
Patch3: test-testing3.patch

BuildRequires: openssl-devel, pkgconfig, texinfo, gettext, autoconf

%description
The libpng package contains a library of functions for creating and
manipulating PNG (Portable Network Graphics) image format files.  PNG
is a bit-mapped graphics format similar to the GIF format.  PNG was
created to replace the GIF format, since GIF uses a patented data
compression algorithm.

Libpng should be installed if you need to manipulate PNG format image
files.

%prep
%setup -q
%patch1
%patch2 -p1
%patch3 -p1 -b .testing3

%build
autoreconf -vi

%configure
make TEST

%install
make DESTDIR=$RPM_BUILD_ROOT install

%check
#to run make check use "--with check"
%if %{?_with_check:1}%{!?_with_check:0}
make check
%endif

%changelog
* Tue Sep 24 2013 Petr Hracek <phracek@redhat.com> 1.0.0-1
- Initial version

