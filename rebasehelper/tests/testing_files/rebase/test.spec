Name:           test
Version:        0.1
Release:        1%{?dist}
Summary:        Test package

License:        BSD
Source0:        https://integration:4430/pkgs/rpms/%{name}/%{name}-%{version}.tar.gz
Patch0:         applicable.patch
Patch1:         conflicting.patch
Patch2:         backported.patch
Patch3:         renamed-%{version}.patch

BuildRequires:  gcc make


%description
Test package


%package extra
Summary:        Test subpackage


%description extra
Test subpackage


%prep
%setup -q
%patch0 -p1
%patch1 -p1
%patch2 -p1


%build
%set_build_flags
%make_build


%install
%make_install


%files
%license LICENSE
%doc README.md CHANGELOG.md
%doc %{_docdir}/%{name}/notes.txt
%{_libdir}/*.so*
%{_datadir}/%{name}/0.dat
%{_datadir}/%{name}/1.dat


%files extra
%doc data/extra/README.extra
%{_datadir}/%{name}/extra/A.dat
%{_datadir}/%{name}/extra/B.dat
%{_datadir}/%{name}/extra/C.dat


%changelog
* Thu Jun 07 2018 Nikola Forró <nforro@redhat.com> - 0.1-1
- first version
