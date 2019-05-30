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

import git  # type: ignore
import pytest  # type: ignore

from rebasehelper.helpers.git_helper import GitHelper


class TestGitHelper:

    def write_config_file(self, config_file, name, email):
        with open(config_file, 'w') as f:
            f.write('[user]\n'
                    '    name = {0}\n'
                    '    email = {1}\n'.format(name, email))

    @pytest.mark.parametrize('config', [
        # Get from $XDG_CONFIG_HOME/git/config
        'global',
        # Get from included file in $XDG_CONFIG_HOME/git/config
        'global_include',
        # Get from $repo_path/.git/config
        'local',
        # Get from GIT_CONFIG
        'env',
    ])
    def test_get_user_and_email(self, config, workdir):
        name = 'Foo Bar'
        email = 'foo@bar.com'
        env = os.environ.copy()

        try:
            if config == 'global':
                work_git_path = os.path.join(workdir, 'git')
                os.makedirs(work_git_path)

                config_file = os.path.join(work_git_path, 'config')
                self.write_config_file(config_file, name, email)
                os.environ['HOME'] = workdir
                os.environ['XDG_CONFIG_HOME'] = workdir
            elif config == 'global_include':
                work_git_path = os.path.join(workdir, 'git')
                os.makedirs(work_git_path)

                config_file = os.path.join(work_git_path, 'config')
                with open(config_file, 'w') as f:
                    f.write('[include]\n'
                            '    path = included_config\n')
                included_config_file = os.path.join(work_git_path, 'included_config')
                self.write_config_file(included_config_file, name, email)
                os.environ['HOME'] = workdir
                os.environ['XDG_CONFIG_HOME'] = workdir
            elif config == 'local':
                repo = git.Repo.init(workdir)
                repo.git.config('user.name', name, local=True)
                repo.git.config('user.email', email, local=True)
            elif config == 'env':
                config_file = os.path.join(workdir, 'git_config')
                os.environ['GIT_CONFIG'] = config_file
                self.write_config_file(config_file, name, email)
            else:
                raise RuntimeError()

            assert name == GitHelper.get_user()
            assert email == GitHelper.get_email()
        finally:
            os.environ = env
