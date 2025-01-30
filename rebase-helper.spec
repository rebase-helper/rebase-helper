Name:           rebase-helper
Version:        0.29.3
Release:        %autorelease
Summary:        The tool that helps you to rebase your package to the latest version

License:        GPL-2.0-or-later
URL:            https://github.com/rebase-helper/rebase-helper
Source0:        %{pypi_source rebasehelper}

BuildArch:      noarch

BuildRequires:  make
BuildRequires:  python%{python3_pkgversion}-devel

BuildRequires:  pandoc
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
%autosetup -p1 -n rebasehelper-%{version}

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
%pyproject_save_files rebasehelper

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
%autochangelog
