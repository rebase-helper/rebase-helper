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

import os

import pytest

from rebasehelper.utils import GitHelper
from rebasehelper.archive import Archive
from rebasehelper import settings
from rebasehelper.patch_helper import GitPatchTool
from rebasehelper.specfile import PatchObject


class TestGitHelper(object):
    OLD_SOURCES = 'project-1.0.0.tar.gz'
    NEW_SOURCES = 'project-1.0.1.tar.gz'
    PATCH_1 = 'project-ChangeLog.patch'
    PATCH_2 = 'project-NEW-update.patch'

    TEST_FILES = [
        OLD_SOURCES,
        NEW_SOURCES,
        PATCH_1,
        PATCH_2,
    ]

    @staticmethod
    def _extract_sources(archive_path, dir_name):
        archive = Archive(archive_path)
        archive.extract_archive(dir_name)

    @staticmethod
    def _init_git_repo(dirname):
        GitPatchTool.init_git(dirname)

    @staticmethod
    def _parse_commit_log(git_helper):
        commit_log = git_helper.command_log(parameters='--pretty=oneline')
        commit_names = []
        for commit in commit_log:
            commit = commit.split()[1:]
            commit_names.append(' '.join(commit))
        return commit_names

    @pytest.fixture
    def git_helper(self, workdir):
        git_old_dir = os.path.join(workdir, settings.OLD_SOURCES_DIR)
        git_new_dir = os.path.join(workdir, settings.NEW_SOURCES_DIR)
        old_git_path = os.path.join(git_old_dir, 'project-1.0.0')
        self._extract_sources(self.OLD_SOURCES, git_old_dir)
        self._extract_sources(self.NEW_SOURCES, git_new_dir)
        gh = GitHelper(old_git_path)
        self._init_git_repo(old_git_path)
        return gh

    def test_git_log(self, git_helper):
        commit_message = self._parse_commit_log(git_helper)
        assert commit_message == ['Initial Commit']

    def test_git_apply(self, workdir, git_helper):
        patch_object = PatchObject(os.path.join(workdir, self.PATCH_1), 1, None)
        GitPatchTool.apply_patch(git_helper, patch_object)
        GitPatchTool.commit_patch(git_helper, os.path.join(workdir, self.PATCH_1))
        commit_message = self._parse_commit_log(git_helper)
        assert commit_message == ['Patch: project-ChangeLog.patch', 'Initial Commit']
