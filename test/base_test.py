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
import shutil
import tempfile


class BaseTest(object):
    """
    Base class for tests. Will setup temporary environment in tmp for each test and destroy
    it aster test is finished.
    """

    WORKING_DIR = ''
    #  TODO: Maybe we should move these two to a settings file for tests??
    TESTS_DIR = os.path.join(os.getcwd(), 'test')
    TEST_FILES_DIR = os.path.join(TESTS_DIR, 'testing_files')

    TEST_FILES = []

    def setup(self):
        """
        Setup the temporary environment and change the working directory to it.
        """
        self.WORKING_DIR = tempfile.mkdtemp(prefix="rebase-helper-test-")
        os.chdir(self.WORKING_DIR)
        # copy files into the testing environment directory
        for file_name in self.TEST_FILES:
            shutil.copy(os.path.join(self.TEST_FILES_DIR, file_name), os.getcwd())

    def teardown(self):
        """
        Destroy the temporary environment.
        :return:
        """
        os.chdir(self.TESTS_DIR)
        shutil.rmtree(self.WORKING_DIR)