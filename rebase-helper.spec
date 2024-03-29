%global pkgname rebasehelper

Name:           rebase-helper
Version:        0.28.1
Release:        1%{?dist}
Summary:        The tool that helps you to rebase your package to the latest version

License:        GPLv2+
URL:            https://github.com/rebase-helper/rebase-helper
Source0:        %{pypi_source %{pkgname}}

BuildArch:      noarch

BuildRequires:  make
BuildRequires:  python%{python3_pkgversion}-devel

BuildRequires:  python%{python3_pkgversion}-m2r
BuildRequires:  python%{python3_pkgversion}-sphinx
BuildRequires:  python%{python3_pkgversion}-sphinx_rtd_theme

Recommends:     licensecheck
Recommends:     rpmlint
Recommends:     libabigail
Recommends:     pkgdiff >= 1.6.3
Recommends:     rpminspect-data-fedora


%description
rebase-helper is a tool which helps package maintainers to rebase their
packages to latest upstream versions.
There are several steps that need to be done when rebasing a package.
The goal of rebase-helper is to automate most of these steps.


%prep
%autosetup -p1 -n %{pkgname}-%{version}

# since we are building from PyPI source, we don't need git-archive
# support in setuptools_scm
sed -i 's/setuptools_scm\[toml\]>=7/setuptools_scm[toml]/' pyproject.toml


%generate_buildrequires
%pyproject_buildrequires -x testing


%build
%pyproject_wheel

# generate man page
make PYTHONPATH=$(pwd)/build/lib SPHINXBUILD=sphinx-build-3 man

# generate bash completion script
make PYTHON=%{python3} PYTHONPATH=$(pwd) completion

# generate sample configuration file
make PYTHON=%{python3} PYTHONPATH=$(pwd) sample_config


%install
%pyproject_install
%pyproject_save_files %{pkgname}

# install man page
mkdir -p %{buildroot}%{_datadir}/man/man1/
install -p -m 0644 docs/build/man/%{name}.1 %{buildroot}%{_datadir}/man/man1

# install bash completion
mkdir -p %{buildroot}%{_datadir}/bash-completion/completions/
install -p -m 0644 %{name}.bash %{buildroot}%{_datadir}/bash-completion/completions/%{name}


%check
%pytest


%files -f %{pyproject_files}
%doc README.md
%doc CHANGELOG.md
%doc %{name}.cfg
%{_bindir}/%{name}
%{_mandir}/man1/%{name}.1*
%{_datadir}/bash-completion/completions/%{name}


%changelog
* Thu Oct 26 2023 Nikola Forró <nforro@redhat.com> - 0.28.1-1
- New release 0.28.1

* Mon Feb 13 2023 Nikola Forró <nforro@redhat.com> - 0.28.0-1
- New release 0.28.0

* Fri Jun 24 2022 Nikola Forró <nforro@redhat.com> - 0.27.0-1
- New release 0.27.0

* Mon Sep 27 2021 Nikola Forró <nforro@redhat.com> - 0.26.0-1
- New release 0.26.0

* Tue Jul 13 2021 Nikola Forró <nforro@redhat.com> - 0.25.0-1
- New release 0.25.0

* Tue Feb 02 2021 Nikola Forró <nforro@redhat.com> - 0.24.0-1
- New release 0.24.0

* Wed Sep 30 2020 Nikola Forró <nforro@redhat.com> - 0.23.1-1
- New release 0.23.1

* Fri Aug 28 2020 Nikola Forró <nforro@redhat.com> - 0.23.0-1
- New release 0.23.0

* Mon Mar 30 2020 Nikola Forró <nforro@redhat.com> - 0.22.0-1
- New release 0.22.0

* Fri Feb 21 2020 Nikola Forró <nforro@redhat.com> - 0.21.0-1
- New release 0.21.0

* Fri Dec 06 2019 Nikola Forró <nforro@redhat.com> - 0.20.0-1
- New release 0.20.0

* Thu Sep 26 2019 Nikola Forró <nforro@redhat.com> - 0.19.0-1
- New release 0.19.0

* Wed Aug 21 2019 Nikola Forró <nforro@redhat.com> - 0.18.0-1
- New release 0.18.0

* Fri Aug 09 2019 Nikola Forró <nforro@redhat.com> - 0.17.2-1
- New release 0.17.2

* Thu Aug 01 2019 Nikola Forró <nforro@redhat.com> - 0.17.1-1
- New release 0.17.1

* Fri May 03 2019 Nikola Forró <nforro@redhat.com> - 0.16.3-1
- New release 0.16.3

* Fri Mar 01 2019 Nikola Forró <nforro@redhat.com> - 0.16.1-1
- New release 0.16.1

* Sat Feb 02 2019 Fedora Release Engineering <releng@fedoraproject.org> - 0.15.0-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_30_Mass_Rebuild

* Thu Dec 27 2018 Igor Gnatenko <ignatenkobrain@fedoraproject.org> - 0.15.0-2
- Enable python dependency generator

* Fri Dec 21 2018 Nikola Forró <nforro@redhat.com> - 0.15.0-1
- New release 0.15.0

