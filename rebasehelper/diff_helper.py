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
from six import StringIO

from rebasehelper.logger import logger
from rebasehelper.utils import ConsoleHelper
from rebasehelper.utils import ProcessHelper
from rebasehelper import settings
from rebasehelper.utils import GitHelper

diff_tools = {}


def register_diff_tool(diff_tool):
    diff_tools[diff_tool.CMD] = diff_tool
    return diff_tool


class GenericDiff(object):
    """
    Class used a generic function for patch generation
    """

    @staticmethod
    def generate_diff(new_sources, suffix, patch, patch_path_argument):
        """
        Path to the patch that should be generated

        :param patch: name of the patch to be generated
        :param patch_path_argument: patch command argument specifying which part of path in patch should be stripped
        :return: return code of the gendiff command
        """
        # gendiff new_source + self.suffix > patch[0]
        logger.debug("Generating patch using gendiff")
        cmd = ['gendiff']
        # strip '-p' from the path argument to determine the path
        if int(patch_path_argument.strip('-p')) == 0:
            cmd.append('.')
            cwd = new_sources
        else:
            cmd.append(os.path.basename(new_sources))
            cwd = os.path.join(os.getcwd(), settings.NEW_SOURCES_DIR)
        cmd.append('.' + suffix)

        return ProcessHelper.run_subprocess_cwd(cmd=cmd,
                                                cwd=cwd,
                                                output=patch)

    @staticmethod
    def check_empty_patch(patch_name):
        """
        Function checks whether patch is empty or not
        """
        cmd = ["lsdiff"]
        cmd.append(patch_name)
        output = StringIO()
        ret_code = ProcessHelper.run_subprocess(cmd, output=output)
        if ret_code == 0 and not output.readlines():
            return True
        else:
            return False


class DiffBase(object):
    """ Class used for testing and other future stuff, ...
        Each method should overwrite method like run_check
    """
    @classmethod
    def match(cls, cmd):
        """
        Checks if diff name matches
        """
        raise NotImplementedError()

    @classmethod
    def run_diff(self, old, new):
        """
            Method for showing difference between two files
        """
        return NotImplementedError()

    @classmethod
    def run_mergetool(self, **kwargs):
        """
            Start a tool for resolving merge conflicts
        """
        return NotImplementedError()


#@register_diff_tool
class VimDiffTool(DiffBase):
    """
    The class is used for diff between two directories or sources
    """
    CMD = 'vimdiff'


    @classmethod
    def match(cls, diff=None):
        if diff == cls.CMD:
            return True
        else:
            return False

    @classmethod
    def run_diff(cls, **kwargs):
        raise NotImplementedError()

    @classmethod
    def run_mergetool(cls, **kwargs):
        raise NotImplementedError()


@register_diff_tool
class MeldDiffTool(DiffBase):
    """
    The class is used for diff between two directory sources
    """
    CMD = 'meld'
    @classmethod
    def match(cls, diff=None):
        if diff == cls.CMD:
            return True
        else:
            return False

    @classmethod
    def run_diff(cls, old, new):
        logger.debug("running diff")

        cmd = [cls.CMD, '--diff', old, new]
        return ProcessHelper.run_subprocess(cmd, output=ProcessHelper.DEV_NULL)

    @classmethod
    def run_mergetool(cls, old_dir, new_dir, failed_files):

        logger.debug("running merge")

        for index, fname in enumerate(failed_files):
            base = os.path.join(old_dir, fname)  # old w/o patch
            remote = os.path.join(old_dir, fname)  # new with patch
            local = os.path.join(new_dir, fname)  # new w/o patch
            merged = os.path.join(new_dir, fname)

            # http://stackoverflow.com/questions/11133290/git-merging-using-meld
            cmd = [cls.CMD, '--diff', base, local, '--diff', base, remote, '--auto-merge', local, base, remote, '--output', merged]

            ProcessHelper.run_subprocess(cmd, output=ProcessHelper.DEV_NULL)

            if len(failed_files) > 1 and index < len(failed_files) - 1:
                if not ConsoleHelper.get_message('Do you want to merge another file'):
                    raise KeyboardInterrupt


class Differ(object):
    """
    Class represents a processes for differences between sources
    """

    def __init__(self, tool=None):
        if tool is None:
            raise TypeError("Expected argument 'tool' is missing.")
        self._tool_name = tool
        self._tool = None

        for diff_tool in diff_tools.values():
            if diff_tool.match(self._tool_name):
                self._tool = diff_tool

        if self._tool is None:
            raise NotImplementedError("Unsupported diff tool")

    def __str__(self):
        return "<Differ tool_name='{_tool_name}' tool='{_tool}'>".format(**vars(self))

    def diff(self, old, new):
        """
        Diff between two files
        """
        logger.debug("Diff between files {0} and {1}".format(old, new))
        return self._tool.run_diff(old, new)

    def merge(self, old_dir, new_dir, failed_files):
        """
        Tool for resolving merge conflicts
        """
        self._tool.run_mergetool(old_dir, new_dir, failed_files)

    @staticmethod
    def get_supported_tools():
        """
        Returns a list of supported diff tools

        :return: list of supported diff tools
        """
        return diff_tools.keys()
