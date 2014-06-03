# -*- coding: utf-8 -*-

from rebasehelper.utils import ProcessHelper
from rebasehelper.utils import PathHelper
from rebasehelper.logger import logger

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
    def _build_srpm(cls, **kwargs):
        """ Build SRPM using mock. """
        spec = kwargs.get('spec')
        sources = kwargs.get('sources')
        root = kwargs.get('root')
        arch = kwargs.get('arch')
        resultdir = kwargs.get('resultdir')
        output = kwargs.get('output')

        cmd = [cls.CMD, '--buildsrpm', '--spec', spec, '--sources', sources,
               '--resultdir', resultdir]
        if root is not None:
            cmd.extend(['--root', root])
        if arch is not None:
            cmd.extend(['--arch', arch])

        logger.debug("MockBuildTool: running '" + str(cmd) + "'")
        ret = ProcessHelper.run_subprocess(cmd, output)

        if ret != 0:
            logger.debug("MockBuildTool: running '" + str(cmd) + "' failed")
            return None
        else:
            return PathHelper.find_first_file(resultdir, '*.src.rpm')


    @classmethod
    def _build_rpm(cls, **kwargs):
        """ Build RPM using mock. """
        srpm = kwargs.get('srpm')
        root = kwargs.get('root')
        arch = kwargs.get('arch')
        resultdir = kwargs.get('resultdir')
        output = kwargs.get('output')

        cmd = [cls.CMD, '--rebuild', srpm, '--resultdir', resultdir]
        if root is not None:
            cmd.extend(['--root', root])
        if arch is not None:
            cmd.extend(['--arch', arch])

        logger.debug("MockBuildTool: running '" + str(cmd) + "'")
        ret = ProcessHelper.run_subprocess(cmd, output)

        if ret != 0:
            logger.debug("MockBuildTool: running '" + str(cmd) + "' failed")
            return None
        else:
            return [ f for f in PathHelper.find_all_files(resultdir, '*.rpm') if not f.endswith('.src.rpm') ]


    @classmethod
    def build(cls, **kwargs):
        """ Builds the SRPM and RPM using mock

        Keyword arguments:
        spec -- path to a SPEC file
        sources -- path to a DIR with SOURCES
        root -- mock root used for building
        arch -- architecture to build the RPM for
        resultdir -- path to DIR where results should be stored
        output -- where mock output should be stored (TODO: split log for RPM and SRPM)

        Returns:
        dict with:
        'srpm' -> path to SRPM
        'rpm' -> list with paths to RPMs
        """
        srpm = cls._build_srpm(**kwargs)
        if srpm is None:
            logger.debug("MockBuildTool: Building SRPM failed")
            raise RuntimeError()
        rpms = cls._build_rpm(srpm=srpm, **kwargs)
        return {'srpm': srpm,
                'rpm': rpms}


@register_build_tool
class RpmbuildBuildTool(BuildToolBase):
    """ rpmbuild build tool. """
    CMD = "rpmbuild"

    @classmethod
    def match(cls, cmd=None):
        if cmd == cls.CMD:
            return True
        else:
            return False


    @classmethod
    def _build_srpm(cls, **kwargs):
        """ Build SRPM using rpmbuild. """
        raise NotImplementedError()


    @classmethod
    def _build_rpm(cls, **kwargs):
        """ Build RPM using rpmbuild. """
        raise NotImplementedError()


    @classmethod
    def build(cls, **kwargs):
        """ Build the SRPM + RPM """
        srpm = cls._build_srpm(**kwargs)
        if srpm is None:
            logger.debug("RpmbuildBuildTool: Building SRPM failed")
            raise RuntimeError()
        return cls._build_rpm(srpm=srpm, **kwargs)


class Builder(object):
    """
    Class representing a process of building binaries from sources.
    """

    def __init__(self, tool=None):
        if tool is None:
            raise TypeError("Expected argument 'tool' (pos 1) is missing")
        self._tool_name = tool
        self._tool = None

        for build_tool in build_tools.values():
            if build_tool.match(self._tool_name):
                self._tool = build_tool

        if self._tool is None:
            raise NotImplementedError("Unsupported build tool")


    def __str__(self):
        return "<Builder tool_name='{_tool_name}' tool={_tool}>".format(**vars(self))


    def build(self, **kwargs):
        """ Build sources. """
        logger.debug("Builder: Building sources...")
        return self._tool.build(**kwargs)
