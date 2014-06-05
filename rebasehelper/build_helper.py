# -*- coding: utf-8 -*-

from rebasehelper.utils import ProcessHelper
from rebasehelper.utils import PathHelper
from rebasehelper.logger import logger

import shutil
import os

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
        """ Build binaries from the sources.

        Keyword arguments:
        spec -- path to a SPEC file
        sources -- list with absolute paths to SOURCES
        patches -- list with absolute paths to PATCHES
        resultdir -- path to DIR where results should be stored

        Returns:
        dict with:
        'srpm' -> path to SRPM
        'rpm' -> list with paths to RPMs
        """
        raise NotImplementedError()


@register_build_tool
class MockBuildTool(BuildToolBase):
    """ Mock build tool. """
    CMD = "mock"

    TEMPDIR = 'tempdir'
    TEMPDIR_SOURCES = 'tempdir_sources'
    TEMPDIR_SPEC = 'tempdir_spec'
    TEMPDIR_RESULTDIR = 'tempdir_resultdir'

    @classmethod
    def match(cls, cmd=None):
        if cmd == cls.CMD:
            return True
        else:
            return False


    @classmethod
    def _environment_prepare(cls, **kwargs):
        """ Create a temporary directory and copy sources and SPEC file in. """
        env = {}
        env[cls.TEMPDIR] = PathHelper.get_temp_dir()

        # copy sources
        env[cls.TEMPDIR_SOURCES] = os.path.join(env[cls.TEMPDIR], "SOURCES")
        os.makedirs(env[cls.TEMPDIR_SOURCES])
        for source in kwargs['sources']:
            shutil.copy(source, env[cls.TEMPDIR_SOURCES])
        # copy patches
        for patch in kwargs['patches']:
            shutil.copy(patch, env[cls.TEMPDIR_SOURCES])

        # copy SPEC file
        tempdir_spec_dir = os.path.join(env[cls.TEMPDIR], "SPECS")
        spec_name = os.path.basename(kwargs['spec'])
        os.makedirs(tempdir_spec_dir)
        env[cls.TEMPDIR_SPEC] = os.path.join(tempdir_spec_dir, spec_name)
        shutil.copy(kwargs['spec'], env[cls.TEMPDIR_SPEC])

        # create temporary results directory
        env[cls.TEMPDIR_RESULTDIR] = os.path.join(env[cls.TEMPDIR], "RESULTS")
        os.makedirs(env[cls.TEMPDIR_RESULTDIR])

        logger.debug("MockBuildTool: Prepared temporary environment in '%s'" % env[cls.TEMPDIR])
        # merge kwargs ans env
        return dict(kwargs.items() + env.items())


    @classmethod
    def _environment_destroy(cls, **kwargs):
        """ Destroys the temprary environment. """
        shutil.rmtree(kwargs[cls.TEMPDIR])
        logger.debug("MockBuildTool: Destroyed temporary environment in '%s'" % kwargs[cls.TEMPDIR])


    @classmethod
    def _envoronment_clear_resultdir(cls, **kwargs):
        """ Removes the content of cls.TEMPDIR_RESULTDIR. """
        logger.debug("MockBuildTool: cleaning the temporary resultdir '%s'" % kwargs[cls.TEMPDIR_RESULTDIR])
        shutil.rmtree(kwargs[cls.TEMPDIR_RESULTDIR])
        os.mkdir(kwargs[cls.TEMPDIR_RESULTDIR])


    @classmethod
    def _build_srpm(cls, **kwargs):
        """ Build SRPM using mock. """
        logger.debug("MockBuildTool: Building SRPM...")
        spec = kwargs.get(cls.TEMPDIR_SPEC)
        sources = kwargs.get(cls.TEMPDIR_SOURCES)
        root = kwargs.get('root')
        arch = kwargs.get('arch')
        resultdir = kwargs.get(cls.TEMPDIR_RESULTDIR)
        output = os.path.join(resultdir, "mock_output.log")

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
        logger.debug("MockBuildTool: Building RPMs...")
        srpm = kwargs.get('srpm')
        root = kwargs.get('root')
        arch = kwargs.get('arch')
        resultdir = kwargs.get(cls.TEMPDIR_RESULTDIR)
        output = os.path.join(resultdir, "mock_output.log")

        cmd = [cls.CMD, '--rebuild', srpm, '--resultdir', resultdir]
        if root is not None:
            cmd.extend(['--root', root])
        if arch is not None:
            cmd.extend(['--arch', arch])

        logger.debug("MockBuildTool: running: " + str(cmd))
        ret = ProcessHelper.run_subprocess(cmd, output)

        if ret != 0:
            logger.error("MockBuildTool: running: " + str(cmd) + " failed!")
            return None
        else:
            return [ f for f in PathHelper.find_all_files(resultdir, '*.rpm') if not f.endswith('.src.rpm') ]


    @classmethod
    def build(cls, **kwargs):
        """ Builds the SRPM and RPM using mock

        Keyword arguments:
        spec -- path to a SPEC file
        sources -- list with absolute paths to SOURCES
        patches -- list with absolute paths to PATCHES
        root -- mock root used for building
        arch -- architecture to build the RPM for
        resultdir -- path to DIR where results should be stored

        Returns:
        dict with:
        'srpm' -> path to SRPM
        'rpm' -> list with paths to RPMs
        """
        # prepare environment for building
        env = cls._environment_prepare(**kwargs)

        # build SRPM
        srpm = cls._build_srpm(**env)
        srpm_resultdir = os.path.join(kwargs['resultdir'], "SRPM")
        if os.path.exists(srpm_resultdir):
            shutil.rmtree(srpm_resultdir)
        shutil.copytree(env[cls.TEMPDIR_RESULTDIR], srpm_resultdir)
        if srpm is None:
            logger.error("MockBuildTool: Building SRPM failed!")
            raise RuntimeError()
        # use the SRPM frpm resultdir
        srpm = os.path.join(srpm_resultdir, os.path.basename(srpm))

        # reset the environment
        cls._envoronment_clear_resultdir(**env)

        # build RPM
        rpms = cls._build_rpm(srpm=srpm, **env)
        rpm_resultdir = os.path.join(kwargs['resultdir'], "RPM")
        # remove SRPM - side product of building RPM
        tmp_srpm = PathHelper.find_first_file(env[cls.TEMPDIR_RESULTDIR], "*.src.rpm")
        if tmp_srpm is not None:
            os.unlink(tmp_srpm)
        shutil.copytree(env[cls.TEMPDIR_RESULTDIR], rpm_resultdir)
        if len(rpms) == 0:
            logger.error("MockBuildTool: Building RPMs failed!")
            raise RuntimeError()
        print str(rpms)
        rpms = [ os.path.join(rpm_resultdir, os.path.basename(f)) for f in rpms ]

        # destroy the temporary environment
        cls._environment_destroy(**env)

        return {'srpm': srpm,
                'rpm': rpms}


