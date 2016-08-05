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
import json

from .base_test import BaseTest
from rebasehelper.output_tool import OutputTool
from rebasehelper.settings import REBASE_HELPER_RESULTS_LOG
from rebasehelper.results_store import ResultsStore


class TestOutputTool(BaseTest):
    """
    Class is used for testing OutputTool
    """

    def setup(self):
        super(TestOutputTool, self).setup()

        data = {'old': {'patches_full': {0: ['mytest.patch', '-p1', 0],
                                         1: ['mytest2.patch', '-p1', 1]},
                        'srpm': './test-1.2.0-1.src.rpm',
                        'rpm': ['./test-1.2.0-1.x86_64.rpm', './test-devel-1.2.0-1.x86_64.rpm'],
                        'logs': ['logfile1.log', 'logfile2.log']
                        },
                'new': {'patches_full': {0: ['mytest.patch', 0, '-p1'],
                                         1: ['mytest2.patch', 1, '-p1']},
                        'srpm': './test-1.2.2-1.src.rpm',
                        'rpm': ['./test-1.2.2-1.x86_64.rpm', './test-devel-1.2.2-1.x86_64.rpm'],
                        'logs': ['logfile3.log', 'logfile4.log']},
                'patches': {'deleted': ['mytest2.patch']},
                'results_dir': self.WORKING_DIR,
                'moved': ['/usr/sbin/test', '/usr/sbin/test2'],
                }

        self.results_store = ResultsStore()
        self.results_store.set_build_data('old', data['old'])
        self.results_store.set_build_data('new', data['new'])
        self.results_store.set_patches_results(data['patches'])
        message = 'Following files were moved\n%s\n' % '\n'.join(data['moved'])
        test_output = {'pkgdiff': message}
        self.results_store.set_checker_output('Results from checker(s)', test_output)
        self.results_store.set_info_text('Information text', 'some information text')
        self.results_store.set_info_text('Next Information', 'some another information text')

    def get_expected_text_output(self):
        expected_output = """
Summary information about patches:
Patch mytest2.patch [deleted]

Old (S)RPM packages:
---------------------
SRPM package(s): are in directory . :
- test-1.2.0-1.src.rpm
RPM package(s): are in directory . :
- test-1.2.0-1.x86_64.rpm
- test-devel-1.2.0-1.x86_64.rpm
Available Old logs:
- logfile1.log
- logfile2.log

New (S)RPM packages:
---------------------
SRPM package(s): are in directory . :
- test-1.2.2-1.src.rpm
RPM package(s): are in directory . :
- test-1.2.2-1.x86_64.rpm
- test-devel-1.2.2-1.x86_64.rpm
Available New logs:
- logfile3.log
- logfile4.log
=== Checker Results from checker(s) results ===
Following files were moved
/usr/sbin/test
/usr/sbin/test2
See for more details pkgdiff"""
        return expected_output

    def get_expected_json_output(self):
        expected_output = {
            ResultsStore.RESULTS_BUILDS: {
                "new": {
                    "logs": ["logfile3.log", "logfile4.log"],
                    "patches_full": {
                        "0": ["mytest.patch", 0, "-p1"],
                        "1": ["mytest2.patch", 1, "-p1"]
                    },
                    "rpm": ["./test-1.2.2-1.x86_64.rpm", "./test-devel-1.2.2-1.x86_64.rpm"],
                    "srpm": "./test-1.2.2-1.src.rpm"
                },
                "old": {
                    "logs": ["logfile1.log", "logfile2.log"],
                    "patches_full": {
                        "0": ["mytest.patch", "-p1", 0],
                        "1": ["mytest2.patch", "-p1", 1]
                    },
                    "rpm": ["./test-1.2.0-1.x86_64.rpm", "./test-devel-1.2.0-1.x86_64.rpm"],
                    "srpm": "./test-1.2.0-1.src.rpm"
                }
            },
            ResultsStore.RESULTS_CHECKERS: {
                "Results from checker(s)": {
                    "pkgdiff": "Following files were moved\n/usr/sbin/test\n/usr/sbin/test2\n"
                }
            },
            ResultsStore.RESULTS_INFORMATION: {
                "Information text": "some information text",
                "Next Information": "some another information text"
            },
            ResultsStore.RESULTS_PATCHES: {
                "deleted": ["mytest2.patch"]
            }
        }
        return expected_output

    def test_text_output(self):
        output = OutputTool('text')

        logfile = os.path.join(self.TESTS_DIR, REBASE_HELPER_RESULTS_LOG)
        output.print_information(logfile, self.results_store)

        with open(logfile) as f:
            lines = [y.strip() for y in f.readlines()]
            assert lines == self.get_expected_text_output().split('\n')

        os.unlink(logfile)

    def test_json_output(self):
        output = OutputTool('json')

        logfile = os.path.join(self.TESTS_DIR, REBASE_HELPER_RESULTS_LOG)
        output.print_information(logfile, self.results_store)

        with open(logfile) as f:
            json_dict = json.loads(f.read(), encoding='utf-8')
            # in Python2 strings in json decoded dict are Unicode, which would make the test fail
            assert json_dict == json.loads(json.dumps(self.get_expected_json_output()))

        os.unlink(logfile)
