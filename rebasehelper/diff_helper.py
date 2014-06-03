
from rebasehelper import base_checker
from rebasehelper.logger import logger

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
        pass


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

