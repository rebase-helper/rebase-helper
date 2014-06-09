# -*- coding: utf-8 -*-

import os
import sys

from rebasehelper.logger import logger
from rebasehelper.utils import get_message
from rebasehelper.utils import ProcessHelper

diff_tools = {}
def register_diff_tool(diff_tool):
    diff_tools[diff_tool.CMD] = diff_tool
    return diff_tool


class DiffBase(object):
    """ Class used for testing and other future stuff, ...
        Each method should overwrite method like run_check
    """
    @classmethod
    def match(cls, *args, **kwargs):
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

@register_diff_tool
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
        pass

    @classmethod
    def run_mergetool(cls, **kwargs):
        pass

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
        if not old:
            raise TypeError("MeldDiffTool:run_diff: missing old")
        if not new:
            raise TypeError("MeldDiffTool:run_diff: missing new")

        cmd = [cls.CMD, '--diff', old, new]
        logger.debug("MeldDiffTool:run_diff: running '" + str(cmd) + "'")
        ret_code = ProcessHelper.run_subprocess_cwd(' '.join(cmd), output=None, shell=True)
        print "ret_code:", ret_code

    @classmethod
    def run_mergetool(cls, **kwargs):
        old_dir = kwargs.get('old_dir')
        new_dir = kwargs.get('new_dir')
        suffix = kwargs.get('suffix')
        failed_files = kwargs.get('failed_files')

        if old_dir == None:
            raise TypeError("MeldDiffTool:run_mergetool: missing old_dir")
        if new_dir == None:
            raise TypeError("MeldDiffTool:run_mergetool: missing new_dir")
        if suffix == None:
            raise TypeError("MeldDiffTool:run_mergetool: missing suffix")
        else:
            suffix = "." + suffix
        if not failed_files:
            raise TypeError("MeldDiffTool:run_mergetool: missing failed_files")

        for index, fname in enumerate(failed_files):
            base =   os.path.join(old_dir, fname + suffix)
            remote = os.path.join(old_dir, fname)
            local =  os.path.join(new_dir, fname + suffix)
            merged = os.path.join(new_dir, fname)

            # http://stackoverflow.com/questions/11133290/git-merging-using-meld
            cmd = [cls.CMD, '--diff', base, local, '--diff', base, remote, '--auto-merge', local, base, remote, '--output', merged]
            logger.debug("MeldDiffTool:run_mergetool: running '" + str(cmd) + "'")
            ret_code = ProcessHelper.run_subprocess_cwd(' '.join(cmd), output=None, shell=True)

            if len(failed_files) > 1 and index < len(failed_files) - 1:
                accept = ['y', 'yes']
                var = get_message(message="Do you want to merge another file? (y/n)")
                if var not in accept:
                    sys.exit(0)


class Diff(object):
    """
    Class represents a processes for differences between sources
    """
    @classmethod
    def __init__(cls, diff=None):
        if diff is None:
            raise TypeError("Expected argument 'diff' is missing.")
        cls._diff_name = diff
        cls._diff = None

        for diff_tool in diff_tools.values():
            if diff_tool.match(cls._diff_name):
                cls._tool = diff_tool

        if cls._tool is None:
            raise NotImplementedError("Unsupported diff tool")

    @classmethod
    def diff(cls, old, new):
        """
        Diff between two files
        """
        logger.debug("Diff: Diff between files {0} and {1}".format(old, new))
        return cls._tool.run_diff(old, new)

    @classmethod
    def mergetool(cls, **kwargs):
        """
        Tool for resolving merge conflicts
        """
        logger.debug("Diff: mergetool..")
        return cls._tool.run_mergetool(**kwargs)

if __name__ == '__main__':
    kwargs = {}
    diff = Diff('meld')
    diff.diff(**kwargs)
