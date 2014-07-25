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
from rebasehelper import specfile
from rebasehelper import settings
from rebasehelper.logger import logger


class TestSpecHelper(object):
    """ SpecHelper tests """
    dir_name = ""
    spec_file = None
    test_spec = 'test.spec'
    result_dir = ""
    workspace_dir = ""

    def setup(self):
        self.dir_name = os.path.dirname(__file__)
        self.result_dir = os.path.join(self.dir_name, settings.REBASE_HELPER_RESULTS_DIR)
        self.workspace_dir = os.path.join(self.dir_name, settings.REBASE_HELPER_WORKSPACE_DIR)
        if os.path.exists(self.result_dir):
            shutil.rmtree(self.result_dir)
        os.makedirs(self.result_dir)
        file_name = os.path.join(self.dir_name, self.test_spec)
        self.spec_file = specfile.SpecFile(file_name, '', download=False)
        self.spec_file.get_old_information()

    def teardown(self):
        if os.path.exists(self.result_dir):
            shutil.rmtree(self.result_dir)
        if os.path.exists(self.workspace_dir):
            shutil.rmtree(self.workspace_dir)

    def test_spec_file(self):
        spec_path = os.path.join(self.dir_name,
                                 settings.REBASE_HELPER_RESULTS_DIR,
                                 self.test_spec)
        assert os.path.exists(spec_path)

    def test_old_tarball(self):
        expected_tarball = 'test-1.0.2.tar.gz'
        test_tarball = self.spec_file._get_old_tarball()
        assert test_tarball == expected_tarball

    def test_all_sources(self):
        sources = ['test-source.sh', 'source-tests.sh', 'test-1.0.2.tar.gz']
        expected_sources = [os.path.join(os.getcwd(), x) for x in sources]
        test_sources = self.spec_file._get_all_sources()
        logger.info(test_sources)
        assert expected_sources == test_sources

    def test_list_patches(self):
        cwd = os.getcwd()
        dir_name = os.path.join(cwd, self.dir_name)
        expected_patches = {1: [os.path.join(dir_name, 'test-testing.patch'), ' ', 0, False],
                            2: [os.path.join(dir_name, 'test-testing2.patch'), '-p1', 1, False],
                            3: [os.path.join(dir_name, 'test-testing3.patch'), '-p1', 2, False],}
        os.chdir(os.path.dirname(__file__))
        test_patches = self.spec_file._get_patches()
        os.chdir(cwd)
        assert expected_patches == test_patches

    def test_get_requires(self):
        expected = set(['openssl-devel', 'pkgconfig', 'texinfo', 'gettext', 'autoconf'])
        req = self.spec_file.get_requires()
        assert len(expected.intersection(req)) == 5
