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


PROGRAM_DESCRIPTION: str = 'Tool to help package maintainers rebase their packages to the latest upstream version'
NEW_ISSUE_LINK: str = 'https://github.com/rebase-helper/rebase-helper/issues/new'

RESULTS_DIR: str = 'rebase-helper-results'
WORKSPACE_DIR: str = 'rebase-helper-workspace'

REBASED_SOURCES_DIR: str = 'rebased-sources'
OLD_BUILD_DIR: str = 'old-build'
NEW_BUILD_DIR: str = 'new-build'
CHECKERS_DIR: str = 'checkers'

LOGS_DIR: str = 'logs'
DEBUG_LOG: str = 'debug.log'
TRACEBACK_LOG: str = 'traceback.log'
VERBOSE_LOG: str = 'verbose.log'
INFO_LOG: str = 'info.log'
REPORT: str = 'report'

OLD_SOURCES_DIR: str = 'old_sources'
NEW_SOURCES_DIR: str = 'new_sources'

GIT_CONFIG: str = '.gitconfig'

CONFIG_PATH: str = '$XDG_CONFIG_HOME'
CONFIG_FILENAME: str = 'rebase-helper.cfg'

SYSTEM_ENCODING: str = locale.getpreferredencoding()
