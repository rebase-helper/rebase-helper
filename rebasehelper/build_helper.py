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

import shutil
import os

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

    results_dir = ''

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
        logger.debug("MockBuildTool: Building SRPM")
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

        ret = ProcessHelper.run_subprocess(cmd, output=output)
        if ret != 0:
            return None
        else:
            return PathHelper.find_first_file(resultdir, '*.src.rpm')

    @classmethod
    def _build_rpm(cls, **kwargs):
        """ Build RPM using mock. """
        logger.debug("MockBuildTool: Building RPMs")
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

        ret = ProcessHelper.run_subprocess(cmd, output=output)

        if ret != 0:
            return None
        else:
            return [f for f in PathHelper.find_all_files(resultdir, '*.rpm') if not f.endswith('.src.rpm')]

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

        cls.results_dir = kwargs.get('workspace_dir', '')

        # build SRPM
        logger.info("Building SRPM package from {0} sources...".format(kwargs.get('tarball', '')))
        srpm = cls._build_srpm(**env)
        logger.info("Building SRPM package done.")
        srpm_resultdir = os.path.join(cls.results_dir, "SRPM")
        shutil.copytree(env[cls.TEMPDIR_RESULTDIR], srpm_resultdir)
        if srpm is None:
            logger.error("MockBuildTool: Building SRPM failed!")
            raise RuntimeError()

        # use the SRPM frpm resultdir
        srpm = os.path.join(srpm_resultdir, os.path.basename(srpm))
        logger.debug("MockBuildTool: Successfully built SRPM: '%s'" % str(srpm))

        # reset the environment
        cls._envoronment_clear_resultdir(**env)

        # build RPM
        logger.info("Building RPM packages with SRPM from {0} sources...".format(kwargs.get('tarball', '')))
        rpms = cls._build_rpm(srpm=srpm, **env)
        logger.info("Building RPM packages done.")
        rpm_resultdir = os.path.join(cls.results_dir, "RPM")
        # remove SRPM - side product of building RPM
        tmp_srpm = PathHelper.find_first_file(env[cls.TEMPDIR_RESULTDIR], "*.src.rpm")
        if tmp_srpm is not None:
            os.unlink(tmp_srpm)
        shutil.copytree(env[cls.TEMPDIR_RESULTDIR], rpm_resultdir)
        if rpms is None:
            logger.error("MockBuildTool: Building RPMs failed!")
            raise RuntimeError()

        rpms = [os.path.join(rpm_resultdir, os.path.basename(f)) for f in rpms]
        logger.debug("MockBuildTool: Successfully built RPMs: '%s'" % str(rpms))

        # destroy the temporary environment
        cls._environment_destroy(**env)

        return {'srpm': srpm,
                'rpm': rpms}


