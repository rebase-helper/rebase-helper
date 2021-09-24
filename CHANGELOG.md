# Change Log

## [Unreleased]

## [0.26.0] - 2021-09-27
### Added
- Added support for SPEC files with no Source tags

### Fixed
- Fixed traceback on setting original locale
- `rpmdiff` is now called with long options to workaround a bug in argument parsing

### Changed
- Employed Github Actions for CI and PyPI deployment
- Character encoding is now explicitly specified everywhere, to conform with PEP597
- Made `copr` project creation more robust

## [0.25.0] - 2021-07-13
### Added
- Added lookaside cache preset for **centpkg**

### Fixed
- Started using C locale for updating *%changelog* section
- Fixed documentation builds with Sphinx 4
- Fixed macro value detection in `SpecFile.set_tag()`
- Fixed **licensecheck** availability test

### Changed
- Moved from using deprecated `--old-chroot` `mock` option to `--isolation simple`
- Migrated from Travis CI to Github Actions
- Moved away from soon-to-be-deprecated distutils

## [0.24.0] - 2021-02-02
### Added
- Added `--lookaside-cache-preset` option to enable using different lookaside cache configuration presets
- Added `--no-changelog-entry` option to prevent **rebase-helper** from generating an entry in *%changelog* section
- Added `--keep-comments` option to disable removing comments

### Fixed
- Fixed removing accompanying comments alongside patches
- Fixed broken `--get-old-build-from-koji` option

