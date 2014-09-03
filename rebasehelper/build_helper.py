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

import shutil
import os

from rebasehelper.utils import ProcessHelper
from rebasehelper.utils import PathHelper
from rebasehelper.utils import TemporaryEnvironment
from rebasehelper.logger import logger

build_tools = {}


def register_build_tool(build_tool):
    build_tools[build_tool.CMD] = build_tool
    return build_tool    


class BuildTemporaryEnvironment(TemporaryEnvironment):
    """
    Class representing temporary environment for MockBuildTool.
    """

    TEMPDIR_SOURCES = TemporaryEnvironment.TEMPDIR + '_SOURCES'
    TEMPDIR_SPEC = TemporaryEnvironment.TEMPDIR + '_SPEC'
    TEMPDIR_SPECS = TemporaryEnvironment.TEMPDIR + '_SPECS'
    TEMPDIR_RESULTS = TemporaryEnvironment.TEMPDIR + '_RESULTS'

    def __init__(self, sources, patches, spec, results_dir):
        super(BuildTemporaryEnvironment, self).__init__(self._build_env_exit_callback)
        self._env['results_dir'] = results_dir
        self.sources = sources
        self.patches = patches
        self.spec = spec

    def __enter__(self):
        obj = super(BuildTemporaryEnvironment, self).__enter__()
        log_message = "BuildTemporaryEnvironment: Copying '{0}' to '{1}'"
        # create the directory structure
        self._create_directory_sctructure()
        # copy sources
        for source in self.sources:
            logger.debug(log_message.format(source, self._env[self.TEMPDIR_SOURCES]))
            shutil.copy(source, self._env[self.TEMPDIR_SOURCES])
        # copy patches
        for patch in self.patches:
            logger.debug(log_message.format(patch, self._env[self.TEMPDIR_SOURCES]))
            shutil.copy(patch, self._env[self.TEMPDIR_SOURCES])
        # copy SPEC file
        spec_name = os.path.basename(self.spec)
        self._env[self.TEMPDIR_SPEC] = os.path.join(self._env[self.TEMPDIR_SPECS], spec_name)
        shutil.copy(self.spec, self._env[self.TEMPDIR_SPEC])
        logger.debug(log_message.format(self.spec, self._env[self.TEMPDIR_SPEC]))

        return obj

    def _create_directory_sctructure(self):
        """
        Function creating the directory structure in the TemporaryEnvironment.
        """
        raise NotImplementedError('The create directory function has to be implemented in child class!')

    def _build_env_exit_callback(self, results_dir, **kwargs):
        """
        The function that is called just before the destruction of the TemporaryEnvironment.
        It copies packages and logs into the results directory.

        :param results_dir: absolute path to results directory
        :return:
        """
        os.makedirs(results_dir)
        log_message = "BuildTemporaryEnvironment: Copying '{0}' '{1}' to '{2}'"
        # copy logs
        for log in PathHelper.find_all_files(kwargs[self.TEMPDIR_RESULTS], '*.log'):
            logger.debug(log_message.format('log', log, results_dir))
            shutil.copy(log, results_dir)
        # copy packages
        for package in PathHelper.find_all_files(kwargs[self.TEMPDIR], '*.rpm'):
            logger.debug(log_message.format('package', package, results_dir))
            shutil.copy(package, results_dir)


