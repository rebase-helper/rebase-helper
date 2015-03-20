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

import shutil
from .base_test import BaseTest
from rebasehelper.build_log_analyzer import BuildLogAnalyzer, BuildLogAnalyzerMakeError
from rebasehelper.build_log_analyzer import BuildLogAnalyzerPatchError


class TestBuildLogAnalyzer(BaseTest):

    BUILD_FAILED_BUILDING = "build-failed-building.log"
    BUILD_FAILED_PATCH = "build-failed-patch.log"
    BUILD_MISSING = "build_missing.log"
    BUILD_OBSOLETES = "build_obsoletes.log"
    TEST_FILES = [
        BUILD_FAILED_BUILDING,
        BUILD_FAILED_PATCH,
        BUILD_MISSING,
        BUILD_OBSOLETES
    ]
    BUILD_LOG = "build.log"

    def _prepare_files(self, log):
        ba = BuildLogAnalyzer()
        shutil.copy(log, self.BUILD_LOG)
        return ba

    def test_failed_build(self):
        ba = self._prepare_files(self.BUILD_FAILED_BUILDING)
        catch_failed = False
        try:
            ba.parse_log(self.WORKING_DIR, self.BUILD_LOG)
        except BuildLogAnalyzerMakeError:
            catch_failed = True
        assert catch_failed is True

    def test_failed_patching(self):
        ba = self._prepare_files(self.BUILD_FAILED_PATCH)
        catch_failed = False
        try:
            ba.parse_log(self.WORKING_DIR, self.BUILD_LOG)
        except BuildLogAnalyzerPatchError:
            catch_failed = True
        assert catch_failed is True
