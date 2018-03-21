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

import json
import os

import git
import pytest
import unidiff

from rebasehelper.cli import CLI
from rebasehelper.config import Config
from rebasehelper.application import Application
from rebasehelper.settings import REBASE_HELPER_RESULTS_DIR


class TestRebase(object):

    @pytest.fixture
    def cloned_dist_git(self, url, commit, workdir):
        repo = git.Repo.clone_from(url, workdir)
        repo.git.checkout(commit)
        return repo

    @pytest.mark.parametrize('buildtool', [
        pytest.mark.skipif(
            os.geteuid() != 0,
            reason='requires superuser privileges')
        ('rpmbuild'),
        'mock',
    ])
    @pytest.mark.parametrize('package, url, commit, version, patches', [
        (
            'vim-go',
            'https://src.fedoraproject.org/git/rpms/vim-go.git',
            'ccf44ccc71e9c4662ebb2c9066f46bbf49bd2e02',
            '1.12',
            {'deleted': None, 'modified': None, 'inapplicable': None},
        ),
        pytest.mark.long_running((
            'libtiff',
            'https://src.fedoraproject.org/git/rpms/libtiff.git',
            '7b1dffc529cb934f8d30083e624f874a2df7c981',
            '4.0.8',
            {
                'deleted': {
                    'libtiff-hylafax-fix.patch',
                    'libtiff-CVE-2017-7592.patch',
                    'libtiff-CVE-2017-7593.patch',
                    'libtiff-CVE-2017-7596_7597_7599_7600.patch',
                    'libtiff-CVE-2017-7598.patch',
                    'libtiff-CVE-2017-7601.patch',
                    'libtiff-CVE-2016-10266.patch',
                    'libtiff-CVE-2016-10267.patch',
                    'libtiff-CVE-2016-10268.patch',
                    'libtiff-CVE-2016-10269.patch',
                    'libtiff-CVE-2016-10270.patch',
                    'libtiff-CVE-2016-10271_10272.patch',
                },
                'modified': None,
                'inapplicable': {
                    'libtiff-CVE-2017-7594.patch',
                    'libtiff-CVE-2017-7595.patch',
                    'libtiff-CVE-2017-7602.patch',
                },
            },
        )),
    ], ids=[
        'vim-go-1.11-2=>1.12',
        'libtiff-4.0.7-5=>4.0.8',
    ])
    @pytest.mark.usefixtures('cloned_dist_git')
    def test_rebase(self, buildtool, package, version, patches):
        cli = CLI([
            '--non-interactive',
            '--disable-inapplicable-patches',
            '--buildtool', buildtool,
            '--outputtool', 'json',
            '--pkgcomparetool', 'rpmdiff,pkgdiff,abipkgdiff',
            '--color=always',
            version
        ])
        config = Config()
        config.merge(cli)
        execution_dir, results_dir, debug_log_file = Application.setup(config)
        app = Application(config, execution_dir, results_dir, debug_log_file)
        app.run()
        with open(os.path.join(REBASE_HELPER_RESULTS_DIR, 'report.json')) as f:
            report = json.load(f)
            for k in ['deleted', 'modified', 'inapplicable']:
                assert set(report['patches'].get(k, [])) == (patches[k] or set())
        changes = os.path.join(REBASE_HELPER_RESULTS_DIR, 'changes.patch')
        patch = unidiff.PatchSet.from_filename(changes, encoding='UTF-8')
        pf = [pf for pf in patch if pf.path == '{}.spec'.format(package)]
        assert pf
        ver = [l for h in pf[0] for l in h.target if l.startswith('+Version')]
        assert ver
        assert version in ver[0]
