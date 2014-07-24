# -*- coding: utf-8 -*-

# This tool helps you to rebase package to the latest version
# Copyright (C) 2013 Petr Hracek
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

import os
import sys
import random
import string


from rebasehelper import settings
from rebasehelper.logger import logger
from rebasehelper.utils import get_temporary_name, remove_temporary_name, get_content_file
from rebasehelper.utils import check_empty_patch, get_message
from rebasehelper.utils import ProcessHelper
from rebasehelper.specfile import get_rebase_name
from rebasehelper.diff_helper import Diff


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
    def match(cls, *args, **kwargs):
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
    def run_process(cls, cmd, cwd=None, input_name=None, output_name=None):
        temp_name = output_name
        if not output_name:
            temp_name = get_temporary_name()
        ret_code = ProcessHelper.run_subprocess_cwd(cmd, cwd=cwd, input=input_name, output=temp_name)
        output_data = get_content_file(temp_name, 'r', method=True)
        if not output_name:
            remove_temporary_name(temp_name)
        return ret_code, output_data

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

        ret_code, cls.output_data = cls.run_process(cmd, cwd=cls.source_dir, input_name=patch_name)
        return ret_code

    @classmethod
    def get_failed_patched_files(cls, patch_name):
        """
        Function gets a lists of patched files from patch command.
        """
        cmd = ['lsdiff', patch_name]
        ret_code, cls.patched_files = cls.run_process(cmd, cwd=cls.source_dir)
        if ret_code != 0:
            return None
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
            file_list = [x for x in cls.patched_files if source_file in x]
            if source_file in failed_files:
                continue
            failed_files.append(source_file)
        return failed_files

    @classmethod
    def generate_diff(cls, patch, source_dir):
        # gendiff new_source + self.suffix > patch[0]
        logger.debug("PatchTool: Generating patch using gendiff")
        cmd = ['gendiff']
        cmd.append(os.path.basename(cls.new_sources))
        cmd.append('.' + cls.suffix)

        ret_code, gendiff_output = cls.run_process(cmd,
                                                   cwd=os.path.join(os.getcwd(), settings.NEW_SOURCES_DIR),
                                                   output_name=patch)
        return ret_code

    @classmethod
    def execute_diff_helper(cls, patch):
        rebased_patch = get_rebase_name(patch[0])
        patched_files = cls.get_failed_patched_files(patch[0])
        if not patched_files:
            raise RuntimeError('We are not able to get a list of failed files.')

        cls.kwargs['suffix'] = cls.suffix
        cls.kwargs['failed_files'] = patched_files

        logger.debug('Input to MergeTool: {0}'.format(cls.kwargs))
        diff_cls = Diff(cls.kwargs.get('diff_tool', None))
        # Running Merge Tool
        ret_code = diff_cls.mergetool(**cls.kwargs)

        # Generating diff
        cls.generate_diff(rebased_patch, cls.source_dir)

        # Showing difference between original and new patch
        diff_cls.diff(patch[0], rebased_patch)
        return rebased_patch

    @classmethod
    def get_rebased_patch_from_kwargs(cls, patch):
        # Check if patch is in rebased patches
        patches = [x for x in cls.kwargs['new']['patches'] if os.path.basename(patch) in x]
        if not patches:
            return None
        return patches[0]

    @classmethod
    def check_already_applied_patch(cls, patch):
        """
        Function checks if patch was already rebased
        :param patch:
        :return: - None if patch is empty
                 - Patch
        """
        rebased_patches = cls.get_rebased_patch_from_kwargs(patch)
        # If patch is not rebased yet
        if not rebased_patches:
            return patch
        # Check if patch is empty
        if check_empty_patch(rebased_patches):
            # If patch is empty then it isn't applied
            # and is removed
            return None
        # Return non empty rebased patch
        return rebased_patches

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
                        any=True)
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
    def run_patch(cls, **kwargs):
        """
        The function can be used for patching one
        directory against another
        """
        cls.kwargs = kwargs
        cls.patches = kwargs['new'].get(settings.FULL_PATCHES, None)
        cls.old_sources = kwargs.get('old_dir', None)
        cls.new_sources = kwargs.get('new_dir', None)
        cls.output_data = []
        cls.patched_files = []
        # apply patches in the same order as in spec file, not according to their numbers
        for order in sorted(cls.patches.items(), key=lambda x: x[1][2]):
            try:
                cls.source_dir = cls.old_sources
                cls.apply_patch(cls.patches[order[0]])
                cls.source_dir = cls.new_sources
                patch = cls.apply_patch(cls.patches[order[0]])
            except Exception:
                raise Exception
            cls.patches[order[0]] = patch

        return cls.patches


class Patch(object):
    def __init__(self, patch=None):
        if patch is None:
            raise TypeError("Expected argument 'tool' (pos 1) is missing")
        self._path_tool_name = patch
        self._tool = None

        for patch_tool in patch_tools.values():
            if patch_tool.match(self._path_tool_name):
                self._tool = patch_tool

        if self._tool is None:
            raise NotImplementedError("Unsupported patch tool")

    def patch(self, **kwargs):
        logger.debug("Patch: Patching source by patch tool {0}".format(self._path_tool_name))
        return self._tool.run_patch(**kwargs)




