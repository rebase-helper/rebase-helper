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

from .base_test import BaseTest
from rebasehelper.cli import CLI
from rebasehelper.application import Application
from rebasehelper import settings


class TestApplication(BaseTest):
    """ Application tests """

    OLD_SOURCES = 'test-1.0.2.tar.xz'
    NEW_SOURCES = 'test-1.0.3.tar.xz'
    SPEC_FILE = 'test.spec'
    PATCH_1 = 'test-testing.patch'
    PATCH_2 = 'test-testing2.patch'
    PATCH_3 = 'test-testing3.patch'
    SOURCE_1 = 'file.txt.bz2'
    SOURCE_2 = 'documentation.tar.xz'
    SOURCE_3 = 'misc.zip'

    TEST_FILES = [
        OLD_SOURCES,
        NEW_SOURCES,
        SPEC_FILE,
        PATCH_1,
        PATCH_2,
        PATCH_3,
        SOURCE_1,
        SOURCE_2,
        SOURCE_3
    ]

    cmd_line_args = ['--not-download-sources', '1.0.3']

    def test_application_sources(self):
        expected_dict = {
            'new': {
                'sources': [os.path.join(self.WORKING_DIR, 'test-source.sh'),
                            os.path.join(self.WORKING_DIR, 'source-tests.sh'),
                            os.path.join(self.WORKING_DIR, self.NEW_SOURCES)],
                'version': '1.0.3',
                'name': 'test',
                'tarball': self.NEW_SOURCES,
                'spec': os.path.join(self.WORKING_DIR, settings.REBASE_HELPER_RESULTS_DIR, self.SPEC_FILE),
                'patches_full': {1: [os.path.join(self.WORKING_DIR, self.PATCH_1),
                                     '',
                                     0,
                                     False],
                                 2: [os.path.join(self.WORKING_DIR, self.PATCH_2),
                                     '-p1',
                                     1,
                                     False],
                                 3: [os.path.join(self.WORKING_DIR, self.PATCH_3),
                                     '-p1',
                                     2,
                                     False]}},
            'workspace_dir': os.path.join(self.WORKING_DIR, settings.REBASE_HELPER_WORKSPACE_DIR),
            'old': {
                'sources': [os.path.join(self.WORKING_DIR, 'test-source.sh'),
                            os.path.join(self.WORKING_DIR, 'source-tests.sh'),
                            os.path.join(self.WORKING_DIR, self.OLD_SOURCES)],
                'version': '1.0.2',
                'name': 'test',
                'tarball': self.OLD_SOURCES,
                'spec': os.path.join(self.WORKING_DIR, self.SPEC_FILE),
                'patches_full': {1: [os.path.join(self.WORKING_DIR, self.PATCH_1),
                                     '',
                                     0,
                                     False],
                                 2: [os.path.join(self.WORKING_DIR, self.PATCH_2),
                                     '-p1',
                                     1,
                                     False],
                                 3: [os.path.join(self.WORKING_DIR, self.PATCH_3),
                                     '-p1',
                                     2,
                                     False]}},
            'results_dir': os.path.join(self.WORKING_DIR, settings.REBASE_HELPER_RESULTS_DIR)}

        try:
            cli = CLI(self.cmd_line_args)
            execution_dir, results_dir, debug_log_file, report_log_file = Application.setup(cli)
            app = Application(cli, execution_dir, results_dir, debug_log_file, report_log_file)
            app.prepare_sources()
            for key, val in app.kwargs.items():
                if key in expected_dict:
                    assert val == expected_dict[key]
        except OSError as oer:
            pass



