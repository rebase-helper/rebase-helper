# -*- coding: utf-8 -*-

from rebasehelper import logger

build_tools = {}

def register_build_tool(build_tool):
    build_tools[build_tool.CMD] = build_tool
    return build_tool    


class BuildToolBase(object):
    """ Base class for various build tools """

    @classmethod
    def match(cls, *args, **kwargs):
        """
        Checks if tool name matches the desired one.
        """
        raise NotImplementedError()

    @classmethod
    def build(cls, *args, **kwargs):
        """
        Build binaries from the sources.
        """
        raise NotImplementedError()


@register_build_tool
class MockBuildTool(BuildToolBase):
    """ Mock build tool. """
    CMD = "mock"
    
    @classmethod
    def match(cls, cmd=None):
        if cmd == cls.CMD:
            return True
        else:
            return False
            
    @classmethod
    def build(cls):
        raise NotImplementedError()


class Builder(object):
    """
    Class representing a process of building binaries from sources.
    """
    
    @classmethod
    def __init__(cls, tool=None):
        if tool is None:
            raise TypeError("Expected argument 'tool' (pos 1) is missing")
        cls._tool_name = tool
        cls._tool = None

        for build_tool in build_tools.values():
            if build_tool.match(cls._tool_name):
                cls._tool = build_tool

        if cls._tool is None:
            raise NotImplementedError("Unsupported build tool")
    
    @classmethod
    def build(cls, spec_file=None, sources=None):
        """ Build sources. """
        logger.debug("Builder: Building sources '{0}' using '{1}'".format(
                     sources, cls._tool_name))
        raise NotImplementedError()