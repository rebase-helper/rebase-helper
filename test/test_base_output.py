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

import six
from rebasehelper.base_output import OutputLogger


class TestBaseOutput(object):
    """
    Class is used for testing OutputTool
    """
    old_rpm_data = {'rpm': ['rpm-0.1.0.x86_64.rpm', ' rpm-devel-0.1.0.x86_64.rpm'],
                'srpm': 'rpm-0.1.0.src.rpm',
                'logs': ['logfile1.log', 'logfile2.log']}
    new_rpm_data = {'rpm': ['rpm-0.2.0.x86_64.rpm', ' rpm-devel-0.2.0.x86_64.rpm'],
                'srpm': 'rpm-0.2.0.src.rpm',
                'logs': ['logfile3.log', 'logfile4.log']}
    patches_data = {'deleted': ['del_patch1.patch', 'del_patch2.patch'],
                    'modified': ['mod_patch1.patch', 'mod_patch2.patch']}
    info_data = {'Information text': 'some information text'}
    info_data2 = {'Next Information': 'some another information text'}

    def setup(self):
        OutputLogger.set_info_text('Information text', 'some information text')
        OutputLogger.set_info_text('Next Information', 'some another information text')
        OutputLogger.set_patch_output('Patches:', self.patches_data)
        OutputLogger.set_build_data('old', self.old_rpm_data)
        OutputLogger.set_build_data('new', self.new_rpm_data)

    def test_base_output_global(self):
        expect_dict = self.info_data
        expect_dict.update(self.info_data2)
        build_dict = {'old': self.old_rpm_data,
                      'new': self.new_rpm_data}
        expected_result = {'build': build_dict,
                           'patch': self.patches_data,
                           'information': expect_dict}
        for key, value in six.iteritems(expected_result):
            assert value == expected_result[key]

    def test_base_output_info(self):
        """
        Test Output logger info

        :return:
        """
        info_results = OutputLogger.get_summary_info()
        expect_dict = self.info_data
        expect_dict.update(self.info_data2)
        assert info_results == expect_dict

    def test_base_output_patches(self):
        """
        Test Output logger patches

        :return:
        """
        patch_results = OutputLogger.get_patches()
        expected_patches = self.patches_data
        assert patch_results == expected_patches

    def test_base_output_builds_old(self):
        """
        Test Output logger old builds

        :return:
        """
        build_results = OutputLogger.get_build('old')
        assert build_results == self.old_rpm_data

    def test_base_output_builds_new(self):
        """
        Test Output logger new builds

        :return:
        """
        build_results = OutputLogger.get_build('new')
        assert build_results == self.new_rpm_data
