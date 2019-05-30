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

from typing import List

from rebasehelper.plugins.plugin_manager import plugin_manager
from rebasehelper.tests.conftest import TEST_FILES_DIR


class TestPkgDiff:
    FILE_XML: str = "files.xml"
    PKGDIFF_HTML: str = "pkgdiff_reports.html"
    TEST_FILES: List[str] = [
        FILE_XML,
        PKGDIFF_HTML
    ]

    def get_data(self):
        data = {'moved': ['/usr/src/debug/iproute2-3.12.0/test/mytest.c',
                          '/usr/src/debug/iproute2-3.12.0/test/mytest2.c'],
                'changed': ['/usr/include/test.h']}
        return data

    def test_fill_dictionary(self):
        expected_dict = {'added': ['/usr/sbin/test',
                                   '/usr/sbin/pkg-*/binary_test',
                                   '/usr/lib64/libtest.so',
                                   '/usr/lib64/libtest.so.1'],
                         'removed': ['/usr/sbin/my_test',
                                     '/usr/sbin/pkg-*/binary_test',
                                     '/usr/lib64/libtest2.so',
                                     '/usr/lib64/libtest2.so.1'],
                         'changed': ['/usr/share/test.man'],
                         'moved': ['/usr/local/test.sh',
                                   '/usr/sbin/pkg-*/binary_test;/usr/sbin/pkg-*/binary_test (1%)'],
                         'renamed': ['/usr/lib/libtest3.so.3',
                                     '/usr/lib/libtest3.so']}
        plugin_manager.checkers.plugins['pkgdiff'].results_dir = TEST_FILES_DIR
        plugin_manager.checkers.plugins['pkgdiff'].fill_dictionary(TEST_FILES_DIR, old_version='1.0.1',
                                                                   new_version='1.0.2')
        assert plugin_manager.checkers.plugins['pkgdiff'].results_dict == expected_dict

    def test_process_xml(self):
        expected_dict = {'added': ['/usr/sbin/test',
                                   '/usr/lib64/libtest.so',
                                   '/usr/lib64/libtest.so.1'],
                         'changed': ['/usr/share/test.man'],
                         'moved': ['/usr/local/test.sh',
                                   '/usr/sbin/pkg-*/binary_test;/usr/sbin/pkg-*/binary_test (1%)'],
                         'removed': ['/usr/sbin/my_test',
                                     '/usr/lib64/libtest2.so',
                                     '/usr/lib64/libtest2.so.1'],
                         'renamed': ['/usr/lib/libtest3.so.3',
                                     '/usr/lib/libtest3.so']}
        plugin_manager.checkers.plugins['pkgdiff'].results_dir = TEST_FILES_DIR
        res_dict = plugin_manager.checkers.plugins['pkgdiff'].process_xml_results(TEST_FILES_DIR, old_version='1.0.1',
                                                                                  new_version='1.0.2')
        assert res_dict == expected_dict
