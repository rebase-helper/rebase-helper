Introduction
============

Let's summarize what is included by default and some future aims for the `rebase-helper`:

This tool helps you to rebase package to the latest version

How the rebase-helper works
---------------------------

- Each action should be logged and visible by user.
    - Extract tarball with the existing sources to directory old_sources/<package_name>.
    - Extract tarball with the new sources to directory new_sources/<package_name>.
    - Provide a list of patches mentioned in SPEC file.
    - New spec file is stored in results/.
- Apply all patches with git command to old_sources/<package_name> directory.
- Add new_sources/<package_name> -> old_sources/<package_name>
    with command ``git rebase --onto new_sources <inital_commit> <last_commit>``.
- Solve all conflicts which arise during the ``git rebase``.
- Create srpm from old and new spec files & new sources & patches (Builder).
- Rebuild srpm -> RPMs (Builder).
- Run rpmdiff tool for finding libraries and header changes.
- Inform user what libraries and header files were changed.

Requirements
------------

- meld
- mock
- rpm-build
- pkgdiff at least 1.6.3
- python-six
- koji
- pyrpkg
- libabigail

How to execute rebase-helper CLI
-------------------------------------

Go to a git directory of your package and execute command:

``/path_to_rebase-helper/rebase-helper.py <new_upstream_version> (e.g. /home/user/phracek/rebase-helper/rebase-helper.py "3.1.10")``
