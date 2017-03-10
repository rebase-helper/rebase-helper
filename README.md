# rebase-helper

[![Code Health](https://landscape.io/github/phracek/rebase-helper/master/landscape.svg?style=flat)](https://landscape.io/github/phracek/rebase-helper/master) [![GitLab CI build status](https://gitlab.com/rebase-helper/rebase-helper/badges/master/build.svg)](https://gitlab.com/rebase-helper/rebase-helper/commits/master) [![Travis CI build status](https://travis-ci.org/rebase-helper/rebase-helper.svg?branch=master)](https://travis-ci.org/rebase-helper/rebase-helper)

This tool helps you to rebase your package to the latest version.

## Landscape scans

[**Landscape.io scans of rebase-helper**](https://landscape.io/github/phracek/rebase-helper/)

## General workflow
- *rebase-helper-results* and *rebase-helper-workspace* directories are created
- original spec file is copied to *rebase-helper-results* directory
  and its Version tag is modified
- old and new sources are downloaded (if needed) and extracted
  to *rebase-helper-workspace* directory
- patches are rebased using git, modified patches (if any) are saved
  to *rebase-helper-results* directory
- old and new source RPMs are created
- the source RPMs are rebuilt with selected build tool
- rpmdiff, pkgdiff and abipkgdiff are run against both sets of packages
  and their output is stored in *rebase-helper-results* directory
- *rebase-helper-workspace* directory is removed

## Patch rebasing workflow
- new git repository is initialized and the old sources are extracted
  and commited to it
- every patch is applied and the changes introduced by it are commited
- new sources are extracted and added as a remote branch to the repository
- git rebase is used to rebase the commits on top of the new sources
- original patches are modified/deleted accordingly
- changes are reflected in the spec file

## Requirements

Packages which need to be installed before you execute *rebase-helper*
for the first time:

- git
- rpm-build
- mock
- fedpkg
- rpmlint
- pkgdiff
- libabigail

Python dependencies are listed in *requirements.txt* and can be installed with pip:

`pip install -r requirements.txt`

## How to execute rebase-helper from CLI

Execute *rebase-helper* from a directory containing spec file, sources and patches
(usually cloned dist-git repository).

There are two ways how to specify the new version. You can pass it
to *rebase-helper* directly, e.g.:

`rebase-helper 3.1.10`

or you can let *rebase-helper* determine it from the new version tarball, e.g.:

`rebase-helper joe-4.2.tar.gz`


## How to use rebase-helper in Docker

Build docker image with command
 
`docker build --build-arg=RH_VERSION=<your_version> --build-arg=RH_PACKAGE=<your_package_name> -t rebasehelper:0.2 . `

Run docker image with command

`docker run -ti -e RH_PACKAGE=<your_package_name> -e RH_VERSION=<new_version> -v /home/phracek/work/programming/docker-rebase-helper/docker_export:/package_name rebasehelper:0.2`

The rebase-helper results should be in directory *./docker_export*.
