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

import os

import pytest  # type: ignore

from typing import List

from rebasehelper.cli import CLI
from rebasehelper.config import Config
from rebasehelper.application import Application
from rebasehelper import constants


class TestApplication:
    OLD_SOURCES: str = 'test-1.0.2.tar.xz'
    NEW_SOURCES: str = 'test-1.0.3.tar.xz'
    SPEC_FILE: str = 'test.spec'
    PATCH_1: str = 'test-testing.patch'
    PATCH_2: str = 'test-testing2.patch'
    PATCH_3: str = 'test-testing3.patch'
    SOURCE_1: str = 'file.txt.bz2'
    SOURCE_2: str = 'documentation.tar.xz'
    SOURCE_3: str = 'misc.zip'
    TEST_SOURCE: str = 'test-source.sh'
    SOURCE_TESTS: str = 'source-tests.sh'

    TEST_FILES: List[str] = [
        OLD_SOURCES,
        NEW_SOURCES,
        SPEC_FILE,
        PATCH_1,
        PATCH_2,
        PATCH_3,
        SOURCE_1,
        SOURCE_2,
        SOURCE_3,
        TEST_SOURCE,
        SOURCE_TESTS,
        'positional-1.1.0.tar.gz',
        'rebase-helper-d70cb5a2f523db5b6088427563531f43b7703859.tar.gz',
        'test-hardcoded-version-1.0.2.tar.gz',
        'test-hardcoded-version-1.0.3.tar.gz',
    ]

    cmd_line_args: List[str] = ['--not-download-sources', '1.0.3']

    def test_application_sources(self, workdir):
        expected_dict = {
            'new': {
                'sources': [os.path.join(workdir, self.TEST_SOURCE),
                            os.path.join(workdir, self.SOURCE_TESTS),
                            os.path.join(workdir, self.NEW_SOURCES)],
                'version': '1.0.3',
                'name': 'test',
                'tarball': self.NEW_SOURCES,
                'spec': os.path.join(workdir, constants.RESULTS_DIR, self.SPEC_FILE),
                'patches_full': {1: [os.path.join(workdir, self.PATCH_1),
                                     '',
                                     0,
                                     False],
                                 2: [os.path.join(workdir, self.PATCH_2),
                                     '-p1',
                                     1,
                                     False],
                                 3: [os.path.join(workdir, self.PATCH_3),
                                     '-p1',
                                     2,
                                     False]}},
            'workspace_dir': os.path.join(workdir, constants.WORKSPACE_DIR),
            'old': {
                'sources': [os.path.join(workdir, self.TEST_SOURCE),
                            os.path.join(workdir, self.SOURCE_TESTS),
                            os.path.join(workdir, self.OLD_SOURCES)],
                'version': '1.0.2',
                'name': 'test',
                'tarball': self.OLD_SOURCES,
                'spec': os.path.join(workdir, self.SPEC_FILE),
                'patches_full': {1: [os.path.join(workdir, self.PATCH_1),
                                     '',
                                     0,
                                     False],
                                 2: [os.path.join(workdir, self.PATCH_2),
                                     '-p1',
                                     1,
                                     False],
                                 3: [os.path.join(workdir, self.PATCH_3),
                                     '-p1',
                                     2,
                                     False]}},
            'results_dir': os.path.join(workdir, constants.RESULTS_DIR)}

        cli = CLI(self.cmd_line_args)
        config = Config()
        config.merge(cli)
        execution_dir, results_dir, debug_log_file = Application.setup(config)
        app = Application(config, execution_dir, results_dir, debug_log_file)
        app.prepare_sources()
        for key, val in app.kwargs.items():
            if key in expected_dict:
                assert val == expected_dict[key]

    @pytest.mark.parametrize('gitignore, sources, result', [
        (
                [
                    '/source1-*.tar.gz\n',
                    '/source2-2.8.0.tar.xz\n',
                    '/Source3.bz2\n',
                ],
                [
                    'source1-1.0.1.tar.gz',
                    'source2-2.8.1.tar.xz',
                    'Source3.bz2',
                ],
                [
                    '/source1-*.tar.gz\n',
                    '/source2-2.8.0.tar.xz\n',
                    '/Source3.bz2\n',
                    '/source2-2.8.1.tar.xz\n',
                ],
        ),
    ], ids=[
        'gitignore',
    ])
    def test_update_gitignore(self, workdir, gitignore, sources, result):
        with open(os.path.join(workdir, '.gitignore'), 'w') as f:
            for line in gitignore:
                f.write(line)
        Application._update_gitignore(sources, workdir)  # pylint: disable=protected-access
        with open(os.path.join(workdir, '.gitignore')) as f:
            assert f.readlines() == result
