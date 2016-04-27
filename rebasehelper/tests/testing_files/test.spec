Summary: A testing spec file
Name: test
Version: 1.0.2
Release: 33%{?dist}
License: GPL2+
Group: System Environment
URL: http://testing.org

# Note: non-current tarballs get moved to the history/ subdirectory,
# so look there if you fail to retrieve the version you want
Source: ftp://ftp.test.org/%{name}-%{version}.tar.xz
Source1: source-tests.sh
Source2: ftp://test.com/test-source.sh
#Source3: source-tests.sh
Source4: file.txt.bz2
Source5: documentation.tar.xz
Source6: misc.zip
Patch1: test-testing.patch
Patch2: test-testing2.patch
Patch3: test-testing3.patch
Patch4: test-testing4.patch

BuildRequires: openssl-devel, pkgconfig, texinfo, gettext, autoconf

%description
Testing spec file

%package devel
Summary: A testing devel package

%description devel
Testing devel spec file

%prep
%setup -q -a 5
%patch1
%patch2 -p1
%patch3 -p1 -b .testing3
%patch4 -p0 -b .testing4
mkdir misc
tar -xf %{SOURCE6} -C misc

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

%files
%{_bindir}/file.txt

%files devel
%{_bindir}/test_example
%{_libdir}/my_test.so

%changelog
* Wed Nov 12 2014 Tomas Hozza <thozza@redhat.com> 1.0.0-33
- Bump the release for testing purposes

* Tue Sep 24 2013 Petr Hracek <phracek@redhat.com> 1.0.0-1
- Initial version

