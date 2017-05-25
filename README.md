# Welcome to rebase-helper

[![Code Health](https://landscape.io/github/phracek/rebase-helper/master/landscape.svg?style=flat)](https://landscape.io/github/phracek/rebase-helper/master) [![GitLab CI build status](https://gitlab.com/rebase-helper/rebase-helper/badges/master/build.svg)](https://gitlab.com/rebase-helper/rebase-helper/commits/master) [![Travis CI build status](https://travis-ci.org/rebase-helper/rebase-helper.svg?branch=master)](https://travis-ci.org/rebase-helper/rebase-helper) [![Documentation build status](https://readthedocs.org/projects/rebase-helper/badge/?version=latest)](https://readthedocs.org/projects/rebase-helper)

There are several steps that need to be done when rebasing a package. The goal of **rebase-helper** is to automate most of these steps.


## General workflow
- *rebase-helper-workspace* and *rebase-helper-results* directories are created
- original SPEC file is copied to *rebase-helper-results* directory and its Version tag is modified
- old and new source tarballs are downloaded and extracted to *rebase-helper-workspace* directory
- downstream patches are rebased on top of new sources using `git-rebase`, resulting modified patches are saved to *rebase-helper-results* directory
- old and new source RPMs are created and built with selected build tool
- multiple checker tools are run against both sets of packages and their output is stored in *rebase-helper-results* directory
- *rebase-helper-workspace* directory is removed


## Patch rebasing workflow
- new git repository is initialized and the old sources are extracted and commited
- each downstream patch is applied and changes introduced by it are commited
- new sources are extracted and added as a remote repository
- `git-rebase` is used to rebase the commits on top of new sources
- original patches are modified/deleted accordingly
- changes are reflected in the spec file


## How to run rebase-helper

Execute **rebase-helper** from a directory containing SPEC file, sources and patches (usually cloned dist-git repository).

There are two ways how to specify the new version. You can pass it to **rebase-helper** directly, e.g.:

`rebase-helper 3.1.10`

or you can let *rebase-helper* determine it from the new version tarball, e.g.:

`rebase-helper foo-4.2.tar.gz`

For complete CLI reference see [usage](https://rebase-helper.readthedocs.io/en/latest/user_guide/usage.html).
