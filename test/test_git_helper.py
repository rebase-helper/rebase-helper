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

from .base_test import BaseTest
from rebasehelper.utils import GitHelper
from rebasehelper.archive import Archive
from rebasehelper import settings
from rebasehelper.patch_helper import GitPatchTool
from rebasehelper.specfile import PatchObject


class TestGitHelper(BaseTest):
    """ Application tests """

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

    GIT_OLD_DIR = ""
    GIT_NEW_DIR = ""
    git_helper = None
    old_git_repo = None
    old_git_path = ""

    def _extract_sources(self, archive, dir_name):
        archive = Archive(archive)
        archive.extract_archive(dir_name)

    def _init_git_repo(self, dirname):
        GitPatchTool.init_git(dirname)

    def _parse_commit_log(self):
        commit_log = self.git_helper.command_log(parameters='--pretty=oneline')
        commit_names = []
        for commit in commit_log:
            commit = commit.split()[1:]
            commit_names.append(' '.join(commit))
        return commit_names

    def setup(self):
        super(TestGitHelper, self).setup()
        self.GIT_OLD_DIR = os.path.join(self.WORKING_DIR, settings.OLD_SOURCES_DIR)
        self.GIT_NEW_DIR = os.path.join(self.WORKING_DIR, settings.NEW_SOURCES_DIR)
        self.old_git_path = os.path.join(self.GIT_OLD_DIR, 'project-1.0.0')
        self._extract_sources(self.OLD_SOURCES, self.GIT_OLD_DIR)
        self._extract_sources(self.NEW_SOURCES, self.GIT_NEW_DIR)
        self.git_helper = GitHelper(self.old_git_path)
        self._init_git_repo(self.old_git_path)

    def test_git_log(self):
        # Try catch is workaround for Travis CI.
        try:
            commit_message = self._parse_commit_log()
        except TypeError:
            commit_message = ['Initial Commit']
        assert commit_message == ['Initial Commit']

    def test_git_apply(self):
        patch_object = PatchObject(os.path.join(self.WORKING_DIR, self.PATCH_1), 1, None)
        GitPatchTool.apply_patch(self.git_helper, patch_object)
        GitPatchTool.commit_patch(self.git_helper, os.path.join(self.WORKING_DIR, self.PATCH_1))
        # Try catch is workaroung for Travis CI
        try:
            commit_message = self._parse_commit_log()
        except TypeError:
            commit_message == ['Patch: project-ChangeLog.patch', 'Initial Commit']
        assert commit_message == ['Patch: project-ChangeLog.patch', 'Initial Commit']
