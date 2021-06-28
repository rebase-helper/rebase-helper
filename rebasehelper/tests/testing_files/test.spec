%{!?specfile: %global specfile spec file}
%global summary %{?longsum}%{!?longsum:A testing %{specfile}}

%global version_major 1
%global version_minor 0
%global version_patch 2
%global version_major_minor %{version_major}.%{version_minor}
%global version %{version_major_minor}.%{version_patch}

%global release 34
%global release_str %{release}%{?dist}

%global project rebase-helper
%global commit d70cb5a2f523db5b6088427563531f43b7703859

Summary: %{summary}
Name: test
Version: %{version}
Release: %{release_str}
License: GPL2+
Group: System Environment

# Regression test for #855: https://github.com/rebase-helper/rebase-helper/issues/855
%global domain testing
%global address %{domain}.org
%global full_address http://%{address}
URL: %{full_address}

# Note: non-current tarballs get moved to the history/ subdirectory,
# so look there if you fail to retrieve the version you want
Source: ftp://ftp.test.org/%{name}-%{version}.tar.xz
Source1: source-tests.sh
#Source3: source-tests.sh
Source5: documentation.tar.xz
Source6: misc.zip
Source8: https://github.com/%{project}/%{project}/archive/%{commit}/%{project}-%{commit}.tar.gz
Patch1: test-testing.patch
Patch2: test-testing2.patch
Patch3: test-testing3.patch
Patch4: test-testing4.patch

%{?use_workaround:Patch100: workaround_base.patch}

%if 0%{?use_workaround:1}
Patch101: workaround_1.patch
Patch102: workaround_2.patch
%else
Patch101: no_workaround.patch
%endif

%global prever b4
Patch1000: 0.7.%{?prever}%{?dist}
%global branch 1.22
Patch1001: %{branch}.1

BuildRequires: openssl-devel, pkgconfig, texinfo, gettext, autoconf
Recommends: test > 1.0.2

%description
Testing spec file

%package devel
Summary: A testing devel package

%description devel
Testing devel spec file

%prep
%setup -q -c -a 5
%patch1
%patch2 -p1
%patch3 -p1 -b .testing3
%patch4 -p0 -b .testing4
mkdir misc
tar -xf %{SOURCE6} -C misc

%build
autoreconf -vi # Unescaped macros %name %{name}

%Install
make DESTDIR=$RPM_BUILD_ROOT install

%files
/usr/share/man/man1/*
/usr/bin/%{name}

%changelog
* Wed Apr 26 2017 Nikola Forró <nforro@redhat.com> - 1.0.2-34
- This is chnagelog entry with some indentional typos

* Wed Nov 12 2014 Tomas Hozza <thozza@redhat.com> 1.0.0-33
- Bump the release for testing purposes

* Tue Sep 24 2013 Petr Hracek <phracek@redhat.com> 1.0.0-1
- Initial version

