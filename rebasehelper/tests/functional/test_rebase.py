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

import json
import os

import git  # type: ignore
import pytest  # type: ignore
import unidiff  # type: ignore

from typing import List

from rebasehelper.cli import CLI
from rebasehelper.config import Config
from rebasehelper.application import Application
from rebasehelper.constants import RESULTS_DIR
from rebasehelper.helpers.git_helper import GitHelper


@pytest.fixture
def initialized_git_repo(workdir):
    repo = git.Repo.init(workdir)
    # Configure user otherwise app.apply_changes() will fail
    repo.git.config('user.name', GitHelper.get_user(), local=True)
    repo.git.config('user.email', GitHelper.get_email(), local=True)
    repo.git.add(all=True)
    repo.index.commit('Initial commit', skip_hooks=True)
    return repo


class TestRebase:

    TEST_FILES: List[str] = [
        'rebase/test.spec',
        'rebase/applicable.patch',
        'rebase/conflicting.patch',
        'rebase/backported.patch',
    ]

    NEW_VERSION: str = '0.2'

    @pytest.mark.parametrize('buildtool', [
        pytest.param('rpmbuild', marks=pytest.mark.skipif(
            os.geteuid() != 0,
            reason='requires superuser privileges')),
        pytest.param('mock', marks=pytest.mark.long_running),
    ])
    @pytest.mark.parametrize('favor_on_conflict', ['upstream', 'downstream', 'off'])
    @pytest.mark.integration
    @pytest.mark.usefixtures('initialized_git_repo')
    def test_rebase(self, buildtool, favor_on_conflict):
        cli = CLI([
            '--non-interactive',
            '--disable-inapplicable-patches',
            '--buildtool', buildtool,
            '--favor-on-conflict', favor_on_conflict,
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

        if favor_on_conflict == 'upstream':
            backported_patch, conflicting_patch, spec_file = patch
            assert conflicting_patch.is_removed_file  # conflicting.patch
        elif favor_on_conflict == 'downstream':
            backported_patch, conflicting_patch, spec_file = patch
            assert conflicting_patch.is_modified_file  # conflicting.patch
        else:
            backported_patch, spec_file = patch
            # Non interactive mode - inapplicable patches are only commented out.
            assert '+#Patch1: conflicting.patch\n' in spec_file[0].target
            assert '+#%%patch1 -p1\n' in spec_file[1].target
        assert backported_patch.is_removed_file   # backported.patch
        assert spec_file.is_modified_file  # test.spec
        if favor_on_conflict != 'downstream':
            assert '-Patch1:         conflicting.patch\n' in spec_file[0].source
            assert '-%patch1 -p1\n' in spec_file[1].source
        assert '-Patch2:         backported.patch\n' in spec_file[0].source
        assert '-%patch2 -p1\n' in spec_file[1].source
        assert '+- New upstream release {}\n'.format(self.NEW_VERSION) in spec_file[2].target
        with open(os.path.join(RESULTS_DIR, 'report.json')) as f:
            report = json.load(f)
            assert 'success' in report['result']
            # patches
            assert 'applicable.patch' in report['patches']['untouched']
            if favor_on_conflict == 'upstream':
                # In case of conflict, upstream code is favored, therefore conflicting patch is unused.
                assert 'conflicting.patch' in report['patches']['deleted']
            elif favor_on_conflict == 'downstream':
                assert 'conflicting.patch' in report['patches']['modified']
            else:
                # Non interactive mode - skipping conflicting patches
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
            if favor_on_conflict != 'downstream':
                assert lib['Variables changes summary']['Removed']['count'] == 1
        repo = git.Repo(execution_dir)
        assert '- New upstream release {}'.format(self.NEW_VERSION) in repo.commit().summary


class TestBuildLogHooks:
    TEST_FILES: List[str] = [
        'build-log-hooks/test-build-log-hooks.spec'
    ]

    NEW_VERSION: str = '0.2'

    @pytest.mark.parametrize('buildtool', [
        pytest.param('rpmbuild', marks=pytest.mark.skipif(
            os.geteuid() != 0,
            reason='requires superuser privileges')),
        pytest.param('mock', marks=pytest.mark.long_running),
    ])
    @pytest.mark.integration
    @pytest.mark.usefixtures('initialized_git_repo')
    def test_files_build_log_hook(self, buildtool):
        cli = CLI([
            '--non-interactive',
            '--force-build-log-hooks',
            '--buildtool', buildtool,
            '--outputtool', 'json',
            '--color=always',
            self.NEW_VERSION,
        ])
        config = Config()
        config.merge(cli)
        execution_dir, results_dir, debug_log_file = Application.setup(config)
        app = Application(config, execution_dir, results_dir, debug_log_file)
        app.run()

        changes = os.path.join(RESULTS_DIR, 'changes.patch')
        patch = unidiff.PatchSet.from_filename(changes, encoding='UTF-8')
        spec_file = patch[0]

        assert spec_file.is_modified_file
        # removed files
        assert '-%license LICENSE README\n' in spec_file[1].source
        assert '+%license LICENSE\n' in spec_file[1].target
        assert '-%license /licensedir/test_license\n' in spec_file[1].source
        assert '-/dirA/fileB\n' in spec_file[1].source
        assert '-/dirB/fileY\n' in spec_file[1].source
        assert '-%doc docs_dir/AUTHORS\n' in spec_file[1].source

        # added files
        assert '+/dirA/fileC\n' in spec_file[1].target
        assert '+/dirB/fileW\n' in spec_file[1].target

        with open(os.path.join(RESULTS_DIR, 'report.json')) as f:
            report = json.load(f)
            assert 'success' in report['result']
            added = report['build_log_hooks']['files']['added']
            assert '/dirA/fileC' in added['%files']
            assert '/dirB/fileW' in added['%files devel']
            removed = report['build_log_hooks']['files']['removed']
            assert 'README' in removed['%files']
            assert '/licensedir/test_license' in removed['%files']
            assert '/dirA/fileB' in removed['%files']
            assert '/dirB/fileY' in removed['%files devel']
            assert 'docs_dir/AUTHORS' in removed['%files devel']
