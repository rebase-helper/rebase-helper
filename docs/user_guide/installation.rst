Installation
============

:program:`rebase-helper` is packaged in Fedora, so you can just install it with :command:`dnf`.

If you can't or don't want to use :program:`rebase-helper` package, you have to install,
apart from Python requirements listed in `get_requirements` function in :file:`setup.py`,
the following dependencies:

============ ======================== =================================================
Dependency   Package name (in Fedora) Notes
============ ======================== =================================================
git          git                      for rebasing of downstream patches
rpmbuild     rpm-build                for building SRPM and for **rpmbuild** build tool
mock         mock                     for **mock** build tool, optional
koji         koji                     for **koji** build tool, optional
rpmdiff      rpmlint                  for **rpmdiff** checker, optional
abipkgdiff   libabigail               for **abipkgdiff** checker, optional
pkgdiff      pkgdiff                  for **pkgdiff** checker, optional
csmock       csmock                   for **csmock** checker, optional
licensecheck licensecheck             for **licensecheck** checker, optional
============ ======================== =================================================

:program:`rebase-helper` is also published on `PyPI <https://pypi.org/project/rebasehelper/>`_.