@register_build_tool
class RpmbuildBuildTool(BuildToolBase):
    """ rpmbuild build tool. """
    CMD = "rpmbuild"

    TEMPDIR = 'tempdir'
    TEMPDIR_RPMBUILD = 'tempdir_rpmbuild'
    TEMPDIR_RPMBUILD_BUILD = 'tempdir_rpmbuild_build'
    TEMPDIR_RPMBUILD_BUILDROOT = 'tempdir_rpmbuild_buildroot'
    TEMPDIR_RPMBUILD_RPMS = 'tempdir_rpmbuild_rpms'
    TEMPDIR_RPMBUILD_SOURCES = 'tempdir_rpmbuild_sources'
    TEMPDIR_RPMBUILD_SPECS = 'tempdir_rpmbuild_specs'
    TEMPDIR_RPMBUILD_SRPMS = 'tempdir_rpmbuild_srpms'
    TEMPDIR_SPEC = 'tempdir_spec'
    TEMPDIR_RESULTDIR = 'tempdir_resultdir'

    @classmethod
    def match(cls, cmd=None):
        if cmd == cls.CMD:
            return True
        else:
            return False


    @classmethod
    def _environment_prepare(cls, **kwargs):
        """ Create a temporary directory and copy sources and SPEC file in. """
        env = {}
        env[cls.TEMPDIR] = PathHelper.get_temp_dir()

        # create rpmbuild directory structure
        env[cls.TEMPDIR_RPMBUILD] = os.path.join(env[cls.TEMPDIR], 'rpmbuild')
        os.makedirs(env[cls.TEMPDIR_RPMBUILD])
        env[cls.TEMPDIR_RPMBUILD_BUILD] = os.path.join(env[cls.TEMPDIR_RPMBUILD], 'BUILD')
        os.makedirs(env[cls.TEMPDIR_RPMBUILD_BUILD])
        env[cls.TEMPDIR_RPMBUILD_BUILDROOT] = os.path.join(env[cls.TEMPDIR_RPMBUILD], 'BUILDROOT')
        os.makedirs(env[cls.TEMPDIR_RPMBUILD_BUILDROOT])
        env[cls.TEMPDIR_RPMBUILD_RPMS] = os.path.join(env[cls.TEMPDIR_RPMBUILD], 'RPMS')
        os.makedirs(env[cls.TEMPDIR_RPMBUILD_RPMS])
        env[cls.TEMPDIR_RPMBUILD_SOURCES] = os.path.join(env[cls.TEMPDIR_RPMBUILD], 'SOURCES')
        os.makedirs(env[cls.TEMPDIR_RPMBUILD_SOURCES])
        env[cls.TEMPDIR_RPMBUILD_SPECS] = os.path.join(env[cls.TEMPDIR_RPMBUILD], 'SPECS')
        os.makedirs(env[cls.TEMPDIR_RPMBUILD_SPECS])
        env[cls.TEMPDIR_RPMBUILD_SRPMS] = os.path.join(env[cls.TEMPDIR_RPMBUILD], 'SRPMS')
        os.makedirs(env[cls.TEMPDIR_RPMBUILD_SRPMS])

        # copy sources
        for source in kwargs['sources']:
            shutil.copy(source, env[cls.TEMPDIR_RPMBUILD_SOURCES])
        # copy patches
        for patch in kwargs['patches']:
            shutil.copy(patch, env[cls.TEMPDIR_RPMBUILD_SOURCES])

        # copy SPEC file
        spec_name = os.path.basename(kwargs['spec'])
        env[cls.TEMPDIR_SPEC] = os.path.join(env[cls.TEMPDIR_RPMBUILD_SPECS], spec_name)
        shutil.copy(kwargs['spec'], env[cls.TEMPDIR_SPEC])

        # create temporary results directory
        env[cls.TEMPDIR_RESULTDIR] = os.path.join(env[cls.TEMPDIR], "RESULTS")
        os.makedirs(env[cls.TEMPDIR_RESULTDIR])

        logger.debug("RpmbuildBuildTool: Prepared temporary environemt in '%s' " % env[cls.TEMPDIR])
        # merge kwargs ans env
        return dict(kwargs.items() + env.items())


    @classmethod
    def _environment_destroy(cls, **kwargs):
        """ Destroys the temprary environment. """
        shutil.rmtree(kwargs[cls.TEMPDIR])
        logger.debug("RpmbuildBuildTool: Destroyed temporary environemt in '%s'" % kwargs[cls.TEMPDIR])


    @classmethod
    def _envoronment_clear_resultdir(cls, **kwargs):
        """ Removes the content of cls.TEMPDIR_RESULTDIR. """
        logger.debug("RpmbuildBuildTool: cleaning the temporary resultdir '%s'" % kwargs[cls.TEMPDIR_RESULTDIR])
        shutil.rmtree(kwargs[cls.TEMPDIR_RESULTDIR])
        os.mkdir(kwargs[cls.TEMPDIR_RESULTDIR])


    @classmethod
    def _build_srpm(cls, **kwargs):
        """ Build SRPM using rpmbuild. """
        logger.debug("RpmbuildBuildTool: Building SRPM...")

        spec_name = os.path.basename(kwargs.get(cls.TEMPDIR_SPEC))
        home = kwargs.get(cls.TEMPDIR)
        resultdir = kwargs.get(cls.TEMPDIR_RESULTDIR)
        output = os.path.join(resultdir, "rpmbuild_output.log")

        cmd = [cls.CMD, '-bs', spec_name]
        logger.debug("RpmbuildBuildTool: running: " + str(cmd))
        ret = ProcessHelper.run_subprocess_cwd_env(cmd, kwargs[cls.TEMPDIR_RPMBUILD_SPECS], {'HOME='+ home}, output)

        if ret != 0:
            logger.error("RpmbuildBuildTool: running: " + str(cmd) + " failed!")
            return None
        else:
            return PathHelper.find_first_file(kwargs[cls.TEMPDIR_RPMBUILD_SRPMS], '*.src.rpm')


    @classmethod
    def _build_rpm(cls, **kwargs):
        """ Build RPM using rpmbuild. """
        logger.debug("RpmbuildBuildTool: Building RPM...")
        home = kwargs.get(cls.TEMPDIR)
        srpm = kwargs.get('srpm')
        resultdir = kwargs.get(cls.TEMPDIR_RESULTDIR)
        output = os.path.join(resultdir, "mock_output.log")

        cmd = ['HOME=' + home, cls.CMD, '--rebuild', srpm]
        logger.debug("RpmbuildBuildTool: running: " + str(cmd))
        ret = ProcessHelper.run_subprocess(cmd, kwargs[cls.TEMPDIR_RPMBUILD_SPECS], output, True)

        if ret != 0:
            logger.error("RpmbuildBuildTool: running: " + str(cmd) + " failed!")
            return None
        else:
            return [ f for f in PathHelper.find_all_files(kwargs[cls.TEMPDIR_RPMBUILD_RPMS], '*.rpm') ]


    @classmethod
    def build(cls, **kwargs):
        """ Builds the SRPM and RPM using rpmbuild

        Keyword arguments:
        spec -- path to a SPEC file
        sources -- list with absolute paths to SOURCES
        patches -- list with absolute paths to PATCHES
        resultdir -- path to DIR where results should be stored

        Returns:
        dict with:
        'srpm' -> path to SRPM
        'rpm' -> list with paths to RPMs
        """
        # prepare environment for building
        env = cls._environment_prepare(**kwargs)

        # build SRPM
        srpm = cls._build_srpm(**env)
        srpm_resultdir = os.path.join(kwargs['resultdir'], "SRPM")
        shutil.copytree(env[cls.TEMPDIR_RESULTDIR], srpm_resultdir)
        if srpm is None:
            logger.error("RpmbuildBuildTool: Building SRPM failed!")
            raise RuntimeError()
        # copy the SRPM
        shutil.copy(srpm, srpm_resultdir)
        srpm = os.path.join(srpm_resultdir, os.path.basename(srpm))

        # reset the environment
        cls._envoronment_clear_resultdir(**env)

        # build RPM
        rpms = cls._build_rpm(srpm=srpm, **env)
        rpm_resultdir = os.path.join(kwargs['resultdir'], "RPM")
        shutil.copytree(env[cls.TEMPDIR_RESULTDIR], rpm_resultdir)
        if len(rpms) == 0:
            logger.error("RpmbuildBuildTool: Building RPMs failed!")
            raise RuntimeError()
        # copy RPMs
        for rpm in rpms:
            shutil.copy(rpm, rpm_resultdir)
        rpms = [ os.path.join(rpm_resultdir, os.path.basename(f)) for f in rpms ]

        # destroy the temporary environment
        cls._environment_destroy(**env)

        return {'srpm': srpm,
                'rpm': rpms}


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
        logger.debug("Builder: Building sources using '%s'" % self._tool_name)
        return self._tool.build(**kwargs)
