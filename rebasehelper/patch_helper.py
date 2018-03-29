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

from __future__ import print_function
import os

import git
import six

from rebasehelper.logger import logger
from rebasehelper.utils import ConsoleHelper
from rebasehelper.utils import GitHelper


patch_tools = {}


def register_patch_tool(patch_tool):
    patch_tools[patch_tool.CMD] = patch_tool
    return patch_tool


class PatchBase(object):

    """
    Class used for using several patching command tools, ...
    Each method should overwrite method like run_check
    """

    @classmethod
    def match(cls, cmd=None):  # pylint: disable=unused-argument
        """Method checks whether it is usefull patch method"""
        return NotImplementedError()

    @classmethod
    def run_patch(cls, old_dir, new_dir, rest_sources, patches, **kwargs):  # pylint: disable=unused-argument
        """Method will check all patches in relevant package"""
        return NotImplementedError()


@register_patch_tool
class GitPatchTool(PatchBase):

    """Class for git command used for patching old and new sources"""

    CMD = 'git'
    source_dir = ""
    old_sources = ""
    new_sources = ""
    diff_cls = None
    output_data = None
    old_repo = None
    new_repo = None
    non_interactive = False
    patches = None

    @classmethod
    def match(cls, cmd=None):
        if cmd is not None and cmd == cls.CMD:
            return True
        else:
            return False

    @staticmethod
    def apply_patch(repo, patch_object):
        """
        Function applies patches to old sources
        It tries apply patch with am command and if it fails
        then with command --apply
        """
        logger.debug('Applying patch with am')

        patch_name = patch_object.get_path()
        patch_strip = patch_object.get_strip()
        try:
            repo.git.am(patch_name)
        except git.GitCommandError:
            logger.debug('Applying patch with git-am failed.')
            try:
                repo.git.apply(patch_name, p=patch_strip)
            except git.GitCommandError:
                repo.git.apply(patch_name, p=patch_strip, reject=True, whitespace='fix')
            repo.git.add(all=True)
            repo.index.commit('Patch: {0}'.format(os.path.basename(patch_name)), skip_hooks=True)
        else:
            # replace last commit message with patch name to preserve mapping between commits and patches
            repo.head.reset('HEAD~1', index=False)
            repo.index.commit('Patch: {0}'.format(os.path.basename(patch_name)), skip_hooks=True)

    @classmethod
    def _update_deleted_patches(cls, inapplicable_patches):
        """Function checks patches against rebase-patches"""
        commits = list(cls.old_repo.iter_commits())
        updated_patches = []
        for patch in cls.patches:
            patch_name = patch.get_patch_name()
            if (not [c for c in commits if c.summary.endswith(patch_name)] and
                    patch_name not in inapplicable_patches):
                updated_patches.append(patch_name)
        return updated_patches

    @staticmethod
    def _get_automerged_patches(output):
        automerged_patches = []
        if not output:
            return automerged_patches
        patch_name = None
        for line in output.split('\n'):
            if line.startswith('Applying:'):
                patch_name = line.split()[-1]
            elif line.startswith('Auto-merging'):
                if patch_name and patch_name not in automerged_patches:
                    automerged_patches.append(patch_name)
        return automerged_patches

    @classmethod
    def _git_rebase(cls):
        """Function performs git rebase between old and new sources"""
        # in old_sources do:
        # 1) git remote add new_sources <path_to_new_sources>
        # 2) git fetch new_sources
        # 3) git rebase --onto new_sources/master <root_commit_old_sources> <last_commit_old_sources>
        if not cls.cont:
            logger.info('git-rebase operation to %s is ongoing...', os.path.basename(cls.new_sources))
            upstream = 'new_upstream'
            cls.old_repo.create_remote(upstream, url=cls.new_sources).fetch()
            root_commit = cls.old_repo.git.rev_list('HEAD', max_parents=0)
            last_commit = cls.old_repo.commit('HEAD')
            try:
                cls.output_data = cls.old_repo.git.rebase(root_commit, last_commit,
                                                          onto='{}/master'.format(upstream),
                                                          stdout_as_string=six.PY3)
            except git.GitCommandError as e:
                ret_code = e.status
                cls.output_data = e.stdout
            else:
                ret_code = 0
        else:
            logger.info('git-rebase operation continues...')
            try:
                cls.output_data = cls.old_repo.git.rebase(skip=True, stdout_as_string=six.PY3)
            except git.GitCommandError as e:
                ret_code = e.status
                cls.output_data = e.stdout
            else:
                ret_code = 0
        logger.debug(cls.output_data)
        patch_dictionary = {}
        modified_patches = []
        inapplicable_patches = []
        while True:
            automerged_patches = cls._get_automerged_patches(cls.output_data)
            for patch_name in automerged_patches:
                commits = [c for c in cls.old_repo.iter_commits() if c.summary.endswith(patch_name)]
                if commits:
                    base_name = os.path.join(cls.kwargs['rebased_sources_dir'], patch_name)
                    diff = cls.old_repo.git.diff(commits[0].parents[0], commits[0], stdout_as_string=False)
                    with open(base_name, 'wb') as f:
                        f.write(diff)
                        f.write(b'\n')
                    modified_patches.append(patch_name)
            if ret_code != 0:
                # get name of the current patch using .git/rebase-apply/next
                try:
                    with open(os.path.join(cls.old_sources, '.git', 'rebase-apply', 'next')) as f:
                        patch_name = cls.patches[int(f.readline()) - 1].get_patch_name()
                except IOError:
                    raise RuntimeError('Git rebase failed with unknown reason. Please check log file')
                if not cls.non_interactive:
                    logger.info("Git has problems with rebasing patch %s", patch_name)
                    GitHelper.run_mergetool(cls.old_repo)
                else:
                    inapplicable_patches.append(patch_name)
                    try:
                        cls.output_data = cls.old_repo.git.rebase(skip=True, stdout_as_string=six.PY3)
                    except git.GitCommandError as e:
                        ret_code = e.status
                        cls.output_data = e.stdout
                    else:
                        ret_code = 0
                    continue
                base_name = os.path.join(cls.kwargs['rebased_sources_dir'], patch_name)
                # unstaged changes
                diff = cls.old_repo.commit().diff(None)
                if diff:
                    # staged changes
                    diff = cls.old_repo.index.diff(cls.old_repo.commit())
                    modified_files = [d.a_path for d in diff]
                    logger.info('Following files were modified: %s', ', '.join(modified_files))
                    try:
                        commit = cls.old_repo.index.commit(patch_name, skip_hooks=True)
                    except git.UnmergedEntriesError:
                        inapplicable_patches.append(patch_name)
                    else:
                        diff = cls.old_repo.git.diff(commit.parents[0], commit, stdout_as_string=False)
                        with open(base_name, 'wb') as f:
                            f.write(diff)
                            f.write(b'\n')
                        modified_patches.append(patch_name)
                if not cls.non_interactive:
                    if not ConsoleHelper.get_message('Do you want to continue with another patch'):
                        raise KeyboardInterrupt
                try:
                    cls.output_data = cls.old_repo.git.rebase(skip=True, stdout_as_string=six.PY3)
                except git.GitCommandError as e:
                    ret_code = e.status
                    cls.output_data = e.stdout
                else:
                    ret_code = 0
            else:
                break
        deleted_patches = cls._update_deleted_patches(inapplicable_patches)
        if deleted_patches:
            patch_dictionary['deleted'] = deleted_patches
        if modified_patches:
            patch_dictionary['modified'] = modified_patches
        if inapplicable_patches:
            patch_dictionary['inapplicable'] = inapplicable_patches
        patches = [os.path.basename(p.path) for p in cls.patches]
        untouched_patches = [p for p in patches if p not in deleted_patches + modified_patches + inapplicable_patches]
        if untouched_patches:
            patch_dictionary['untouched'] = untouched_patches
        # TODO correct settings for merge tool in ~/.gitconfig
        # currently now meld is not started
        return patch_dictionary

    @classmethod
    def apply_old_patches(cls):
        """Function applies a patch to a old/new sources"""
        for patch in cls.patches:
            logger.info("Applying patch '%s' to '%s'",
                        os.path.basename(patch.get_path()),
                        os.path.basename(cls.source_dir))
            try:
                cls.apply_patch(cls.old_repo, patch)
            except git.GitCommandError:
                raise RuntimeError('Failed to patch old sources')

    @classmethod
    def init_git(cls, directory):
        """Function initialize old and new Git repository"""
        repo = git.Repo.init(directory)
        repo.git.config('user.name', GitHelper.get_user(), local=True)
        repo.git.config('user.email', GitHelper.get_email(), local=True)
        repo.git.add(all=True)
        repo.index.commit('Initial commit', skip_hooks=True)
        return repo

    @classmethod
    def run_patch(cls, old_dir, new_dir, rest_sources, patches, **kwargs):
        """
        The function can be used for patching one
        directory against another
        """
        cls.kwargs = kwargs
        cls.old_sources = old_dir
        cls.new_sources = new_dir
        cls.output_data = None
        cls.cont = cls.kwargs['continue']
        cls.rest_sources = rest_sources
        cls.patches = patches
        cls.non_interactive = kwargs.get('non_interactive')
        if not os.path.isdir(os.path.join(cls.old_sources, '.git')):
            cls.old_repo = cls.init_git(old_dir)
            cls.new_repo = cls.init_git(new_dir)
            cls.source_dir = cls.old_sources
            cls.apply_old_patches()
            cls.cont = False
        else:
            cls.old_repo = git.Repo(old_dir)
            cls.new_repo = git.Repo(new_dir)

        return cls._git_rebase()


class Patcher(object):

    """
    Class representing a process of applying and generating rebased patch using specific tool.
    """

    def __init__(self, tool=None):
        """
        Constructor

        :param tool: tool to be used. If not supported, raises NotImplementedError
        :return: None
        """
        if tool is None:
            raise TypeError("Expected argument 'tool' (pos 1) is missing")
        self._patch_tool_name = tool
        self._tool = None

        for patch_tool in patch_tools.values():
            if patch_tool.match(self._patch_tool_name):
                self._tool = patch_tool

        if self._tool is None:
            raise NotImplementedError("Unsupported patch tool")

    def patch(self, old_dir, new_dir, rest_sources, patches, **kwargs):
        """
        Apply patches and generate rebased patches if needed

        :param old_dir: path to dir with old patches
        :param new_dir: path to dir with new patches
        :param patches: old patches
        :param rebased_patches: rebased patches
        :param kwargs: --
        :return:
        """
        logger.debug("Patching source by patch tool %s", self._patch_tool_name)
        return self._tool.run_patch(old_dir, new_dir, rest_sources, patches, **kwargs)
