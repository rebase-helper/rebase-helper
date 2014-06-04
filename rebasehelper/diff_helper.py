# -*- coding: utf-8 -*-

import os
import sys

from rebasehelper.logger import logger
from rebasehelper.utils import PathHelper
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
    def run_diff(self, **kwargs):
        """
            Method will check all patches in relevant package
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
    def run_diff(cls, **kwargs):
        old_dir = kwargs.get('old_dir')
        new_dir = kwargs.get('new_dir')
        suffix = kwargs.get('suffix')
        failed_files = kwargs.get('failed_files')
        output = kwargs.get('output')

        if old_dir == None:
            raise TypeError("MeldDiffTool: missing old_dir")
        if new_dir == None:
            raise TypeError("MeldDiffTool: missing new_dir")
        if suffix == None:
            raise TypeError("MeldDiffTool: missing suffix")
        else:
            suffix = "." + suffix
        if not failed_files:
            raise TypeError("MeldDiffTool: missing failed_files")
        if output == None:
            pass # never mind

        for fname in failed_files:
            base =   os.path.join(old_dir, fname + suffix)
            remote = os.path.join(old_dir, fname)
            local =  os.path.join(new_dir, fname + suffix)
            merged = os.path.join(new_dir, fname)

            # http://stackoverflow.com/questions/11133290/git-merging-using-meld
            cmd = [cls.CMD, '--diff', base, local, '--diff', base, remote, '--auto-merge', local, base, remote, '--output', merged]
            logger.debug("MeldDiffTool: running '" + str(cmd) + "'")
            ret = ProcessHelper.run_subprocess_cwd(' '.join(cmd), output, shell=True)
            print "ret" + str(ret)
            if len(failed_files) > 1:
                var = raw_input("Do you want to merge another patch? (y/n)")
                output = ['y', 'n']
                while var.lower() not in output:
                    var = raw_input("Do you want to merge another patch? (y/n)")
                if var.lower() == "n":
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
    def diff(cls, **kwargs):
        """
        Diff between sources
        """
        logger.debug("Diff: Diff between trees..")
        return cls._tool.run_diff(**kwargs)

if __name__ == '__main__':
    kwargs = {}
    diff = Diff('meld')
    diff.diff(**kwargs)
