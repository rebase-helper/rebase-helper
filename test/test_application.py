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
import tarfile
import shutil
from rebasehelper.cli import CLI
from rebasehelper.application import Application
from rebasehelper import settings
from rebasehelper.specfile import SpecFile


class TestApplication(object):
    """ Application tests """
    TAR_GZ = "tar_gz"
    TAR_GZ2 = "tar_gz2"
    list_archives = [TAR_GZ, TAR_GZ2]
    list_names = {TAR_GZ: 'test-1.0.2.tar.gz',
                  TAR_GZ2: 'test-1.0.3.tar.gz',
                  }
    dir_name = os.path.join(os.path.dirname(__file__))
    spec_file = 'test.spec'
    rebased_spec = os.path.join(settings.REBASE_HELPER_RESULTS_DIR, spec_file)
    cmd_line_args = ['--not-download-sources', 'test-1.0.3.tar.gz']
    result_dir = ""
    workspace_dir = ""

    def setup(self):
        self.result_dir = os.path.join(self.dir_name, settings.REBASE_HELPER_RESULTS_DIR)
        self.workspace_dir = os.path.join(self.dir_name, settings.REBASE_HELPER_WORKSPACE_DIR)
        for tarball in self.list_archives:
            arch_name = os.path.join(self.dir_name, self.list_names[tarball])
            archive = tarfile.TarFile.open(arch_name, 'w:gz')
            for file_name in os.listdir(os.path.join(self.dir_name, tarball)):
                archive.add(os.path.join(self.dir_name, tarball, file_name), arcname=file_name)
            archive.close()

    def teardown(self):
        if os.path.exists(self.result_dir):
            shutil.rmtree(self.result_dir)
        if os.path.exists(self.workspace_dir):
            shutil.rmtree(self.workspace_dir)
        for tarball in self.list_archives:
            if os.path.exists(tarball):
                os.unlink(tarball)

    def test_old_information(self):
        expected_results = {
            'sources': ['/home/phracek/work/programming/rebase-helper/test/test-source.sh',
                        '/home/phracek/work/programming/rebase-helper/test/source-tests.sh',
                        '/home/phracek/work/programming/rebase-helper/test/test-1.0.2.tar.gz'],
            'version': '1.0.2',
            'name': 'test',
            'patches_full': {
                1: ['/home/phracek/work/programming/rebase-helper/test/test-testing.patch', ' ', 0, False],
                2: ['/home/phracek/work/programming/rebase-helper/test/test-testing2.patch', '-p1', 1, False],
                3: ['/home/phracek/work/programming/rebase-helper/test/test-testing3.patch', '-p1', 2, False]},
            'tarball': 'test-1.0.2.tar.gz'}
        cwd = os.getcwd()
        os.chdir(os.path.join(cwd, 'test'))
        os.makedirs(settings.REBASE_HELPER_RESULTS_DIR)
        spec = SpecFile(self.spec_file, new_sources=self.list_names[self.TAR_GZ2], download=False)
        result_dic = spec.get_old_information()
        shutil.rmtree(settings.REBASE_HELPER_RESULTS_DIR)
        os.chdir(cwd)
        assert expected_results == result_dic

    def test_new_information(self):
        expected_results = {
            'sources': ['/home/phracek/work/programming/rebase-helper/test/test-source.sh',
                        '/home/phracek/work/programming/rebase-helper/test/source-tests.sh',
                        '/home/phracek/work/programming/rebase-helper/test/test-1.0.2.tar.gz'],
            'version': '1.0.2',
            'name': 'test',
            'patches_full': {
                1: ['/home/phracek/work/programming/rebase-helper/test/test-testing.patch', ' ', 0, False],
                2: ['/home/phracek/work/programming/rebase-helper/test/test-testing2.patch', '-p1', 1, False],
                3: ['/home/phracek/work/programming/rebase-helper/test/test-testing3.patch', '-p1', 2, False]},
            'tarball': 'test-1.0.3.tar.gz'}
        cwd = os.getcwd()
        os.chdir(os.path.join(cwd, 'test'))
        os.makedirs(settings.REBASE_HELPER_RESULTS_DIR)
        spec = SpecFile(self.spec_file, new_sources=self.list_names[self.TAR_GZ2], download=False)
        result_dic = spec.get_new_information()
        shutil.rmtree(settings.REBASE_HELPER_RESULTS_DIR)
        os.chdir(cwd)
        assert expected_results == result_dic

    def test_application_sources(self):
        expected_dict = {
            'new': {
                'sources': ['/home/phracek/work/programming/rebase-helper/test/test-source.sh',
                             '/home/phracek/work/programming/rebase-helper/test/source-tests.sh',
                             '/home/phracek/work/programming/rebase-helper/test/test-1.0.3.tar.gz'],
                'version': '1.0.3',
                'name': 'test',
                'tarball': 'test-1.0.3.tar.gz',
                'spec': '/home/phracek/work/programming/rebase-helper/test/rebase-helper-results/test.spec',
                'patches_full': {1: ['/home/phracek/work/programming/rebase-helper/test/test-testing.patch',
                                     ' ',
                                     0,
                                     False],
                                 2: ['/home/phracek/work/programming/rebase-helper/test/test-testing2.patch',
                                     '-p1',
                                     1,
                                     False],
                                 3: ['/home/phracek/work/programming/rebase-helper/test/test-testing3.patch',
                                     '-p1',
                                     2,
                                     False]}},
            'workspace_dir': '/home/phracek/work/programming/rebase-helper/test/rebase-helper-workspace',
            'old': {
                'sources': ['/home/phracek/work/programming/rebase-helper/test/test-source.sh',
                            '/home/phracek/work/programming/rebase-helper/test/source-tests.sh',
                            '/home/phracek/work/programming/rebase-helper/test/test-1.0.2.tar.gz'],
                'version': '1.0.2',
                'name': 'test',
                'tarball': 'test-1.0.2.tar.gz',
                'spec': '/home/phracek/work/programming/rebase-helper/test/test.spec',
                'patches_full': {1: ['/home/phracek/work/programming/rebase-helper/test/test-testing.patch',
                                     ' ',
                                     0,
                                     False],
                                 2: ['/home/phracek/work/programming/rebase-helper/test/test-testing2.patch',
                                     '-p1',
                                     1,
                                     False],
                                 3: ['/home/phracek/work/programming/rebase-helper/test/test-testing3.patch',
                                     '-p1',
                                     2,
                                     False]}},
            'results_dir': '/home/phracek/work/programming/rebase-helper/test/rebase-helper-results'}

        cwd = os.getcwd()
        os.chdir(os.path.join(cwd, 'test'))
        try:
            cli = CLI(self.cmd_line_args)
            app = Application(cli)
            sources = app.prepare_sources()
            assert app.kwargs == expected_dict
        except OSError as oer:
            os.chdir(cwd)
        os.chdir(cwd)



