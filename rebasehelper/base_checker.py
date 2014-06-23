# -*- coding: utf-8 -*-
import os
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

