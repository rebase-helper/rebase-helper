Name:           test
Version:        0.1
Release:        1%{?dist}
Summary:        Test package

License:        BSD
Source0:        https://integration:4430/pkgs/%{name}/%{name}-%{version}.tar.gz
Patch0:         applicable.patch
Patch1:         conflicting.patch
Patch2:         backported.patch

BuildRequires:  gcc


%description
Test package


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
%{_libdir}/*.so


%changelog
* Thu Jun 07 2018 Nikola Forró <nforro@redhat.com> - 0.1-1
- first version
