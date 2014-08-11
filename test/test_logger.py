# -*- coding: utf-8 -*-

# This tool helps you to rebase package to the latest version
# Copyright (C) 2013 Petr Hracek
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

import tempfile
import os
import shutil
from rebasehelper.logger import LoggerHelper


class TestLoggerHelper(object):
    """ RebaseHelperLogger class tests. """

    def setup(self):
        self.WORKING_DIR = tempfile.mkdtemp(prefix="rebase-helper-test-")
        os.chdir(self.WORKING_DIR)

    def teardown(self):
        os.chdir(tempfile.gettempdir())
        shutil.rmtree(self.WORKING_DIR)
        self.WORKING_DIR = tempfile.gettempdir()

    def test_get_basic_logger(self):
        #  TODO: Add the test
        assert False

    def test_add_stream_handler(self):
        #  TODO: Add the test
        assert False

    def test_add_file_handler(self):
        #  TODO: Add the test
        assert False

