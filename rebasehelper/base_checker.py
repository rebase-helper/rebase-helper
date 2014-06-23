# -*- coding: utf-8 -*-

from rebasehelper.logger import logger

check_tools = {}

def register_check_tool(check_tool):
    check_tools[check_tool.CMD] = check_tool
    return check_tool


class BaseChecker(object):
    """ Base class used for testing tool run on final pkgs. """

    @classmethod
    def match(cls, *args, **kwargs):
        """
        Checks if the tool name match the class implementation. If yes, returns
        True, otherwise returns False.
        """
        raise NotImplementedError()

    @classmethod
    def run_check(cls, *args, **kwargs):
        """
        Perform the check itself and return results.
        """
        raise NotImplementedError()


class Checker(object):
    """
    Class representing a process of checking final packages.
    """

    def __init__(self, tool=None):
        if tool is None:
            raise TypeError("Expected argument 'tool' (pos 1) is missing")
        self._tool_name = tool
        self._tool = None

        for check_tool in check_tools.values():
            if check_tool.match(self._tool_name):
                self._tool = check_tool

        if self._tool is None:
            raise NotImplementedError("Unsupported checking tool")

    def __str__(self):
        return "<Checker tool_name='{_tool_name}' tool={_tool}>".format(**vars(self))

    def run_check(self, **kwargs):
        """ Run the check """
        logger.debug("Checker: Running tests on packages using '%s'" % self._tool_name)
        return self._tool.run_check(**kwargs)

    @classmethod
    def get_supported_tools(cls):
        """ Return list of supported tools """
        return check_tools.keys()