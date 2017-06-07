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
from rebasehelper.logger import logger
from rebasehelper.utils import ConsoleHelper
from rebasehelper.utils import ProcessHelper
from rebasehelper.utils import GitHelper, GitRebaseError

#from git import Repo
#import git

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
    def match(cls, cmd=None, *args, **kwargs):
        """Method checks whether it is usefull patch method"""
        return NotImplementedError()

    @classmethod
    def run_patch(cls, old_dir, new_dir, rest_sources, git_helper, patches, *args, **kwargs):
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
    output_data = []
    old_repo = None
    new_repo = None
    git_helper = None
    non_interactive = False
    patches = None
    prep_section = False
    exec_prep_script = False
    patch_sources_by_prep_script = False

    @classmethod
    def match(cls, cmd=None):
        if cmd is not None and cmd == cls.CMD:
            return True
        else:
            return False

    @staticmethod
    def apply_patch(git_helper, patch_object):
        """
        Function applies patches to old sources
        It tries apply patch with am command and if it fails
        then with command --apply
        """
        logger.debug('Applying patch with am')

        patch_name = patch_object.get_path()
        patch_option = patch_object.get_option()
        ret_code = git_helper.command_am(input_file=patch_name)
        if int(ret_code) != 0:
            git_helper.command_am(parameters='--abort', input_file=patch_name)
            logger.debug('Applying patch with git am failed.')
            ret_code = git_helper.command_apply(input_file=patch_name, option=patch_option)
            if int(ret_code) != 0:
                ret_code = git_helper.command_apply(input_file=patch_name, option=patch_option, ignore_space=True)
            ret_code = GitPatchTool.commit_patch(git_helper, patch_name)
        else:
            # replace last commit message with patch name to preserve mapping between commits and patches
            ret_code = git_helper.command_commit(message='Patch: {0}'.format(os.path.basename(patch_name)), amend=True)
        return ret_code

    @classmethod
    def _prepare_git(cls, upstream_name):
        cls.git_helper.command_remote_add(upstream_name, cls.new_sources)
        cls.git_helper.command_fetch(upstream_name)
        cls.output_data = cls.git_helper.command_log(parameters='--pretty=oneline')
        logger.debug('Outputdata from git log %s', cls.output_data)
        number = 0
        if cls.prep_section:
            number = 1
        last_hash = GitHelper.get_commit_hash_log(cls.output_data, number=number)
        init_hash = GitHelper.get_commit_hash_log(cls.output_data, len(cls.output_data)-1)
        return init_hash, last_hash

    @classmethod
    def _get_git_helper_data(cls):
        cls.output_data = cls.git_helper.get_output_data()

    @classmethod
    def _update_deleted_patches(cls, deleted_patches, unapplied_patches):
        """Function checks patches against rebase-patches"""
        cls.output_data = cls.git_helper.command_log(parameters='--pretty=oneline')
        updated_patches = []
        for patch in cls.patches:
            patch_name = patch.get_patch_name()
            if (not [x for x in cls.output_data if patch_name in x] and
                    patch_name not in deleted_patches and
                    patch_name not in unapplied_patches):
                updated_patches.append(patch_name)
        return updated_patches

    @classmethod
    def _git_rebase(cls):
        """Function performs git rebase between old and new sources"""
        # in old_sources do.
        # 1) git remote add new_sources <path_to_new_sources>
        # 2) git fetch new_sources
        # 3 git rebase -i --onto new_sources/master <oldest_commit_old_source> <the_latest_commit_old_sourcese>
        if not cls.cont:
            logger.info('Git-rebase operation to %s is ongoing...', os.path.basename(cls.new_sources))
            upstream = 'new_upstream'
            init_hash, last_hash = cls._prepare_git(upstream)
            ret_code = cls.git_helper.command_rebase(parameters='--onto', upstream_name=upstream,
                                                     first_hash=init_hash, last_hash=last_hash)
        else:
            logger.info('Git-rebase operation continues...')
            ret_code = cls.git_helper.command_rebase(parameters='--skip')
        cls._get_git_helper_data()
        logger.debug(cls.output_data)
        patch_dictionary = {}
        modified_patches = []
        deleted_patches = []
        unapplied_patches = []
        while True:
            log = cls.git_helper.command_log(parameters='--pretty=oneline')
            for patch_name in cls.git_helper.get_automerged_patches(cls.output_data):
                index = [i for i, l in enumerate(log) if l.endswith(patch_name)]
                if index:
                    commit = GitHelper.get_commit_hash_log(log, number=index[0])
                    base_name = os.path.join(cls.kwargs['rebased_sources_dir'], patch_name)
                    cls.git_helper.command_diff('{}~1'.format(commit), commit, output_file=base_name)
                    modified_patches.append(base_name)
            if int(ret_code) != 0:
                if not cls.non_interactive:
                    patch_name = cls.git_helper.get_unapplied_patch(cls.output_data)
                    logger.info("Git has problems with rebasing patch %s", patch_name)
                    cls.git_helper.command_mergetool()
                else:
                    # Take the patch which failed from .git/rebase-apply/next file
                    try:
                        with open(os.path.join(cls.old_sources, '.git', 'rebase-apply', 'next')) as f:
                            number = '\n'.join(f.readlines())
                    except IOError:
                        raise RuntimeError("Git rebase failed with unknown reason. Please check log file")
                    # Getting the patch which failed
                    unapplied_patches.append(cls.patches[int(number) - 1].get_patch_name())
                    ret_code = cls.git_helper.command_rebase('--skip')
                    cls._get_git_helper_data()
                    continue
                modified_files = cls.git_helper.command_diff_status()
                cls.git_helper.command_add_files(parameters=modified_files)
                base_name = os.path.join(cls.kwargs['rebased_sources_dir'], patch_name)
                cls.git_helper.command_diff('HEAD', output_file=base_name)
                with open(base_name, "r") as f:
                    del_patches = f.readlines()
                if not del_patches:
                    deleted_patches.append(base_name)
                else:
                    logger.info('Following files were modified: %s', ','.join(modified_files))
                    cls.git_helper.command_commit(message=patch_name)
                    cls.git_helper.command_diff('HEAD~1', output_file=base_name)
                    modified_patches.append(base_name)
                if not cls.non_interactive:
                    if not ConsoleHelper.get_message('Do you want to continue with another patch'):
                        raise KeyboardInterrupt
                ret_code = cls.git_helper.command_rebase('--skip')
                cls._get_git_helper_data()
            else:
                break
        deleted_patches = cls._update_deleted_patches(deleted_patches,
                                                      unapplied_patches)
        if deleted_patches:
            patch_dictionary['deleted'] = deleted_patches
        if modified_patches:
            patch_dictionary['modified'] = modified_patches
        if unapplied_patches:
            patch_dictionary['unapplied'] = unapplied_patches
        #TODO correct settings for merge tool in ~/.gitconfig
        # currently now meld is not started
        return patch_dictionary

    @staticmethod
    def commit_patch(git_helper, patch_name):
        """Function commits patched files to git"""
        logger.debug('Commit patch')
        ret_code = git_helper.command_add_files(parameters=['--all'])
        if int(ret_code) != 0:
            raise GitRebaseError('We are not able to add changed files to local git repository.')
        ret_code = git_helper.command_commit(message='Patch: {0}'.format(os.path.basename(patch_name)))
        return ret_code

    @classmethod
    def apply_old_patches(cls):
        """Function applies a patch to a old/new sources"""
        for patch in cls.patches:
            logger.info("Applying patch '%s' to '%s'",
                        os.path.basename(patch.get_path()),
                        os.path.basename(cls.source_dir))
            ret_code = GitPatchTool.apply_patch(cls.git_helper, patch)
            # unexpected
            if int(ret_code) != 0:
                if cls.source_dir == cls.old_sources:
                    raise RuntimeError('Failed to patch old sources')

    @classmethod
    def _prepare_prep_script(cls, sources, prep):
        for src in sources:
            file_name = os.path.join('SOURCES', os.path.basename(src))
            for index, row in enumerate(prep):
                if file_name in row:
                    src_path = [x for x in row.split() if x.endswith(file_name)]
                    prep[index] = row.replace(src_path[0], src)

        return prep

    @classmethod
    def create_prep_script(cls, prep):
        """Function abstract special things from prep section and apply them to old sources"""
        logger.debug('Extract prep script')
        # Check whether patch or git am is used inside %prep section
        # If yes then execute whole %prep section
        logger.debug("prep section '%s'", prep)
        found_patching = [x for x in prep if ' patch ' in x]
        if found_patching:
            cls.exec_prep_script = True
        found_git_am = [x for x in prep if 'git am' in x]
        if found_git_am:
            cls.patch_sources_by_prep_script = True

        logger.debug('Fix %SOURCES tags in prep script')
        prep = cls._prepare_prep_script(cls.rest_sources, prep)
        logger.debug('Fix %PATCH tags in prep script')
        prep = cls._prepare_prep_script([x.get_path() for x in cls.patches], prep)
        prep_script_path = os.path.join(cls.kwargs['workspace_dir'], 'prep_script')
        logger.debug("Writing Prep script '%s' to the disc", prep_script_path)
        try:
            with open(prep_script_path, "w") as f:
                f.write("#!/bin/bash\n\n")
                f.writelines('\n'.join(prep))
            os.chmod(prep_script_path, 0o755)
        except IOError:
            logger.debug("Unable to write prep script file to '%s'", prep_script_path)
            return None

        return prep_script_path

    @classmethod
    def call_prep_script(cls, prep_script_path):
        cwd = os.getcwd()
        os.chdir(cls.old_sources)
        ProcessHelper.run_subprocess(prep_script_path,
                                     output=os.path.join(cls.kwargs['workspace_dir'], 'prep_script.log'))
        if not cls.patch_sources_by_prep_script:
            cls.git_helper.command_add_files(parameters=["--all"])
            cls.git_helper.command_commit(message="prep_script prep_corrections")
        os.chdir(cwd)

    @classmethod
    def init_git(cls, directory):
        """Function initialize old and new Git repository"""
        gh = GitHelper(directory)
        gh.command_init(directory)
        gh.command_add_files('.')
        gh.command_commit(message='Initial Commit')

    @classmethod
    def run_patch(cls, old_dir, new_dir, rest_sources, git_helper, patches, prep, **kwargs):
        """
        The function can be used for patching one
        directory against another
        """
        cls.kwargs = kwargs
        cls.old_sources = old_dir
        cls.new_sources = new_dir
        cls.output_data = []
        cls.cont = cls.kwargs['continue']
        cls.rest_sources = rest_sources
        cls.git_helper = git_helper
        cls.patches = patches
        cls.non_interactive = kwargs.get('non_interactive')
        if not os.path.isdir(os.path.join(cls.old_sources, '.git')):
            cls.init_git(old_dir)
            cls.init_git(new_dir)
            cls.source_dir = cls.old_sources
            prep_path = cls.create_prep_script(prep)
            if not cls.patch_sources_by_prep_script:
                cls.apply_old_patches()
            if cls.exec_prep_script or cls.patch_sources_by_prep_script:
                logger.info('Executing prep script')
                cls.call_prep_script(prep_path)
            cls.cont = False

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

    def patch(self, old_dir, new_dir, rest_sources, git_helper, patches, prep, **kwargs):
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
        return self._tool.run_patch(old_dir, new_dir, rest_sources, git_helper, patches, prep, **kwargs)




