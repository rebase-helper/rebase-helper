rebase-helper
------------------------------

This tool helps you to rebase package to the latest version

How the rebase-helper works:
- Each action should be logged and visible by user.
    - extract tarball with the existing sources to directory old_sources/<package_name>
    - extract tarball with the new sources to directory new_sources/<package_name>
    - Provide a list of patches mentioned in SPEC file
    - New spec file is stored in results/
- for all patches
    - apply patch to existing directory to old-sources/<package_name>
    - Try to apply patch to new-sources/<package_name> with fuzz=0
    - If the patch failed run a DiffHelper.mergetool to correct a patch
    - Save the corrected patch to results/<orig_name>.patch
    - Show diff between old patch and new patch and ask user if everything's ok
- create srpm from old and new spec files & new sources & patches (Builder)
- rebuild srpm -> RPMs (Builder)
- Run rpmdiff tool for finding libraries and header changes.
- Inform user what libraries and header files were changed.

[**Landscape.io scans of rebase-helper**](https://landscape.io/github/phracek/rebase-helper/)

Packages which needs to be installed before you execute rebase-helper:
- meld
- mock
- rpm-build
- pkgdiff at least 1.6.3
- python-six