class BuildToolBase(object):
    """
    Base class for various build tools
    """

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

        Keyword arguments:
        spec -- path to a SPEC file
        sources -- list with absolute paths to SOURCES
        patches -- list with absolute paths to PATCHES
        results_dir -- path to DIR where results should be stored

        Returns:
        dict with:
        'srpm' -> absolute path to SRPM
        'rpm' -> list of absolute paths to RPMs
        'logs' -> list of absolute paths to logs
        """
        raise NotImplementedError()


@register_build_tool
class MockBuildTool(BuildToolBase):
    """
    Class representing Mock build tool.
    """

    CMD = "mock"

    class MockTemporaryEnvironment(BuildTemporaryEnvironment):
        """
        Class representing temporary environment for MockBuildTool.
        """

        def _create_directory_sctructure(self):
            # create directory structure
            for dir_name in ['SOURCES', 'SPECS', 'RESULTS']:
                self._env[self.TEMPDIR + '_' + dir_name] = os.path.join(self._env[self.TEMPDIR], dir_name)
                logger.debug("MockTemporaryEnvironment: Creating '{0}'".format(self._env[self.TEMPDIR + '_' + dir_name]))
                os.makedirs(self._env[self.TEMPDIR + '_' + dir_name])


    @classmethod
    def _build_srpm(cls, spec, sources, results_dir, root=None, arch=None):
        """ Build SRPM using mock. """
        logger.info("Building SRPM")
        output = os.path.join(results_dir, "mock_output.log")

        cmd = [cls.CMD, '--buildsrpm', '--spec', spec, '--sources', sources,
               '--resultdir', results_dir]
        if root is not None:
            cmd.extend(['--root', root])
        if arch is not None:
            cmd.extend(['--arch', arch])

        ret = ProcessHelper.run_subprocess(cmd, output=output)
        if ret != 0:
            return None
        else:
            return PathHelper.find_first_file(results_dir, '*.src.rpm')

    @classmethod
    def _build_rpm(cls, srpm, results_dir, root=None, arch=None):
        """ Build RPM using mock. """
        logger.info("Building RPMs")
        output = os.path.join(results_dir, "mock_output.log")

        cmd = [cls.CMD, '--rebuild', srpm, '--resultdir', results_dir]
        if root is not None:
            cmd.extend(['--root', root])
        if arch is not None:
            cmd.extend(['--arch', arch])

        ret = ProcessHelper.run_subprocess(cmd, output=output)

        if ret != 0:
            return None
        else:
            return [f for f in PathHelper.find_all_files(results_dir, '*.rpm') if not f.endswith('.src.rpm')]

    @classmethod
    def match(cls, cmd=None):
        if cmd == cls.CMD:
            return True
        else:
            return False

    @classmethod
    def build(cls, spec, sources, patches, results_dir, root=None, arch=None, **kwargs):
        """
        Builds the SRPM and RPM using mock

        :param spec: absolute path to a SPEC file
        :param sources: list with absolute paths to SOURCES
        :param patches: list with absolute paths to PATCHES
        :param results_dir: absolute path to directory where results will be stored
        :param root: mock root used for building
        :param arch: architecture to build the RPM for
        :return: dict with:
                 'srpm' -> absolute path to SRPM
                 'rpm' -> list with absolute paths to RPMs
                 'logs' -> list with absolute paths to logs
        """

        rpms = None
        srpm = None

        # build SRPM
        srpm_results_dir = os.path.join(results_dir, "SRPM")
        with cls.MockTemporaryEnvironment(sources, patches, spec, srpm_results_dir) as tmp_env:
            env = tmp_env.env()
            tmp_spec = env.get(cls.MockTemporaryEnvironment.TEMPDIR_SPEC)
            tmp_sources_dir = env.get(cls.MockTemporaryEnvironment.TEMPDIR_SOURCES)
            tmp_results_dir = env.get(cls.MockTemporaryEnvironment.TEMPDIR_RESULTS)
            srpm = cls._build_srpm(tmp_spec, tmp_sources_dir, tmp_results_dir)

        if srpm is None:
            raise RuntimeError("Building SRPM failed!")
        else:
            logger.info("Building SRPM finished successfully")

        # use the SRPM frpm results_dir
        srpm = os.path.join(srpm_results_dir, os.path.basename(srpm))
        logger.debug("MockBuildTool: Successfully built SRPM: '{0}'".format(str(srpm)))
        # gather logs
        logs = [l for l in PathHelper.find_all_files(srpm_results_dir, '*.log')]
        logger.debug("MockBuildTool: logs: '{0}'".format(str(logs)))

        # build RPM
        rpm_results_dir = os.path.join(results_dir, "RPM")
        with cls.MockTemporaryEnvironment(sources, patches, spec, rpm_results_dir) as tmp_env:
            env = tmp_env.env()
            tmp_results_dir = env.get(cls.MockTemporaryEnvironment.TEMPDIR_RESULTS)
            rpms = cls._build_rpm(srpm, tmp_results_dir)
            # remove SRPM - side product of building RPM
            tmp_srpm = PathHelper.find_first_file(tmp_results_dir, "*.src.rpm")
            if tmp_srpm is not None:
                os.unlink(tmp_srpm)

        if rpms is None:
            # We need to be inform what directory to analyze and what spec file failed
            raise RuntimeError("Building RPMs failed!", rpm_results_dir, spec)
        else:
            logger.info("Building RPM finished successfully")

        rpms = [os.path.join(rpm_results_dir, os.path.basename(f)) for f in rpms]
        logger.debug("MockBuildTool: Successfully built RPMs: '{0}'".format(str(rpms)))

        # gather logs
        logs.extend([l for l in PathHelper.find_all_files(rpm_results_dir, '*.log')])
        logger.debug("MockBuildTool: logs: '{0}'".format(str(logs)))

        return {'srpm': srpm,
                'rpm': rpms,
                'logs': logs}


@register_build_tool
class RpmbuildBuildTool(BuildToolBase):
    """
    Class representing rpmbuild build tool.
    """

    CMD = "rpmbuild"

    class RpmbuildTemporaryEnvironment(BuildTemporaryEnvironment):
        """
        Class representing temporary environment for RpmbuildBuildTool.
        """

        TEMPDIR_RPMBUILD = TemporaryEnvironment.TEMPDIR + '_RPMBUILD'
        TEMPDIR_BUILD = TemporaryEnvironment.TEMPDIR + '_BUILD'
        TEMPDIR_BUILDROOT = TemporaryEnvironment.TEMPDIR + '_BUILDROOT'
        TEMPDIR_RPMS = TemporaryEnvironment.TEMPDIR + '_RPMS'
        TEMPDIR_SRPMS = TemporaryEnvironment.TEMPDIR + '_SRPMS'

        def _create_directory_sctructure(self):
            # create rpmbuild directory structure
            for dir_name in ['RESULTS', 'rpmbuild']:
                self._env[self.TEMPDIR + '_' + dir_name.upper()] = os.path.join(self._env[self.TEMPDIR], dir_name)
                logger.debug("RpmbuildTemporaryEnvironment: Creating '{0}'".format(self._env[self.TEMPDIR + '_' + dir_name.upper()]))
                os.makedirs(self._env[self.TEMPDIR + '_' + dir_name.upper()])
            for dir_name in ['BUILD', 'BUILDROOT', 'RPMS', 'SOURCES', 'SPECS', 'SRPMS']:
                self._env[self.TEMPDIR + '_' + dir_name] = os.path.join(self._env[self.TEMPDIR_RPMBUILD],
                                                                        dir_name)
                logger.debug("RpmbuildTemporaryEnvironment: Creating '{0}'".format(self._env[self.TEMPDIR + '_' + dir_name]))
                os.makedirs(self._env[self.TEMPDIR + '_' + dir_name])


    @classmethod
    def _build_srpm(cls, spec, workdir, results_dir):
        """
        Build SRPM using rpmbuild.

        :param spec: abs path to SPEC file inside the rpmbuild/SPECS in workdir.
        :param workdir: abs path to working directory with rpmbuild directory
                        structure, which will be used as HOME dir.
        :param results_dir: abs path to dir where the log should be placed.
        :return: If build process ends successfully returns list of abs paths
                 to built RPMs, otherwise 'None'.
        """
        logger.info("Building SRPM")
        spec_loc, spec_name = os.path.split(spec)
        output = os.path.join(results_dir, "rpmbuild_output.log")

        cmd = [cls.CMD, '-bs', spec_name]
        ret = ProcessHelper.run_subprocess_cwd_env(cmd,
                                                   cwd=spec_loc,
                                                   env={'HOME': workdir},
                                                   output=output)

        if ret != 0:
            return None
        else:
            return PathHelper.find_first_file(workdir, '*.src.rpm')

    @classmethod
    def _build_rpm(cls, srpm, workdir, results_dir):
        """
        Build RPM using rpmbuild.

        :param srpm: abs path to SRPM
        :param workdir: abs path to working directory with rpmbuild directory
                        structure, which will be used as HOME dir.
        :param results_dir: abs path to dir where the log should be placed.
        :return: If build process ends successfully returns list of abs paths
                 to built RPMs, otherwise 'None'.
        """
        logger.info("Building RPMs")
        output = os.path.join(results_dir, "rpmbuild_output.log")

        cmd = [cls.CMD, '--rebuild', srpm]
        ret = ProcessHelper.run_subprocess_cwd_env(cmd,
                                                   env={'HOME': workdir},
                                                   output=output)

        if ret != 0:
            return None
        else:
            return [f for f in PathHelper.find_all_files(workdir, '*.rpm') if not f.endswith('.src.rpm')]

    @classmethod
    def match(cls, cmd=None):
        if cmd == cls.CMD:
            return True
        else:
            return False

    @classmethod
    def build(cls, spec, sources, patches, results_dir, **kwargs):
        """
        Builds the SRPM and RPMs using rpmbuild

        :param spec: absolute path to the SPEC file.
        :param sources: list with absolute paths to SOURCES
        :param patches: list with absolute paths to PATCHES
        :param results_dir: absolute path to DIR where results should be stored
        :return: dict with:
                 'srpm' -> absolute path to SRPM
                 'rpm' -> list with absolute paths to RPMs
                 'logs' -> list with absolute paths to build_logs
        """

        rpms = None
        srpm = None

        # build SRPM
        srpm_results_dir = os.path.join(results_dir, "SRPM")
        with cls.RpmbuildTemporaryEnvironment(sources, patches, spec, srpm_results_dir) as tmp_env:
            env = tmp_env.env()
            tmp_dir = tmp_env.path()
            tmp_spec = env.get(cls.RpmbuildTemporaryEnvironment.TEMPDIR_SPEC)
            tmp_results_dir = env.get(cls.RpmbuildTemporaryEnvironment.TEMPDIR_RESULTS)
            srpm = cls._build_srpm(tmp_spec, tmp_dir, tmp_results_dir)

        if srpm is None:
            raise RuntimeError("Building SRPM failed!")
        else:
            logger.info("Building SRPM finished successfully")

        # srpm path in results_dir
        srpm = os.path.join(srpm_results_dir, os.path.basename(srpm))
        logger.debug("RpmbuildBuildTool: Successfully built SRPM: '{0}'".format(str(srpm)))
        # gather logs
        logs = [l for l in PathHelper.find_all_files(srpm_results_dir, '*.log')]
        logger.debug("RpmbuildBuildTool: logs: '{0}'".format(str(logs)))

        # build RPMs
        rpm_results_dir = os.path.join(results_dir, "RPM")
        with cls.RpmbuildTemporaryEnvironment(sources, patches, spec, rpm_results_dir) as tmp_env:
            env = tmp_env.env()
            tmp_dir = tmp_env.path()
            tmp_results_dir = env.get(cls.RpmbuildTemporaryEnvironment.TEMPDIR_RESULTS)
            rpms = cls._build_rpm(srpm, tmp_dir, tmp_results_dir)

        if rpms is None:
            raise RuntimeError("RpmbuildBuildTool: Building RPMs failed!")
        else:
            logger.info("Building RPMs finished successfully")

        # RPMs paths in results_dir
        rpms = [os.path.join(rpm_results_dir, os.path.basename(f)) for f in rpms]
        logger.debug("RpmbuildBuildTool: Successfully built RPMs: '{0}'".format(str(rpms)))

        # gather logs
        logs.extend([l for l in PathHelper.find_all_files(rpm_results_dir, '*.log')])
        logger.debug("RpmbuildBuildTool: logs: '{0}'".format(str(logs)))

        return {'srpm': srpm,
                'rpm': rpms,
                'logs': logs}


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
        return "<Builder tool_name='{_tool_name}' tool='{_tool}'>".format(**vars(self))

    def build(self, **kwargs):
        """ Build sources. """
        logger.debug("Builder: Building sources using '{0}'".format(self._tool_name))
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
        for path in ['old', 'new']:
            input_structure = kwargs.get(path)
            input_structure['results_dir'] = os.path.join(kwargs.get('results_dir'), path)
            logger.info("Building packages from sources '{0}'".format(input_structure.get('tarball', '')))
            results = self.build(**input_structure)
            kwargs[path].update(results)
