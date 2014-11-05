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
import sys
import six
import random
import string
from six import StringIO

from rebasehelper import settings
from rebasehelper.logger import logger
from rebasehelper.utils import check_empty_patch, get_message
from rebasehelper.utils import ProcessHelper
from rebasehelper.specfile import get_rebase_name
from rebasehelper.diff_helper import Differ


patch_tools = {}


def get_patch_name(name):
    """
    Function returns a patch name with suffix
    :param name:
    :return: patch name with suffix
    """
    name, extension = os.path.splitext(name)
    return name + settings.REBASE_HELPER_SUFFIX + extension


def get_path_to_patch(patch):
    return os.path.join('..', '..', patch)


def register_patch_tool(patch_tool):
    patch_tools[patch_tool.CMD] = patch_tool
    return patch_tool


class PatchBase(object):
    """ Class used for using several patching command tools, ...
        Each method should overwrite method like run_check
    """

    helpers = {}

    @classmethod
    def match(cls, cmd):
        """
            Method checks whether it is usefull patch method
        """
        return NotImplementedError()

    @classmethod
    def run_patch(cls, *args, **kwargs):
        """
            Method will check all patches in relevant package
        """
        return NotImplementedError()


@register_patch_tool
class PatchTool(PatchBase):
    """
    Class for patch command used for patching old and new
    sources
    """
    CMD = 'patch'
    suffix = None
    fuzz = 0
    source_dir = ""
    old_sources = ""
    new_sources = ""
    diff_cls = None
    output_data = []

    @classmethod
    def match(cls, cmd):
        if cls.CMD == cmd:
            return True
        else:
            return False

    @classmethod
    def patch_command(cls, patch_name, patch_flags):
        """
        Patch command whom patches as the
        """
        logger.debug('PatchTool: Applying patch')

        cmd = [cls.CMD]
        cmd.append(patch_flags)
        if cls.suffix:
            cmd.append('-b')
            cmd.append('--suffix=.' + cls.suffix)
        cmd.append('--fuzz={0}'.format(cls.fuzz))
        cmd.append('--force')  # don't ask questions

        output = StringIO()
        ret_code = ProcessHelper.run_subprocess_cwd(cmd=cmd,
                                                    cwd=cls.source_dir,
                                                    input=patch_name,
                                                    output=output)
        cls.output_data = output.readlines()
        return ret_code

    @classmethod
    def get_failed_patched_files(cls, patch_name):
        """
        Function gets a lists of patched files from patch command.
        """
        cmd = ['lsdiff', patch_name]
        output = StringIO()
        ret_code = ProcessHelper.run_subprocess_cwd(cmd=cmd,
                                                    cwd=cls.source_dir,
                                                    output=output)
        if ret_code != 0:
            return None
        cls.patched_files = output.readlines()
        failed_files = []
        applied_rules = ['succeeded']
        source_file = ""
        for data in cls.output_data:
            # First we try to find what file is patched
            if data.startswith('patching file'):
                patch, file_text, source_file = data.strip().split()
                continue
            # Next we look whether patching was successful
            result = [x for x in applied_rules if x in data]
            if result:
                continue
            # file_list = [x for x in cls.patched_files if source_file in x]
            if source_file in failed_files:
                continue
            failed_files.append(source_file)
        return failed_files

    @classmethod
    def generate_diff(cls, patch, patch_path_argumennt):
        """
        Path to the patch that should be generated

        :param patch: name of the patch to be generated
        :param patch_path_argumennt: patch command argument specifying which part of path in patch should be stripped
        :return: return code of the gendiff command
        """
        # gendiff new_source + self.suffix > patch[0]
        logger.debug("PatchTool: Generating patch using gendiff")
        cmd = ['gendiff']
        # strip '-p' from the path argument to determine the path
        if int(patch_path_argumennt.strip('-p')) == 0:
            cmd.append('.')
            cwd = cls.new_sources
        else:
            cmd.append(os.path.basename(cls.new_sources))
            cwd = os.path.join(os.getcwd(), settings.NEW_SOURCES_DIR)
        cmd.append('.' + cls.suffix)

        return ProcessHelper.run_subprocess_cwd(cmd=cmd,
                                                cwd=cwd,
                                                output=patch)

    @classmethod
    def execute_diff_helper(cls, patch):
        """
        Function rebases a patch with help of diff program
        on new upstream version
        :param patch: Patch name
        :return:
        """
        rebased_patch = get_rebase_name(patch[0])
        patched_files = cls.get_failed_patched_files(patch[0])
        if not patched_files:
            raise RuntimeError('We are not able to get a list of failed files.')

        logger.debug('Input to MergeTool: {0}'.format(cls.kwargs))
        diff_cls = Differ(cls.kwargs.get('diff_tool', None))
        # Running Merge Tool
        diff_cls.merge(cls.old_sources, cls.new_sources, cls.suffix, patched_files)

        # Generating diff
        cls.generate_diff(rebased_patch, patch[1])

        # Showing difference between original and new patch
        diff_cls.diff(patch[0], rebased_patch)
        return rebased_patch

    @classmethod
    def get_rebased_patch_from_kwargs(cls, patch):
        """
        Function finds patch in already rebases patches
        :param patch:
        :return:
        """
        # Check if patch is in rebased patches
        found = False
        for value in six.itervalues(cls.rebased_patches):
            if os.path.basename(patch) in value[0]:
                return value[0]
        if not found:
            return None

    @classmethod
    def check_already_applied_patch(cls, patch):
        """
        Function checks if patch was already rebased
        :param patch:
        :return: - None if patch is empty
                 - Patch
        """
        rebased_patch_name = cls.get_rebased_patch_from_kwargs(patch)
        # If patch is not rebased yet
        if not rebased_patch_name:
            return patch
        # Check if patch is empty
        if check_empty_patch(rebased_patch_name):
            # If patch is empty then it isn't applied
            # and is removed
            return None
        # Return non empty rebased patch
        return rebased_patch_name

    @classmethod
    def apply_patch(cls, patch):
        """
        Function applies a patch to a old/new sources
        """
        if cls.source_dir == cls.old_sources:
            # for new_sources we want the same suffix as for old_sources
            cls.suffix = ''.join(random.choice(string.ascii_letters) for _ in range(6))
        else:
            # This check is applied only in case of new_sources
            # If rebase-helper is called with --continue option
            if cls.kwargs.get('continue', False):
                applied = cls.check_already_applied_patch(patch[0])
                if not applied:
                    patch[0] = cls.get_rebased_patch_from_kwargs(patch[0])
                    return patch
                patch[0] = applied

        logger.info("Applying patch '{0}' to '{1}'".format(os.path.basename(patch[0]),
                                                           os.path.basename(cls.source_dir)))
        ret_code = cls.patch_command(get_path_to_patch(patch[0]), patch[1])
        if ret_code != 0:
            # unexpected
            if cls.source_dir == cls.old_sources:
                raise RuntimeError('Failed to patch old sources')

            get_message("Applying patch {0} to new source failed. Press Enter to start merge-tool.".
                        format(os.path.basename(patch[0])),
                        any_input=True)
            logger.warning('Applying patch failed. '
                           'Starting merge-tool to fix conflicts manually.')
            # Running diff_helper in order to merge patch to the upstream version
            patch[0] = cls.execute_diff_helper(patch)

            # User should clarify whether another patch will be applied
            accept = ['y', 'yes']
            var = get_message(message="Do you want to continue with another patch? (y/n)")
            if var not in accept:
                sys.exit(0)

        return patch

    @classmethod
    def run_patch(cls, old_dir, new_dir, patches, rebased_patches, **kwargs):
        """
        The function can be used for patching one
        directory against another
        """
        cls.kwargs = kwargs
        cls.patches = patches
        if rebased_patches:
            cls.rebased_patches = rebased_patches
        else:
            cls.rebased_patches = patches
        cls.old_sources = old_dir
        cls.new_sources = new_dir
        cls.output_data = []
        cls.patched_files = []

        # apply patches in the same order as in spec file, not according to their numbers
        for order in sorted(cls.patches.items(), key=lambda x: x[1][2]):
            try:
                cls.source_dir = cls.old_sources
                cls.apply_patch(cls.patches[order[0]])
                cls.source_dir = cls.new_sources
                patch = cls.apply_patch(cls.rebased_patches[order[0]])
            except Exception:
                raise Exception
            cls.patches[order[0]] = patch

        return cls.patches


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
        self._path_tool_name = tool
        self._tool = None

        for patch_tool in patch_tools.values():
            if patch_tool.match(self._path_tool_name):
                self._tool = patch_tool

        if self._tool is None:
            raise NotImplementedError("Unsupported patch tool")

    def patch(self, old_dir, new_dir, patches, rebased_patches, **kwargs):
        """
        Apply patches and generate rebased patches if needed

        :param old_dir: path to dir with old patches
        :param new_dir: path to dir with new patches
        :param patches: old patches
        :param rebased_patches: rebased patches
        :param kwargs: --
        :return:
        """
        logger.debug("Patcher: Patching source by patch tool {0}".format(self._path_tool_name))
        return self._tool.run_patch(old_dir, new_dir, patches, rebased_patches, **kwargs)




