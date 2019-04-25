Name:		test-build-log-hooks
Version:	0.1
Release:	1%{?dist}
Summary:	Package for testing build log hooks

License:	BSD
Source0:	https://integration:4430/pkgs/%{name}/%{name}-%{version}.tar.gz

BuildArch:	noarch


%description
Test package


%package devel
Summary:	Test subpackage


%description devel
Test subpackage


%prep
%setup -q


%install
%make_install


%files
%license LICENSE README
%license /licensedir/test_license
/dirA/fileA
/dirA/fileB

%files devel
%doc docs_dir/AUTHORS
/dirB/fileX
/dirB/fileY
/dirB/fileZ


%changelog
* Thu Dec 06 2018 root - 0.1-1
- first version



