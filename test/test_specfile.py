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

from base_test import BaseTest
from rebasehelper.specfile import SpecFile


class TestSpecFile(BaseTest):
    """ SpecFile tests """
    NAME = 'test'
    VERSION = '1.0.2'
    OLD_ARCHIVE = NAME + '-' + VERSION + '.tar.xz'
    SPEC_FILE = 'test.spec'
    SOURCE_0 = 'test-source.sh'
    SOURCE_1 = 'source-tests.sh'
    PATCH_1 = 'test-testing.patch'
    PATCH_2 = 'test-testing2.patch'
    PATCH_3 = 'test-testing3.patch'

    TEST_FILES = [
        SPEC_FILE,
        PATCH_1,
        PATCH_2,
        PATCH_3
    ]

    def setup(self):
        super(TestSpecFile, self).setup()
        self.SPEC_FILE_OBJECT = SpecFile(self.SPEC_FILE, download=False)

    def test_get_version(self):
        assert self.SPEC_FILE_OBJECT.get_version() == self.VERSION

    def test_set_version(self):
        NEW_VERSION = '1.2.3.4.5'
        self.SPEC_FILE_OBJECT.set_version(NEW_VERSION)
        self.SPEC_FILE_OBJECT.save()
        assert self.SPEC_FILE_OBJECT.get_version() == NEW_VERSION

    def test_get_package_name(self):
        assert self.SPEC_FILE_OBJECT.get_package_name() == self.NAME

    def test__write_spec_file_to_disc(self):
        new_content = [
            'testing line 1\n',
            'testing line 2\n'
        ]
        self.SPEC_FILE_OBJECT.spec_content = new_content
        self.SPEC_FILE_OBJECT._write_spec_file_to_disc()
        with open(self.SPEC_FILE) as spec:
            assert new_content == spec.readlines()

    def test__update_filtered_spec_content(self):
        new_content_1 = [
            'testing line 1\n',
            '#testing line 2\n'
        ]
        expected_content_1 = ['testing line 1\n']
        self.SPEC_FILE_OBJECT.spec_content = new_content_1
        self.SPEC_FILE_OBJECT._update_filtered_spec_content()
        assert self.SPEC_FILE_OBJECT.spec_filtered_content == expected_content_1

    def test_old_tarball(self):
        assert self.SPEC_FILE_OBJECT.get_archive() == self.OLD_ARCHIVE

    def test_all_sources(self):
        sources = [self.SOURCE_0, self.SOURCE_1, self.OLD_ARCHIVE]
        sources = [os.path.join(self.WORKING_DIR, f) for f in sources]
        assert len(set(sources).intersection(set(self.SPEC_FILE_OBJECT.get_sources()))) == 3

    def test_get_patches(self):
        expected_patches = {1: [os.path.join(self.WORKING_DIR, self.PATCH_1), '', 0, False],
                            2: [os.path.join(self.WORKING_DIR, self.PATCH_2), '-p1', 1, False],
                            3: [os.path.join(self.WORKING_DIR, self.PATCH_3), '-p1', 2, False]}
        assert self.SPEC_FILE_OBJECT.get_patches() == expected_patches

    def test_get_requires(self):
        expected = set(['openssl-devel', 'pkgconfig', 'texinfo', 'gettext', 'autoconf'])
        req = self.SPEC_FILE_OBJECT.get_requires()
        assert len(expected.intersection(req)) == 5
