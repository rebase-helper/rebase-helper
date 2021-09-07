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

import logging
import os
import re
import shutil
import tempfile
from typing import List, Optional, cast

import git  # type: ignore
import unidiff  # type: ignore

from rebasehelper.specfile import PatchObject
from rebasehelper.helpers.git_helper import GitHelper
from rebasehelper.helpers.input_helper import InputHelper
from rebasehelper.constants import ENCODING
from rebasehelper.logger import CustomLogger


logger: CustomLogger = cast(CustomLogger, logging.getLogger(__name__))


class Patcher:

    """Class for git command used for patching old and new sources"""

    old_sources: Optional[str] = None
    new_sources: Optional[str] = None
    output_data: Optional[str] = None
    old_repo: Optional[git.Repo] = None
    new_repo: Optional[git.Repo] = None
    non_interactive: bool = False
    patches: List[PatchObject] = []

    @staticmethod
    def decorate_patch_name(patch_name):
        return '<<[{0}]>>'.format(patch_name)

    @classmethod
    def insert_patch_name(cls, message, patch_name):
        return '{0}\n\n{1}'.format(message, cls.decorate_patch_name(patch_name))

    @classmethod
    def extract_patch_name(cls, message):
        for line in message.split('\n'):
            if line.startswith('<<[') and line.endswith(']>>'):
                return line[3:-3]
        return None

    @classmethod
    def strip_patch_name(cls, diff, patch_name):
        token = '\n\n{0}'.format(cls.decorate_patch_name(patch_name)).encode(ENCODING)
        try:
            idx = diff.index(token)
            return diff[:idx] + diff[idx + len(token):]
        except (IndexError, ValueError):
            return diff

    @classmethod
    def apply_patch(cls, repo, patch_object):
        """
        Function applies patches to old sources
        It tries apply patch with am command and if it fails
        then with command --apply
        """
        def sanitize(patch_filename):
            diffgit = re.compile(r'diff\s+--git\s+(a/.*)\s+(b/.*)')
            patch = unidiff.PatchSet.from_filename(patch_filename)
            for pf in patch:
                # use paths from "diff --git" line if present
                if pf.patch_info:
                    for line in pf.patch_info:
                        m = diffgit.match(line)
                        if not m:
                            continue
                        pf.source_file = m.group(1)
                        pf.target_file = m.group(2)
                # use the shortest path
                fn = min([pf.source_file, pf.target_file], key=len)
                pf.source_file = fn
                pf.target_file = fn
            tmp = tempfile.NamedTemporaryFile(mode='w')
            tmp.write(str(patch))
            tmp.flush()
            return tmp
        logger.verbose('Applying patch with git-am')
        patch_name = patch_object.path
        patch_strip = patch_object.strip
        try:
            repo.git.am(patch_name)
            commit = repo.head.commit
        except git.GitCommandError as e:
            logger.verbose('Applying patch with git-am failed.')
            logger.debug(str(e))
            try:
                repo.git.am(abort=True)
            except git.GitCommandError:
                pass
            logger.verbose('Applying patch with git-apply')
            # before trying git-apply, sanitize the paths in the patch
            with sanitize(patch_name) as sanitized_patch:
                try:
                    repo.git.apply(sanitized_patch.name, p=patch_strip)
                except git.GitCommandError:
                    try:
                        repo.git.apply(sanitized_patch.name, p=patch_strip, reject=True, whitespace='fix')
                    except git.GitCommandError as e:
                        logger.verbose('Applying patch with git-apply failed.')
                        logger.debug(str(e))
                        raise
            repo.git.add(all=True)
            commit = repo.index.commit(cls.decorate_patch_name(os.path.basename(patch_name)), skip_hooks=True)
        repo.git.commit(amend=True, m=cls.insert_patch_name(commit.message, os.path.basename(patch_name)))

    @classmethod
    def _git_rebase(cls):
        """Function performs git rebase between old and new sources"""
        def compare_commits(a, b):
            # compare commit diffs disregarding differences in blob hashes
            attributes = (
                'a_mode', 'b_mode', 'a_rawpath', 'b_rawpath',
                'new_file', 'deleted_file', 'raw_rename_from', 'raw_rename_to',
                'diff', 'change_type', 'score')
            diff1 = a.diff(a.parents[0], create_patch=True)
            diff2 = b.diff(b.parents[0], create_patch=True)
            if len(diff1) != len(diff2):
                return False
            for d1, d2 in zip(diff1, diff2):
                for attr in attributes:
                    if getattr(d1, attr) != getattr(d2, attr):
                        return False
            return True
        # in old_sources do:
        # 1) git remote add new_sources <path_to_new_sources>
        # 2) git fetch new_sources
        # 3) git rebase --onto new_sources/master <root_commit_old_sources> <last_commit_old_sources>
        if not os.path.exists(os.path.join(cls.old_sources, '.git', 'rebase-apply')):
            logger.info('git-rebase operation to %s is ongoing...', os.path.basename(cls.new_sources))
            upstream = 'new_upstream'
            cls.old_repo.create_remote(upstream, url=cls.new_sources).fetch()
            root_commit = cls.old_repo.git.rev_list('HEAD', max_parents=0)
            last_commit = cls.old_repo.commit('HEAD')
            if cls.favor_on_conflict == 'upstream':
                strategy_option = 'ours'
            elif cls.favor_on_conflict == 'downstream':
                strategy_option = 'theirs'
            else:
                strategy_option = False
            try:
                cls.output_data = cls.old_repo.git.rebase(root_commit, last_commit,
                                                          strategy_option=strategy_option,
                                                          onto='{}/master'.format(upstream),
                                                          stdout_as_string=True)
            except git.GitCommandError as e:
                ret_code = e.status
                cls.output_data = e.stdout
            else:
                ret_code = 0
        else:
            logger.info('git-rebase operation continues...')
            try:
                cls.output_data = cls.old_repo.git.rebase('--continue', stdout_as_string=True)
            except git.GitCommandError as e:
                ret_code = e.status
                cls.output_data = e.stdout
            else:
                ret_code = 0
        logger.verbose(cls.output_data)
        patch_dictionary = {}
        modified_patches = []
        inapplicable_patches = []
        while ret_code != 0:
            if not cls.old_repo.index.unmerged_blobs() and not cls.old_repo.index.diff(cls.old_repo.commit()):
                # empty commit - conflict has been automatically resolved - skip
                try:
                    cls.output_data = cls.old_repo.git.rebase(skip=True, stdout_as_string=True)
                except git.GitCommandError as e:
                    ret_code = e.status
                    cls.output_data = e.stdout
                    continue
                else:
                    break
            try:
                if os.path.isdir(os.path.join(cls.old_sources, '.git', 'rebase-merge')):
                    with open(os.path.join(cls.old_sources, '.git', 'rebase-merge', 'msgnum'), encoding=ENCODING) as f:
                        next_index = int(f.readline())
                    with open(os.path.join(cls.old_sources, '.git', 'rebase-merge', 'end'), encoding=ENCODING) as f:
                        last_index = int(f.readline())
                else:
                    with open(os.path.join(cls.old_sources, '.git', 'rebase-apply', 'next'), encoding=ENCODING) as f:
                        next_index = int(f.readline())
                    with open(os.path.join(cls.old_sources, '.git', 'rebase-apply', 'last'), encoding=ENCODING) as f:
                        last_index = int(f.readline())
            except (FileNotFoundError, IOError) as e:
                raise RuntimeError('Git rebase failed with unknown reason. Please check log file') from e
            patch_name = cls.patches[next_index - 1].get_patch_name()
            inapplicable = False
            if cls.non_interactive:
                inapplicable = True
            else:
                logger.info('Failed to auto-merge patch %s', patch_name)
                unmerged = cls.old_repo.index.unmerged_blobs()
                GitHelper.run_mergetool(cls.old_repo)
                if cls.old_repo.index.unmerged_blobs():
                    if InputHelper.get_message('There are still unmerged entries. Do you want to skip this patch',
                                               default_yes=False):
                        inapplicable = True
                    else:
                        continue
                if not inapplicable:
                    # check for unresolved conflicts
                    unresolved = []
                    for file in unmerged:
                        try:
                            with open(os.path.join(cls.old_sources, file), 'rb') as f:
                                if [l for l in f if b'<<<<<<<' in l]:
                                    unresolved.append(file)
                        except FileNotFoundError:
                            # skip deleted files
                            continue
                    if unresolved:
                        if InputHelper.get_message('There are still unresolved conflicts. '
                                                   'Do you want to skip this patch',
                                                   default_yes=False):
                            inapplicable = True
                        else:
                            cls.old_repo.index.reset(paths=unresolved)
                            unresolved.insert(0, '--')
                            cls.old_repo.git.checkout(*unresolved, conflict='diff3')
                            continue
            if inapplicable:
                inapplicable_patches.append(patch_name)
                try:
                    cls.output_data = cls.old_repo.git.rebase(skip=True, stdout_as_string=True)
                except git.GitCommandError as e:
                    ret_code = e.status
                    cls.output_data = e.stdout
                    continue
                else:
                    break
            diff = cls.old_repo.index.diff(cls.old_repo.commit())
            if diff:
                modified_patches.append(patch_name)
            if next_index < last_index:
                if not InputHelper.get_message('Do you want to continue with another patch'):
                    raise KeyboardInterrupt
            try:
                if diff:
                    cls.output_data = cls.old_repo.git.rebase('--continue', stdout_as_string=True)
                else:
                    cls.output_data = cls.old_repo.git.rebase(skip=True, stdout_as_string=True)
            except git.GitCommandError as e:
                ret_code = e.status
                cls.output_data = e.stdout
            else:
                break
        original_commits = list(cls.old_repo.iter_commits(rev=cls.old_repo.branches.master))
        commits = list(cls.old_repo.iter_commits())
        untouched_patches = []
        deleted_patches = []
        for patch in cls.patches:
            patch_name = patch.get_patch_name()
            original_commit = [c for c in original_commits if cls.extract_patch_name(c.message) == patch_name]
            commit = [c for c in commits if cls.extract_patch_name(c.message) == patch_name]
            if original_commit and commit:
                if patch_name not in modified_patches and compare_commits(original_commit[0], commit[0]):
                    untouched_patches.append(patch_name)
                else:
                    base_name = os.path.join(cls.kwargs['rebased_sources_dir'], patch_name)
                    if commit[0].summary == cls.decorate_patch_name(patch_name):
                        diff = cls.old_repo.git.diff(commit[0].parents[0], commit[0], stdout_as_string=False)
                    else:
                        diff = cls.old_repo.git.format_patch(commit[0], '-1',
                                                             stdout=True, no_numbered=True,
                                                             no_attach=True, stdout_as_string=False)
                        diff = cls.strip_patch_name(diff, patch_name)
                    with open(base_name, 'wb') as f:
                        f.write(diff)
                        f.write(b'\n')
                    if patch_name not in modified_patches:
                        modified_patches.append(patch_name)
            elif patch_name not in inapplicable_patches:
                deleted_patches.append(patch_name)
        if deleted_patches:
            patch_dictionary['deleted'] = deleted_patches
        if modified_patches:
            patch_dictionary['modified'] = modified_patches
        if inapplicable_patches:
            patch_dictionary['inapplicable'] = inapplicable_patches
        if untouched_patches:
            patch_dictionary['untouched'] = untouched_patches
        return patch_dictionary

    @classmethod
    def apply_old_patches(cls, source_dir):
        """Function applies a patch to a old/new sources"""
        for patch in cls.patches:
            logger.info("Applying patch '%s' to '%s'",
                        patch.get_patch_name(),
                        os.path.basename(source_dir))
            try:
                cls.apply_patch(cls.old_repo, patch)
            except git.GitCommandError as e:
                raise RuntimeError('Failed to patch old sources') from e
        # update repository state
        cls.old_repo.git.config('rebasehelper.state', 'PATCHES', local=True)

    @classmethod
    def init_git(cls, directory):
        """Function initialize old and new Git repository"""
        try:
            repo = git.Repo(directory)
            try:
                state = repo.git.config('rebasehelper.state', get=True, local=True)
            except git.GitCommandError:
                del repo
                # repository not created by us, remove the metadata
                shutil.rmtree(os.path.join(directory, '.git'))
            else:
                return repo, state
        except git.InvalidGitRepositoryError:
            pass
        repo = git.Repo.init(directory)
        state = 'INIT'
        repo.git.config('rebasehelper.state', state, local=True)
        repo.git.config('user.name', GitHelper.get_user(), local=True)
        repo.git.config('user.email', GitHelper.get_email(), local=True)
        # prevent git commands from launching an interactive editor
        repo.git.config('core.editor', 'true', local=True)
        repo.git.add(all=True)
        repo.index.commit('Initial commit', skip_hooks=True)
        return repo, state

    @classmethod
    def patch(cls, old_dir, new_dir, rest_sources, patches, **kwargs):
        """
        The function can be used for patching one
        directory against another
        """
        cls.kwargs = kwargs
        cls.old_sources = old_dir
        cls.new_sources = new_dir
        cls.output_data = None
        cls.rest_sources = rest_sources
        cls.patches = patches
        cls.non_interactive = kwargs.get('non_interactive')
        cls.favor_on_conflict = kwargs.get('favor_on_conflict')
        cls.old_repo, old_repo_state = cls.init_git(old_dir)
        if old_repo_state == 'INIT':
            cls.apply_old_patches(old_dir)
        cls.new_repo, _ = cls.init_git(new_dir)
        return cls._git_rebase()
