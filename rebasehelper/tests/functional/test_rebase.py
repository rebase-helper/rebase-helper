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

import json
import os

import git
import pytest
import unidiff

from rebasehelper.cli import CLI
from rebasehelper.config import Config
from rebasehelper.application import Application
from rebasehelper.constants import RESULTS_DIR
from rebasehelper.helpers.git_helper import GitHelper


class TestRebase(object):

    TEST_FILES = [
        'rebase/test.spec',
        'rebase/applicable.patch',
        'rebase/conflicting.patch',
        'rebase/backported.patch',
    ]

    NEW_VERSION = '0.2'

    @pytest.fixture
    def initialized_git_repo(self, workdir):
        repo = git.Repo.init(workdir)
        # Configure user otherwise app.apply_changes() will fail
        repo.git.config('user.name', GitHelper.get_user(), local=True)
        repo.git.config('user.email', GitHelper.get_email(), local=True)
        repo.git.add(all=True)
        repo.index.commit('Initial commit', skip_hooks=True)
        return repo

    @pytest.mark.parametrize('buildtool', [
        pytest.param('rpmbuild', marks=pytest.mark.skipif(
            os.geteuid() != 0,
            reason='requires superuser privileges')),
        pytest.param('mock', marks=pytest.mark.long_running),
    ])
    @pytest.mark.integration
    @pytest.mark.usefixtures('initialized_git_repo')
    def test_rebase(self, buildtool):
        cli = CLI([
            '--non-interactive',
            '--disable-inapplicable-patches',
            '--buildtool', buildtool,
            '--outputtool', 'json',
            '--pkgcomparetool', 'rpmdiff,pkgdiff,abipkgdiff,licensecheck',
            '--color=always',
            '--apply-changes',
            self.NEW_VERSION,
        ])
        config = Config()
        config.merge(cli)
        execution_dir, results_dir, debug_log_file = Application.setup(config)
        app = Application(config, execution_dir, results_dir, debug_log_file)
        app.run()
        changes = os.path.join(RESULTS_DIR, 'changes.patch')
        patch = unidiff.PatchSet.from_filename(changes, encoding='UTF-8')
        assert patch[0].is_removed_file   # backported.patch
        assert patch[1].is_modified_file  # test.spec
        assert '-Patch1:         conflicting.patch\n' in patch[1][0].source
        assert '-Patch2:         backported.patch\n' in patch[1][0].source
        assert '+#Patch1: conflicting.patch\n' in patch[1][0].target
        assert '-%patch1 -p1\n' in patch[1][1].source
        assert '-%patch2 -p1\n' in patch[1][1].source
        assert '+#%%patch1 -p1\n' in patch[1][1].target
        assert '+- New upstream release {}\n'.format(self.NEW_VERSION) in patch[1][2].target
        with open(os.path.join(RESULTS_DIR, 'report.json')) as f:
            report = json.load(f)
            assert 'success' in report['result']
            # patches
            assert 'applicable.patch' in report['patches']['untouched']
            assert 'conflicting.patch' in report['patches']['inapplicable']
            assert 'backported.patch' in report['patches']['deleted']
            # licensecheck
            assert report['checkers']['licensecheck']['license_changes']
            assert len(report['checkers']['licensecheck']['disappeared_licenses']) == 1
            assert len(report['checkers']['licensecheck']['new_licenses']) == 1
            # rpmdiff
            assert report['checkers']['rpmdiff']['files_changes']['changed'] == 2
            # abipkgdiff
            assert report['checkers']['abipkgdiff']['abi_changes']
            lib = report['checkers']['abipkgdiff']['packages']['test']['libtest.so']
            assert lib['Functions changes summary']['Added']['count'] == 1
            assert lib['Variables changes summary']['Removed']['count'] == 1
        repo = git.Repo(execution_dir)
        assert '- New upstream release {}'.format(self.NEW_VERSION) in repo.commit().summary
