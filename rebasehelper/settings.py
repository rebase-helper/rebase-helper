# -*- coding: utf-8 -*-
#
# This tool helps you to rebase package to the latest version
# Copyright (C) 2013-2014 Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# he Free Software Foundation; either version 2 of the License, or
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
# Authors: Petr Hracek <phracek@redhat.com>
#          Tomas Hozza <thozza@redhat.com>

import os

REBASE_HELPER_SUFFIX = "-rebase"
REBASE_HELPER_PREFIX = "rebase-helper-"
REBASE_HELPER_LOGS = "logs"

REBASE_HELPER_RESULTS_DIR = REBASE_HELPER_PREFIX + "results"
REBASE_HELPER_WORKSPACE_DIR = REBASE_HELPER_PREFIX + "workspace"
REBASE_HELPER_LOGS_DIR = os.path.join(REBASE_HELPER_RESULTS_DIR, REBASE_HELPER_LOGS)

OLD_SOURCES = 'old_sources'
NEW_SOURCES = 'new_sources'
OLD_SOURCES_DIR = os.path.join(REBASE_HELPER_WORKSPACE_DIR, OLD_SOURCES)
NEW_SOURCES_DIR = os.path.join(REBASE_HELPER_WORKSPACE_DIR, NEW_SOURCES)

# The variable for access to full information about patches
FULL_PATCHES = 'patches_full'

GIT_CONFIG = '.gitconfig'
REBASE_HELPER_DEBUG_LOG = REBASE_HELPER_PREFIX + 'debug.log'
REBASE_HELPER_RESULTS_LOG = REBASE_HELPER_PREFIX + 'results.log'
REBASE_HELPER_REPORT_LOG = REBASE_HELPER_PREFIX + 'report.log'

BEGIN_COMMENT = '#BEGIN THIS MODIFIED BY REBASE-HELPER'
END_COMMENT = '#END THIS MODIFIED BY REBASE-HELPER'

CHECKER_TAGS = ['added', 'removed', 'changed', 'moved', 'renamed']

ABIDIFF_ERROR = 1
ABIDIFF_USAGE_ERROR = 2

REBASE_HELPER_OUTPUT_SUFFIX = ".txt"