* Fri Oct 05 2018 Nikola Forró <nforro@redhat.com> - 0.14.0-1
- New release 0.14.0

* Sat Jul 14 2018 Fedora Release Engineering <releng@fedoraproject.org> - 0.13.2-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_29_Mass_Rebuild

* Tue Jun 19 2018 Miro Hrončok <mhroncok@redhat.com> - 0.13.2-2
- Rebuilt for Python 3.7

* Wed May 23 2018 Nikola Forró <nforro@redhat.com> - 0.13.2-1
- New release 0.13.2 (#1562375)

* Fri Feb 09 2018 Fedora Release Engineering <releng@fedoraproject.org> - 0.12.0-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_28_Mass_Rebuild

* Tue Dec 19 2017 Nikola Forró <nforro@redhat.com> - 0.12.0-1
- New release 0.12.0 (#1527597)

* Wed Oct 04 2017 Nikola Forró <nforro@redhat.com> - 0.11.0-1
- New release 0.11.0 (#1498782)

* Wed Aug 30 2017 Nikola Forró <nforro@redhat.com> - 0.10.1-1
- New release 0.10.1 (#1486607)

* Fri Aug 25 2017 Nikola Forró <nforro@redhat.com> - 0.10.0-1
- New release 0.10.0 (#1485315)
- Update for python3

* Thu Jul 27 2017 Fedora Release Engineering <releng@fedoraproject.org> - 0.9.0-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_27_Mass_Rebuild

* Sat Feb 11 2017 Fedora Release Engineering <releng@fedoraproject.org> - 0.9.0-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_26_Mass_Rebuild

* Mon Jan 16 2017 Nikola Forró <nforro@redhat.com> - 0.9.0-1
- New release 0.9.0
- Install generated man page
- Add missing python-copr dependency (#1391461)

* Tue Nov 22 2016 Petr Hracek <phracek@redhat.com> - 0.8.0-3
- Fix for result dir (#1397312)

* Wed Aug 17 2016 Petr Hracek <phracek@redhat.com> - 0.8.0-2
- Fix bug caused by dependency to python-pyquery (#1363777)

* Sun Jul 31 2016 Tomas Hozza <thozza@redhat.com> - 0.8.0-1
- New release 0.8.0

* Tue Jul 19 2016 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 0.7.3-3
- https://fedoraproject.org/wiki/Changes/Automatic_Provides_for_Python_RPM_Packages

* Thu May 26 2016 Nikola Forró <nforro@redhat.com> - 0.7.3-2
- Clear output data on Application initialization

* Mon Apr 11 2016 Petr Hracek <phracek@redhat.com> - 0.7.3-1
- New upstream release 0.7.3. It contains fixes. (#1325599)

* Tue Mar 15 2016 Petr Hracek <phracek@redhat.com> - 0.7.2-1
- New upstream release 0.7.2

* Mon Feb 22 2016 Petr Hracek <phracek@redhat.com> - 0.7.1-1
- New upstream version 0.7.1 (#1310640)

* Thu Feb 04 2016 Fedora Release Engineering <releng@fedoraproject.org> - 0.7.0-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_24_Mass_Rebuild

* Wed Jan 13 2016 Petr Hracek <phracek@redhat.com> - 0.7.0-1
- New upstream version 0.7.0 (#1298403)

* Mon Nov 09 2015 Petr Hracek <phracek@redhat.com> - 0.6.2-1
- New upstream version 0.6.2 (#1280294)
- support upstream monitoring service

* Fri Jul 31 2015 Petr Hracek <phracek@redhat.com> - 0.6.0-1
- New upstream version 0.6.0 (#1249518)

* Thu Jun 18 2015 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 0.5.0-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_23_Mass_Rebuild

* Mon May 25 2015 Petr Hracek <phracek@redhat.com> - 0.5.0-1
- New upstream version 0.5.0 #1224680

* Thu Mar 05 2015 Petr Hracek <phracek@redhat.com> - 0.4.0-3
- Add man page (#1185985)

* Mon Jan 19 2015 Petr Hracek <phracek@redhat.com> - 0.4.0-2
- Remove dependency to pkgdiff from setup (#1176563)

* Fri Dec 05 2014 Petr Hracek <phracek@redhat.com> - 0.4.0-1
- New upstream release

* Fri Jul 25 2014 Petr Hracek <phracek@redhat.com> - 0.3.1-1
- New upstream release
- Add --build-only option
- Catch Keyboard Interupted
- Add --continue option for rebases

* Tue Jul 08 2014 Tomas Hozza <thozza@redhat.com> - 0.3.0-0.4.20140624git
- Add requires on pkgdiff

* Mon Jun 23 2014 Petr Hracek <phracek@redhat.com> - 0.3.0-0.3.20140624git
- Include LICENSE text file
- use __python2 macros

* Mon Jun 23 2014 Petr Hracek <phracek@redhat.com> - 0.3.0-0.2.20140623git
- Removed shebang from __init__.py file

* Mon Jun 23 2014 Petr Hracek <phracek@redhat.com> - 0.3.0-0.1.20140623git
- Initial version