@register_build_tool
class RpmbuildBuildTool(BuildToolBase):
    """ rpmbuild build tool. """
    CMD = "rpmbuild"

    TEMPDIR = 'tempdir_'
    TEMPDIR_RPMBUILD = TEMPDIR + 'rpmbuild'
    TEMPDIR_RPMBUILD_BUILD = TEMPDIR_RPMBUILD + '_build'
    TEMPDIR_RPMBUILD_BUILDROOT = TEMPDIR_RPMBUILD + '_buildroot'
    TEMPDIR_RPMBUILD_RPMS = TEMPDIR_RPMBUILD + '_rpms'
    TEMPDIR_RPMBUILD_SOURCES = TEMPDIR_RPMBUILD + '_sources'
    TEMPDIR_RPMBUILD_SPECS = TEMPDIR_RPMBUILD + '_specs'
    TEMPDIR_RPMBUILD_SRPMS = TEMPDIR_RPMBUILD + '_srpms'
    TEMPDIR_SPEC = 'tempdir_spec'
    TEMPDIR_RESULTDIR = 'tempdir_resultdir'

    results_dir = ''

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
        for dir_name in ['BUILD', 'BUILDROOT', 'RPMS', 'SOURCES', 'SPECS', 'SRPMS']:
            env[cls.TEMPDIR_RPMBUILD + "_" + dir_name.lower()] = os.path.join(env[cls.TEMPDIR_RPMBUILD], dir_name)
            os.makedirs(env[cls.TEMPDIR_RPMBUILD + "_" + dir_name.lower()])

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

        logger.debug("RpmbuildBuildTool: Prepared temporary environment in '%s' " % env[cls.TEMPDIR])
        # merge kwargs ans env
        return dict(kwargs.items() + env.items())

    @classmethod
    def _environment_destroy(cls, **kwargs):
        """ Destroys the temprary environment. """
        shutil.rmtree(kwargs[cls.TEMPDIR])
        logger.debug("RpmbuildBuildTool: Destroyed temporary environment in '%s'" % kwargs[cls.TEMPDIR])

    @classmethod
    def _envoronment_clear_resultdir(cls, **kwargs):
        """ Removes the content of cls.TEMPDIR_RESULTDIR. """
        logger.debug("RpmbuildBuildTool: cleaning the temporary resultdir '%s'" % kwargs[cls.TEMPDIR_RESULTDIR])
        shutil.rmtree(kwargs[cls.TEMPDIR_RESULTDIR])
        os.mkdir(kwargs[cls.TEMPDIR_RESULTDIR])

    @classmethod
    def _build_srpm(cls, **kwargs):
        """ Build SRPM using rpmbuild. """
        logger.debug("RpmbuildBuildTool: Building SRPM")

        spec_name = os.path.basename(kwargs.get(cls.TEMPDIR_SPEC))
        home = kwargs.get(cls.TEMPDIR)
        resultdir = kwargs.get(cls.TEMPDIR_RESULTDIR)
        output = os.path.join(resultdir, "rpmbuild_output.log")

        cmd = [cls.CMD, '-bs', spec_name]
        ret = ProcessHelper.run_subprocess_cwd_env(cmd,
                                                   cwd=kwargs[cls.TEMPDIR_RPMBUILD_SPECS],
                                                   env={'HOME': home},
                                                   output=output)

        if ret != 0:
            return None
        else:
            return PathHelper.find_first_file(kwargs[cls.TEMPDIR_RPMBUILD_SRPMS], '*.src.rpm')

    @classmethod
    def _build_rpm(cls, **kwargs):
        """ Build RPM using rpmbuild. """
        logger.debug("RpmbuildBuildTool: Building RPM")
        home = kwargs.get(cls.TEMPDIR)
        srpm = kwargs.get('srpm')
        resultdir = kwargs.get(cls.TEMPDIR_RESULTDIR)
        output = os.path.join(resultdir, "rpmbuild_output.log")

        cmd = [cls.CMD, '--rebuild', srpm]
        ret = ProcessHelper.run_subprocess_cwd_env(cmd,
                                                   cwd=kwargs[cls.TEMPDIR_RPMBUILD_SPECS],
                                                   env={'HOME': home},
                                                   output=output)

        if ret != 0:
            return None
        else:
            return [f for f in PathHelper.find_all_files(kwargs[cls.TEMPDIR_RPMBUILD_RPMS], '*.rpm')]

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

        # TODO: check for dependencies from SRPM! If they are missing, the build will fail

        # prepare environment for building
        env = cls._environment_prepare(**kwargs)

        cls.results_dir = kwargs.get('workspace_dir', '')

        # build SRPM
        logger.info("Building SRPM package from sources {0}...".format(kwargs.get('tarball', '')))
        srpm = cls._build_srpm(**env)
        logger.info("Building SRPM package done.")
        srpm_resultdir = os.path.join(cls.results_dir, "SRPM")
        shutil.copytree(env[cls.TEMPDIR_RESULTDIR], srpm_resultdir)
        if srpm is None:
            logger.error("RpmbuildBuildTool: Building SRPM failed!")
            raise RuntimeError()

        # copy the SRPM
        shutil.copy(srpm, srpm_resultdir)
        srpm = os.path.join(srpm_resultdir, os.path.basename(srpm))
        logger.debug("RpmbuildBuildTool: Successfully built SRPM: '%s'" % str(srpm))

        # reset the environment
        cls._envoronment_clear_resultdir(**env)

        # build RPM
        logger.info("Building RPM packages with SRPM from {0} sources...".format(kwargs.get('tarball', '')))
        rpms = cls._build_rpm(srpm=srpm, **env)
        logger.info("Building RPM packages done.")
        rpm_resultdir = os.path.join(cls.results_dir, "RPM")
        shutil.copytree(env[cls.TEMPDIR_RESULTDIR], rpm_resultdir)
        if rpms is None:
            logger.error("RpmbuildBuildTool: Building RPMs failed!")
            raise RuntimeError()

        # copy RPMs
        for rpm in rpms:
            shutil.copy(rpm, rpm_resultdir)

        rpms = [os.path.join(rpm_resultdir, os.path.basename(f)) for f in rpms]
        logger.debug("RpmbuildBuildTool: Successfully built RPMs: '%s'" % str(rpms))

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

    @classmethod
    def get_supported_tools(cls):
        """
        Returns a list of supported build tools

        :return: list of supported build tools
        """
        return build_tools.keys()

    def build_packages(self, **kwargs):
        """
        Build old and new packages
        Returns structure like
        {new: {'srpm': <path_to_srpm>,
                'rpm': <path_to_rpm>, <path_to_rpm>},
        {old: {'srpm': <path_to_srpm>,
                'rpm' : <path_to_rpm>, <path_to_rpm>},
        }
        :param kwargs:
        :return: new and old packages
        """
        if 'old' not in kwargs:
            logger.error('Builder class expects old specfile, sources and patches.')
            raise RuntimeError
        if 'new' not in kwargs:
            logger.error('Builder class expects new specfile, sources and patches.')
            raise RuntimeError
        if 'workspace_dir' not in kwargs:
            logger.error('Builder class expects workspace_dir.')
            raise RuntimeError

        for path in ['old', 'new']:
            input_structure = kwargs.get(path)
            input_structure['workspace_dir'] = os.path.join(kwargs.get('workspace_dir'), path)
            results = self.build(**input_structure)
            kwargs[path].update(results)
