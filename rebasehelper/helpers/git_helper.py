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

from rebasehelper.logger import logger
from rebasehelper.helpers.process_helper import ProcessHelper


class GitHelper:

    """Class which operates with git repositories"""

    # provide fallback values if system is not configured
    GIT_USER_NAME: str = 'rebase-helper'
    GIT_USER_EMAIL: str = 'rebase-helper@localhost.local'

    @classmethod
    def get_user(cls):
        try:
            return git.cmd.Git().config('user.name', get=True, stdout_as_string=True)
        except git.GitCommandError:
            logger.warning("Failed to get configured git user name, using '%s'", cls.GIT_USER_NAME)
            return cls.GIT_USER_NAME

    @classmethod
    def get_email(cls):
        try:
            return git.cmd.Git().config('user.email', get=True, stdout_as_string=True)
        except git.GitCommandError:
            logger.warning("Failed to get configured git user email, using '%s'", cls.GIT_USER_EMAIL)
            return cls.GIT_USER_EMAIL

    @classmethod
    def run_mergetool(cls, repo):
        # we can't use GitPython here, as it doesn't allow
        # for the command to attach to stdout directly
        cwd = os.getcwd()
        try:
            os.chdir(repo.working_tree_dir)
            ProcessHelper.run_subprocess(['git', 'mergetool'])
        finally:
            os.chdir(cwd)
