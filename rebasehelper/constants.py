# -*- coding: utf-8 -*-
#
# This tool helps you rebase your package to the latest version
# Copyright (C) 2013-2019 Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Authors: Petr Hráček <phracek@redhat.com>
#          Tomáš Hozza <thozza@redhat.com>
#          Nikola Forró <nforro@redhat.com>
#          František Nečas <fifinecas@seznam.cz>

import locale
import re


PROGRAM_DESCRIPTION = 'Tool to help package maintainers rebase their packages to the latest upstream version'
NEW_ISSUE_LINK = 'https://github.com/rebase-helper/rebase-helper/issues/new'

RESULTS_DIR = 'rebase-helper-results'
WORKSPACE_DIR = 'rebase-helper-workspace'

REBASED_SOURCES_DIR = 'rebased-sources'
OLD_BUILD_DIR = 'old-build'
NEW_BUILD_DIR = 'new-build'
CHECKERS_DIR = 'checkers'

LOGS_DIR = 'logs'
DEBUG_LOG = 'debug.log'
TRACEBACK_LOG = 'traceback.log'
VERBOSE_LOG = 'verbose.log'
INFO_LOG = 'info.log'
REPORT = 'report'

OLD_SOURCES_DIR = 'old_sources'
NEW_SOURCES_DIR = 'new_sources'

GIT_CONFIG = '.gitconfig'

CONFIG_PATH = '$XDG_CONFIG_HOME'
CONFIG_FILENAME = 'rebase-helper.cfg'

PACKAGE_CATEGORIES = {
    'python': re.compile(r'^python[23]?-'),
    'perl': re.compile(r'^perl-'),
    'ruby': re.compile(r'^rubygem-'),
    'nodejs': re.compile(r'^nodejs-'),
    'php': re.compile(r'^php-'),
    'haskell': re.compile(r'^ghc-'),
    'R': re.compile(r'^R-'),
}

DEFENC = locale.getpreferredencoding()
DEFENC = 'utf-8' if DEFENC == 'ascii' else DEFENC