### Changed
- Switched to new format of Fedora lookaside cache URLs
- Limited **koji** builds to *x86_64* (it's a waste of resources until **rebase-helper** fully supports other architectures)
- Suppressed harmless errors produced by `rpm` when expanding and deleting macros
- Paths in patches are now sanitized before applying with `git apply`, to allow dealing with unusual patch formats
- `SpecFile._process_patches()` method has been replaced with a public `SpecFile.process_patch_macros()` method

## [0.23.1] - 2020-09-30
### Fixed
- Fixed uploads to Fedora lookaside cache and improved error handling
- A build is no longer retried as a result of checker failure

### Changed
- `SpecFile.set_version()` and `SpecFile.set_release()` now allow disabling of preserving macros
- **rpminspect** checker now uses `rpminspect-fedora`

## [0.23.0] - 2020-08-28
### Added
- Added **rpminspect** checker

### Fixed
- **rebase-helper** is now able to deal with existing git repository in extracted upstream sources
- Prevented git commands executed in the background from launching an interactive editor and effectively rendering **rebase-helper** unusable
- Outputs of checkers are now removed before subsequent runs
- Tilde is now recognized as extra version separator
- `make test-podman` has been updated to work with the latest podman

### Changed
- Checker outputs are now ordered by type in the text report
- Excessive blank lines are now removed from the SPEC file when removing patches
- Sources and patches are now automatically renamed, if necessary
- **abipkgdiff** now falls back to comparing without debuginfo in case it is unable to read it from the provided debuginfo packages

## [0.22.0] - 2020-03-31
### Added
- Added more type hints, including all public API methods

### Fixed
- `SpecFile.reload()` no longer pointlessly calls `SpecFile._read_spec_content()`
- Deleted files are now skipped when detecting unresolved conflicts during `git rebase`
- Fixed detection of Koji log file containing build failure
- Adapted to changes in git 2.26.0
- Fixed unhandled exception during upload to lookaside cache

### Changed
- Removed no longer necessary workarounds from Fedora base images
- Simplified packit configuration
- Options `--pkgcomparetool`, `--versioneer-blacklist`, `--spec-hook-blacklist` and `--build-log-hook-blacklist` can now be specified without an argument to indicate none of the tools/hooks should be run

## [0.21.0] - 2020-02-21
### Added
- Added public API tests for `Tags` class
- Added support for *%patchlist* and *%sourcelist*
- Added support for automatic *Source*/*Patch* numbering

### Fixed
- **commit-hash-updater** SPEC hook now handles empty release name
- *sources* is now ignored if it's not a regular file
- Fixed summary and report paths when using `--bugzila-id` or `--results-dir`
- Fixed and extended detection of ABI changes reported by **abipkgdiff**
- Removed deprecated encoding parameter in `json.load()` for Python 3.9
- Fixed processing of remote patches
- Fixed handling of intermediate macros in `SpecFile.set_tag()`

### Changed
- All RPM macros are now reset when `SpecFile` object is destroyed
- Renamed docker directory to containers and Dockerfiles to Containerfiles
- Switched from Docker Hub to quay.io for automatic image building
- Improved and cleaned up `SpecFile` tests
- **replace-old-version** SPEC hook can now replace also extraversion

## [0.20.0] - 2019-12-06
### Added
- Introduced `Tags` class unifying and simplifying access to SPEC tags
- Added proper support for *crate* and *gem* archives
- Added `--bugzilla-id` option to perform a rebase based on *Upstream Release Monitoring* bugzilla
- Added `-D`/`--define` option to define macros
- Added tests for public API

### Fixed
- Fixed `--build-tasks` option
- Fixed detecting unresolved conflicts in non-UTF-8 files
- Prevented loss of messages logged before logging file handlers are created
- **rebase-helper** now skips unparseable lines in *%prep* instead of tracebacking on them
- Fixed parsing SPEC files with `-h` in *%prep*
- Fixed processing SPEC files with zero-padded indexed tags and `%patch` macros

### Changed
- Completely reworked dealing with extraversions
- Improved `SpecFile.set_tag()` to minimize changes made to the SPEC file

## [0.19.0] - 2019-09-26
### Added
- Added `--workspace-dir` option to allow specifying custom workspace directory
- Added **sonamecheck** checker for detecting *SONAME* changes
- Added `--copr-project-permanent`, `--copr-project-frontpage` and `--copr-chroots` options

### Fixed
- Strings like "1" are no longer replaced with macros in *%prep*
- SPEC files without *Source0* tag are now handled correctly
- Fixed **copr** build tool, switched to V3 API
- Avoided parsing SPEC without properly setting `%{_sourcedir}` macro first

### Changed
- Introduced `RpmHeader` class for more convenient access to package header attributes
- Modification of *Patch* tags now preserves whitespace to minimize differences in SPEC
- Moved Bash completion script from `/etc/bash_completion.d` to `/usr/share/bash-completion/completions`

### Removed
- Removed non-working `--patch-only`, `--build-only` and `--comparepkgs-only` options
- Temporarily removed `--continue` option
- Removed no longer used `python3-six` build dependency
- Removed `copr` workaround in favor of making **copr** build tool unavailable in case it's not working

## [0.18.0] - 2019-08-21
### Added
- Added workaround for missing *mock* group in Fedora Rawhide

### Fixed
- Moved setup dependencies from `install_requires` to `setup_requires`

### Changed
- Refactored logging, see [logging documentation](https://rebase-helper.readthedocs.io/en/latest/user_guide/logging.html) for details
- Reason of build failure is now always logged

### Removed
- Removed unused `Application` methods and attributes
- Removed unused testing files

## [0.17.2] - 2019-08-09
### Added
- Added tests for `SpecContent` class
- Enabled and configured [Packit-as-a-Service](https://packit.dev/packit-as-a-service/)

### Fixed
- Added exception handling to PyPI release webhook endpoint
- Fixed `TestCLI.test_cli_unit()` test
- Updated `MANIFEST.in` to include all necessary files

### Changed
- Improved tests for `Application` class
- `SpecFile.update_changelog()` now creates *%changelog* section if it doesn't exist
- **rebase-helper** now uses `setuptools-scm` to determine version from git
- `setup.py sdist` now supports overriding distribution base name with `--base-name` option

## [0.17.1] - 2019-08-01
### Fixed
- Fixed PyPI release webhook endpoint

### Changed
- Removed direct dependencies preventing PyPI release

## [0.17.0] - 2019-07-31
### Added
- Added possibility for plugins to specify their own arguments
- Added basic type hints and enabled mypy linter
- Added *rust* package category
- **replace-old-version** SPEC hook can now replace old version with `%{version}` macro
- **replace-old-version** SPEC hook can now replace also parts of version in Sources and Patches

### Fixed
- Fixed broken ansicolors dependency
- Fixed printing of output of unavaiable checkers
- Fixed determining unmatched quotation in *%prep* section
- Made **files** build log hook handle conditions and macros in *%files* section
- **files** build log hook now adds man pages in a way that follows [Fedora Packaging Guidelines](https://docs.fedoraproject.org/en-US/packaging-guidelines/#_manpages)
- **files** build log hook now ignores debuginfo files
- Fixed issues with polluted global macro namespace when parsing multiple different SPEC files
- Fixed handling of remote downstream patches (URLs)
- Fixed parsing of patch strip options in *%prep*
- Fixed wrapping of extra long lines in the usage documentation
- Sources from lookaside cache are now downloaded to a proper location

### Changed
- Restructured the code layout of plugins
- Refactored parts of SpecFile class
- Disabled removing of "unused" patches
- `mock` is now automatically run with superuser privileges if necessary
- Local builder is now used if `--get-old-build-from-koji` is specified and the build can't be downloaded from Koji
- checkers (even the default ones) are now skipped if they are not available
- Sources are now copied to destination if they cannot be extracted
- Reimplemented downloading Koji builds
- Updated documentation

### Removed
- Removed Python 2 support

## [0.16.3] - 2019-05-03
### Fixed
- Fixed handling of SPEC files with conditionalized sections
- Fixed **replace-old-version** SPEC hook not to update version in *%changelog* and local sources
- Fixed capturing RPM error output during SPEC parsing
- Fixed handling of absolute *%license* and *%doc* paths in **files** build log hook
- Fixed logging of SRPM and RPM build errors

### Changed
- Updated packit configuration for packit 0.2.0
- Adapted to upcoming change in RPM python API
- Made `SpecFile` class more suitable for external use

## [0.16.2] - 2019-03-07
### Added
- Added support for [packit](https://github.com/packit-service/packit)
- Added SPEC hook for replacing old version string

### Fixed
- Fixed documentation building by mocking `requests-gssapi`
- Fixed `TestOutputTool` for checkers

### Changed
- Build log hooks are now run only if build of **new** binary packages fails
- It is now possible to use `--get-old-build-from-koji` option without FAS

## [0.16.1] - 2019-02-28
### Fixed
- Made `GitPatchTool` auto-skip empty commits caused by new rebase implementation in **git** 2.20
- Fixed `TestGitHelper` to work on real systems with existing git configuration

## [0.16.0] - 2019-02-27
### Added
- Added category for *R* packages
- Added `make test-podman` as an alternative to `make test-docker`
- Added `--skip-upload` option (to be used in conjunction with `--update-sources`)
- Added check that all sources for the new version are present
- Added SPEC hook for escaping macros in comments

### Changed
- `--get-old-build-from-koji` now tries to get specific version build (as opposed to the latest one)
- Implemented parsing of multiline macros and shell expansions in SPEC files
- **rebase-helper** can now handle multiline enquoted strings in *%prep* section
- Refactored `GitPatchTool` to make the rebase process more robust and to preserve as much of the original downstream patches as possible
- `git mergetool` is now run again if there are some unresolved conflicts left
- Associated comments are now removed along with patches

### Fixed
- Fixed populating list of logs on build failures
- Added missing abort after failed `git am`
- Fixed processing SPEC files without *%prep* section
- Fixed several issues in **ruby-helper** SPEC hook
- Fixed unwanted expansion of *%autosetup* macro
- Fixed automatic rebulding based on build log hooks result
- Fixed removal of *%doc* and *%license* files in subpackages

### Removed
- Removed `requests-kerberos` support and switched to `requests-gssapi` exclusively

## [0.15.0] - 2018-12-21
### Added
- Implemented build log hooks and added **files** hook to detect and fix missing/unpackaged files

### Changed
- Refactored and simplified all plugins

### Fixed
- Fixed not listing all argument choices while generating documentation
- Fixed error in parsing rpmdiff output
- Fixed insertion of extra blank lines to a SPEC file after removing patches

### Removed
- Removed unneeded packages from base Docker image

## [0.14.0] - 2018-10-04
### Added
- Added **PathsToRPMMacros** SPEC hook for transforming paths in *%files* section
- Added `--favor-on-conflict` option to prefer upstream or downstream changes with conflicting patches

### Changed
- Extended **PyPIURLFix** SPEC hook to incorporate the new https://pypi.org website
- Made processing of patches in a SPEC file more robust
- Rewritten functional test to use an artificial package designed to check most aspects of the rebase process
- `pylint` is now run with Python 3 only, as Python 2 variant is no longer supported
- Code refactoring, simplified `SpecFile` class
- Checkers are no longer required for **rebase-helper** to run, only available checkers are used

### Fixed
- Fixed bug in **licensecheck** checker when used with **json** output tool
- Fixed SPEC hook tests
- Fixed strangely acting lookaside cache upload progressbar
- Fixed downloading of SRPMs with `--get-old-build-from-koji`
- Fixed building usage documentation

## [0.13.2] - 2018-05-18
### Added
- Added **licensecheck** checker for detecting license changes
- Added another *not-so-verbose* verbosity level

### Changed
- Refactored `utils` module

### Fixed
- Fixed **abipkgdiff** detecting changes in only one object file
- Fixed uploads to lookaside cache
- Fixed broken consequent build retries

## [0.13.1] - 2018-04-19
### Added
- Added `--apply-changes` option to apply *changes.patch* after successful rebase
- Implemented *.gitignore* update with `--update-sources`

### Changed
- Extended `README.md`
- Cleaned up constants

### Fixed
- Fixed crash after failed rebase when no checkers were run

## [0.13.0] - 2018-03-29
### Added
- Added possibility to make changes to specfile between build retries
- Added **CommitHashUpdater** SPEC hook
- Added **hackage** versioneer
- Added support for uncompressed tar archives
- Created integration environment for test suite to isolate it from the internet
- Added `--update-sources` option to update *sources* file and upload new sources to lookaside cache

### Changed
- Switched to `requests` library for downloads
- Made error messages from **Koji** builds more useful
- Reworked handling of downstream patches
- Changed package build process to build first SRPMs and then RPMs
- Divided checkers into categories running at different phases of rebase
- **Koji** build tool refactored to be better adjustable and extensible
- Colorized **rebase-helper** output and enhanced log messages
- Significatly improved rebase summary and report

### Fixed
- Fixed `TestConsoleHelper.test_get_message()` test
- Fixed bug in **rpmdiff** output analysis
- Fixed some code styling errors and a large number of issues found by static analysis

## [0.12.0] - 2017-12-19
### Added
- Added **npmjs** and **cpan** versioneers
- Added possibility to specify custom py.test arguments
- Added possibility to customize changelog entry
- Added version check to abort rebase if requested version is not newer than current
- Added separate tox tasks for linting
- Implemented **rpmbuild** and **mock** SRPM build tools
- Added possibility to configure rebase-helper with configuration file
- Added possibility to blacklist certain SPEC hooks or versioneers
- Created `rebasehelper/rebase-helper` Docker Hub repository

### Changed
- Made several speed optimizations in the test suite
- Tests requiring superuser privileges are now automatically skipped if necessary
- Simplified build analysis and made related log messages more useful

### Fixed
- Fixed documentation builds on readthedocs.org broken by *rpm distribution* requirement
- Fixed reading username and e-mail from git configuration
- Added missing dependencies to Dockerfile
- Fixed processing of custom builder options
- Added workarounds for RPM bugs related to `%sources` and `%patches`
- Fixed several unhandled exceptions
- Fixed parsing tarball filename containing certain characters

## [0.11.0] - 2017-10-04
### Added
- Added `rpm-py-installer` to install `rpm-python` from pip
- Implemented detection of package category (*python*, *perl*, *ruby*, *nodejs*, *php*)
- Added **RubyGems** versioneer
- Added **RubyHelper** SPEC hook for getting additional sources based on instructions in SPEC file comments

### Changed
- Value of *Version* and *Release* tags is now preserved if there are any macros that can be modified instead
- Versioneers and SPEC hooks are now run only for matching package categories
- Bash completion is now generated from source code, so it is always up-to-date

### Fixed
- Prevented unwanted modifications of *%prep* section
- Fixed unexpected removal of rpms and build logs after last build retry
- Added files are no longer listed as removed in **rpmdiff** report

## [0.10.1] - 2017-08-30
### Added
- Added `--version` argument

### Changed
- **Anitya** versioneer now primarily searches for projects using Fedora mapping
- Python dependencies moved from `requirements.txt` to `setup.py`

### Fixed
- Made `CustomManPagesBuilder` work with Sphinx >= 1.6
- *%prep* section parser is now able to handle backslash-split lines

## [0.10.0] - 2017-08-25
### Added
- Implemented extensible SPEC hooks and versioneers
- Added **PyPI** SPEC hook for automatic fixing of Source URL of Python packages
- Added **Anitya** and **PyPI** versioneers for determining latest upstream version of a package
- Added possibility to download old version build of a package from Koji
- Added support for test suite to be run in Docker containers
- Implemented functional tests for automatic testing of whole rebase process
- Diff against original source files is now generated as *changes.patch*

### Changed
- Introduced plugin system for extending build tools, checkers and output tools
- Updated for **Koji 1.13** which finally brings Python 3 support
- Improved output information and reports
- Added colorized output
- Improved project documentation

### Fixed
- Pre-configured git username and e-mail address is now used if available
- Fixed several issues in **rpmdiff** and especially **abipkgdiff** checkers
- Fixed several test suite related issues


## [0.9.0] - 2017-01-05
### Added
- Old sources are now downloaded from Fedora lookaside cache
- Auto-generated and improved CLI documentation and man page
- Added support for downloading files of unknown size

### Changed
- `SpecFile` class preparation for pre-download hooks
- Code cleanup and refactorization

### Fixed
- Fixed regexp for getting release number from SPEC
- Fixed functionality of `--results-dir` option
- Several upstream monitoring fixes
- Fixed issues caused by Fedora Flag Day


## [0.8.0] - 2016-07-31
### Added
- Added support for JSON output format
- Added support for **copr** build tool
- Added support for passing arbitrary extra arguments to local builders (**mock**, **rpmbuild**) with `--builder-options`.
- Added new option `--build-retries` allows the user to specify number of build retries (by default *2*)
- Added support for **csmock** check tool

### Changed
- Renamed **fedpkg** build tool to **koji** to make it more clear
- Downloading of files is now done only using standard Python library and not using PyCURL

### Fixed
- Many bug fixes and code clean up


## [0.7.3] - 2016-04-08
### Added
- Added `rpm.addMacro`

### Fixed
- Handled exceptions raised during parsing of SPEC files
- Fixed unapplied patches mixing with deleted ones


## [0.7.2] - 2016-03-15
### Added
- Added information about scratch builds

### Fixed
- Added check if file exists and is empty for **the-new-hotness**
- Patches are applied in case `--builds-nowait` option is used


## [0.7.1] - 2016-02-22
### Added
- Two new command line options used by upstream monitoring

### Fixed
- **fedpkg** reimplementation


## [0.7.0] - 2016-01-13
### Changed
- Several improvements

### Fixed
- **pkgdiff** is now smarter
- Included `tar.bz2` into list of supported formats
- Added support for noarch package in case of **fedpkg** build
- Checker should return `None` if there is no debug package

### Removed
- Removed a bunch of debug stuff


## [0.6.2] - 2015-11-09
### Fixed
- Logs are being saved to their own directory
- Prep script is moved into workspace directory
- No more traceback in case `koji` module is not present
- Each checker creates its own log file
- **rebase-helper** informs if it failed or not
- Report on script is smarter


## [0.6.1] - 2015-10-30
### Added
- `upstream-monitoring.py` - used by upstream monitoring service
- `rebase-helper-fedmsg.py` - testing Python script


## [0.6.0] - 2015-07-31
### Added
- Parts of `%prep` section related to patching are executed
- Support for **abipkgdiff**

### Fixed
- Several fixes
- Replaced `yum` with `dnf`


## [0.5.0] - 2015-05-22
### Added
- Added support for building packages via **fedpkg** (or **koji**)
- Added summary report for better overview
- `continue` option implemented for `git rebase`
- Added several tests
- Added class for operating with Git repositories

### Changed
- `git rebase` is used instead of `patch` command

### Fixed
- Fixed several decoding issues
- Several **PEP8** and **W1202** fixes

### Removed
- `DiffHelper` class is not needed


## [0.4.0] - 2014-12-05
### Added
- Handling of extra versions like `b1`, `rc1`, etc.
- Added build log analyzer to detect unpackaged files or other issues
- Added Bash completion

### Changed
- Improved version extraction from archive name
- **rebase-helper** output is looged to `rebase-helper-results` directory
- `SpecFile` class rewritten


## [0.3.1] - 2014-07-25
### Added
- New build class
- `--build-only` option
- Installation of build dependencies in case of **rpmbuild** tool
- More tests
- `RebaseHelperError` class for catching exceptions

### Fixed
- Several fixes


## [0.3.0]
### Added
- **pkgdiff** tool for comparing RPM packages
- Tests for `Archive` class and SPEC file


## [0.2.0]
### Added
- `diff_helper` for comparing two tarballs
- Applying patches to tarballs
- `patch_helper`


## [0.1.0]
### Added
- Initial classes
- CLI interface
