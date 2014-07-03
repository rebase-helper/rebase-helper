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

import os
import shutil
import logging

from logging import FileHandler
from rebasehelper import output_tool
from rebasehelper.logger import logger
from rebasehelper.utils import get_content_file


class TestOutputTool(object):
    """
    Class is used for testing OutputTool
    """
    data = {'old': {'patches_full': {0: ['mytest.patch', '-p1', 0],
                                     1: ['mytest2.patch', '-p1', 1]},
                    'srpm': 'test-1.2.0-1.src.rpm',
                    'rpm': ['test-1.2.0-1.rpm', 'test-devel-1.2.0-1.rpm']
                    },
            'new': {'patches_full': {0: ['mytest.patch', 0, '-p1'],
                                     1: ['mytest2.patch', 1, '-p1']},
                    'srpm': 'test-1.2.2-1.src.rpm',
                    'rpm': ['test-1.2.2-1.rpm', 'test-devel-1.2.2-1.rpm']},
            'summary_info': {'deleted': ['mytest2.patch']}
            }
    output_log = os.path.join(os.path.dirname(__file__), 'output.log')

    def setup(self):
        logger.addHandler(FileHandler(self.output_log, mode='w'))
        logger.setLevel(logging.INFO)

    def teardown(self):
        if os.path.exists(self.output_log):
            shutil.rmtree(self.output_log)

    def test_text_output(self):
        expected_output = """Summary information:
====================
Patches:
Patch1   mytest2.patch   [deleted]
Old (S)RPM packages:
--------------------
SRPM package(s):
- test-1.2.0-1.src.rpm
RPM package(s):
- test-1.2.0-1.rpm
- test-devel-1.2.0-1.rpm
New (S)RPM packages:
--------------------
SRPM package(s):
- test-1.2.2-1.src.rpm
RPM package(s):
- test-1.2.2-1.rpm
- test-devel-1.2.2-1.rpm
Results from pkgcompare check could not be found."""
        output = output_tool.OutputTool('text')
        output.print_information(**self.data)
        real_output = get_content_file(self.output_log, 'r')
        if os.path.exists(self.output_log):
            os.unlink(self.output_log)
        assert real_output.strip() == expected_output
