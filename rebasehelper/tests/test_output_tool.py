# -*- coding: utf-8 -*-
#
# This tool helps you to rebase package to the latest version
# Copyright (C) 2013-2014 Red Hat, Inc.
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
# Authors: Petr Hracek <phracek@redhat.com>
#          Tomas Hozza <thozza@redhat.com>

import os
import json

import pytest

from rebasehelper.output_tool import output_tools_runner
from rebasehelper.output_tools.json_output_tool import JSONOutputTool
from rebasehelper.output_tools.text_output_tool import TextOutputTool
from rebasehelper.results_store import ResultsStore


class TestOutputTool(object):
    @pytest.fixture
    def results_file_path(self, workdir):
        return os.path.join(workdir, 'output_file')

    @pytest.fixture
    def results_store(self, workdir):
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
                'results_dir': workdir,
                'moved': ['/usr/sbin/test', '/usr/sbin/test2'],
                'success': 'Success',
                }

        rs = ResultsStore()
        rs.set_build_data('old', data['old'])
        rs.set_build_data('new', data['new'])
        rs.set_patches_results(data['patches'])
        message = 'Following files were moved\n%s\n' % '\n'.join(data['moved'])
        test_output = {'pkgdiff': message}
        rs.set_checker_output('Results from checker(s)', test_output)
        rs.set_info_text('Information text', 'some information text')
        rs.set_info_text('Next Information', 'some another information text')
        rs.set_result_message('success', data['success'])

        return rs

    def get_expected_text_output(self, workdir):
        expected_output = """\
Success
All result files are stored in {workdir}

Downstream Patches
==================
Rebased patches are located in rebase-helper-results/rebased-sources
Legend:
[-] = already applied, patch removed
[*] = merged, patch modified
[!] = conflicting or inapplicable, patch skipped
[ ] = patch untouched
* mytest2.patch                            [-]

RPMS
====

Old packages
------------

Source packages and logs are in directory rebase-helper-results/old-build/SRPM:
- test-1.2.0-1.src.rpm
- logfile1.log
- logfile2.log

Binary packages and logs are in directory rebase-helper-results/old-build/RPM:
- test-1.2.0-1.x86_64.rpm
- test-devel-1.2.0-1.x86_64.rpm
- logfile1.log
- logfile2.log

New packages
------------

Source packages and logs are in directory rebase-helper-results/new-build/SRPM:
- test-1.2.2-1.src.rpm
- logfile3.log
- logfile4.log

Binary packages and logs are in directory rebase-helper-results/new-build/RPM:
- test-1.2.2-1.x86_64.rpm
- test-devel-1.2.2-1.x86_64.rpm
- logfile3.log
- logfile4.log""".format(workdir=workdir)
        return expected_output

    @staticmethod
    def get_expected_json_output():
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
            },
            ResultsStore.RESULTS_SUCCESS: {
                "success": "Success"
            }
        }
        return expected_output

    def test_text_output_tool(self, results_file_path, results_store):
        assert TextOutputTool.get_name() in output_tools_runner.output_tools
        TextOutputTool.print_summary(results_file_path, results_store)

        with open(results_file_path) as f:
            lines = [y.strip() for y in f.readlines()]
            assert lines == self.get_expected_text_output(os.path.dirname(results_file_path)).split('\n')

    def test_json_output_tool(self, results_file_path, results_store):
        assert JSONOutputTool.get_name() in output_tools_runner.output_tools
        JSONOutputTool.print_summary(results_file_path, results_store)

        with open(results_file_path) as f:
            json_dict = json.load(f, encoding='utf-8')
            # in Python2 strings in json decoded dict are Unicode, which would make the test fail
            assert json_dict == json.loads(json.dumps(self.get_expected_json_output()))
