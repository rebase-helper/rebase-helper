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
from rebasehelper.constants import RESULTS_DIR, CHANGES_PATCH, ENCODING
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
        'rebase/backported.patch',
        'rebase/conflicting.patch',
        'rebase/renamed-0.1.patch',
    ]

    @pytest.mark.xfail(reason='''
        the test fails from time to time due to RPM macros not being expanded,
        see https://github.com/rebase-helper/rebase-helper/issues/811
    ''')
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
        new_version = '0.2'

        cli = CLI([
            '--non-interactive',
            '--disable-inapplicable-patches',
            '--buildtool', buildtool,
            '--favor-on-conflict', favor_on_conflict,
            '--outputtool', 'json',
            '--pkgcomparetool', 'rpmdiff,pkgdiff,abipkgdiff,licensecheck,sonamecheck',
            '--color=always',
            '--apply-changes',
            new_version,
        ])
        config = Config()
        config.merge(cli)
        execution_dir, results_dir = Application.setup(config)
        app = Application(config, os.getcwd(), execution_dir, results_dir)
        app.run()
        changes = os.path.join(RESULTS_DIR, CHANGES_PATCH)
        patch = unidiff.PatchSet.from_filename(changes, encoding='UTF-8')

        if favor_on_conflict == 'upstream':
            backported_patch, conflicting_patch, renamed_patch, spec_file = patch
            assert conflicting_patch.is_removed_file  # conflicting.patch
        elif favor_on_conflict == 'downstream':
            backported_patch, conflicting_patch, renamed_patch, spec_file = patch
            assert conflicting_patch.is_modified_file  # conflicting.patch
        else:
            backported_patch, renamed_patch, spec_file = patch
            # Non interactive mode - inapplicable patches are only commented out.
            assert [h for h in spec_file if '+#Patch1:         conflicting.patch\n' in h.target]
            assert [h for h in spec_file if '+#%%patch1 -p1\n' in h.target]
        assert renamed_patch.is_rename  # renamed patch 0.1.patch to 0.2.patch
        assert os.path.basename(renamed_patch.source_file) == 'renamed-0.1.patch'
        assert os.path.basename(renamed_patch.target_file) == 'renamed-0.2.patch'
        # Check that the renamed patch path is unchanged
        assert not [h for h in spec_file if '-Patch3:         renamed-%{version}.patch\n' in h.source]
        assert backported_patch.is_removed_file   # backported.patch
        assert spec_file.is_modified_file  # test.spec
        if favor_on_conflict != 'downstream':
            assert [h for h in spec_file if '-Patch1:         conflicting.patch\n' in h.source]
            assert [h for h in spec_file if '-%patch1 -p1\n' in h.source]
        assert [h for h in spec_file if '-Patch2:         backported.patch\n' in h.source]
        assert [h for h in spec_file if '-%patch2 -p1\n' in h.source]
        assert [h for h in spec_file if '+- New upstream release {}\n'.format(new_version) in h.target]
        with open(os.path.join(RESULTS_DIR, 'report.json'), encoding=ENCODING) as f:
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
            assert report['checkers']['rpmdiff']['files_changes']['added'] == 1
            assert report['checkers']['rpmdiff']['files_changes']['changed'] == 3
            assert report['checkers']['rpmdiff']['files_changes']['removed'] == 1
            # abipkgdiff
            assert report['checkers']['abipkgdiff']['abi_changes']
            lib = report['checkers']['abipkgdiff']['packages']['test']['libtest1.so']
            if 'Function symbols changes summary' in lib:
                assert lib['Function symbols changes summary']['Added']['count'] == 1
            elif 'Functions changes summary' in lib:
                assert lib['Functions changes summary']['Added']['count'] == 1
            if favor_on_conflict != 'downstream':
                if 'Variable symbols changes summary' in lib:
                    assert lib['Variable symbols changes summary']['Removed']['count'] == 1
                elif 'Variables changes summary' in lib:
                    assert lib['Variables changes summary']['Removed']['count'] == 1
            # sonamecheck
            change = report['checkers']['sonamecheck']['soname_changes']['test']['changed'][0]
            assert change['from'] == 'libtest2.so.0.1'
            assert change['to'] == 'libtest2.so.0.2'

        repo = git.Repo(execution_dir)
        assert '- New upstream release {}'.format(new_version) in repo.commit().summary

    @pytest.mark.parametrize('buildtool', [
        pytest.param('rpmbuild', marks=pytest.mark.skipif(
            os.geteuid() != 0,
            reason='requires superuser privileges')),
        pytest.param('mock', marks=pytest.mark.long_running),
    ])
    @pytest.mark.integration
    @pytest.mark.usefixtures('initialized_git_repo')
    def test_files_build_log_hook(self, buildtool):
        new_version = '0.3'

        cli = CLI([
            '--non-interactive',
            '--disable-inapplicable-patches',
            '--force-build-log-hooks',
            '--buildtool', buildtool,
            '--outputtool', 'json',
            '--pkgcomparetool', '',
            '--color=always',
            new_version,
        ])
        config = Config()
        config.merge(cli)
        execution_dir, results_dir = Application.setup(config)
        app = Application(config, os.getcwd(), execution_dir, results_dir)
        app.run()
        changes = os.path.join(RESULTS_DIR, CHANGES_PATCH)
        patch = unidiff.PatchSet.from_filename(changes, encoding='UTF-8')

        _, _, spec_file = patch

        assert spec_file.is_modified_file
        # removed files
        assert [h for h in spec_file if '-%doc README.md CHANGELOG.md\n' in h.source]
        assert [h for h in spec_file if '+%doc README.md\n' in h.target]
        assert [h for h in spec_file if '-%doc %{_docdir}/%{name}/notes.txt\n' in h.source]
        assert [h for h in spec_file if '-%{_datadir}/%{name}/1.dat\n' in h.source]
        assert [h for h in spec_file if '-%{_datadir}/%{name}/extra/C.dat\n' in h.source]
        assert [h for h in spec_file if '-%doc data/extra/README.extra\n' in h.source]
        # added files
        assert [h for h in spec_file if '+%{_datadir}/%{name}/2.dat\n' in h.target]
        assert [h for h in spec_file if '+%{_datadir}/%{name}/extra/D.dat\n' in h.target]

        with open(os.path.join(RESULTS_DIR, 'report.json'), encoding=ENCODING) as f:
            report = json.load(f)
            assert 'success' in report['result']
            # files build log hook
            added = report['build_log_hooks']['files']['added']
            assert '%{_datadir}/%{name}/2.dat' in added['%files']
            assert '%{_datadir}/%{name}/extra/D.dat' in added['%files extra']
            removed = report['build_log_hooks']['files']['removed']
            assert 'CHANGELOG.md' in removed['%files']
            assert '%{_docdir}/%{name}/notes.txt' in removed['%files']
            assert '%{_datadir}/%{name}/1.dat' in removed['%files']
            assert '%{_datadir}/%{name}/extra/C.dat' in removed['%files extra']
            assert 'data/extra/README.extra' in removed['%files extra']
