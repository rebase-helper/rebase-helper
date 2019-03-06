# -*- coding: utf-8 -*-
#
# This tool helps you rebase your package to the latest version
# Copyright (C) 2013-2019 Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
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
# Authors: Petr Hráček <phracek@redhat.com>
#          Tomáš Hozza <thozza@redhat.com>
#          Nikola Forró <nforro@redhat.com>
#          František Nečas <fifinecas@seznam.cz>

import shlex
import shutil
import os

import six

from rebasehelper.plugins import Plugin, PluginLoader
from rebasehelper.helpers.path_helper import PathHelper
from rebasehelper.temporary_environment import TemporaryEnvironment
from rebasehelper.logger import logger


class SourcePackageBuildError(RuntimeError):
    """
    Error indicating failure to build Source Package.
    """
    def __init__(self, *args, **kwargs):
        """
        Constructor of SourcePackageBuildError
        :param args: tuple of arguments stored in the exception instance
        :param kwargs: dictionary containing path to the logfile that contains main errors
        """
        super(SourcePackageBuildError, self).__init__()
        self.args = args
        self.logfile = kwargs.get('logfile')


class BinaryPackageBuildError(RuntimeError):
    """
    Error indicating failure to build Binary Package
    """
    def __init__(self, *args, **kwargs):
        """
        Constructor of BinaryPackageBuildError
        :param args: tuple of arguments stored in the exception instance
        :param kwargs: dictionary containing path to the logfile that contains main errors
        """
        super(BinaryPackageBuildError, self).__init__()
        self.args = args
        # Return code obtained from koji only at this time
        self.return_code = kwargs.get('return_code')
        self.logfile = kwargs.get('logfile')


class BuildTemporaryEnvironment(TemporaryEnvironment):
    """
    Class representing temporary environment.
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
        log_message = "Copying '%s' to '%s'"
        # create the directory structure
        self._create_directory_structure()
        # copy sources
        for source in self.sources:
            logger.debug(log_message, source, self._env[self.TEMPDIR_SOURCES])
            shutil.copy(source, self._env[self.TEMPDIR_SOURCES])
        # copy patches
        for patch in self.patches:
            logger.debug(log_message, patch, self._env[self.TEMPDIR_SOURCES])
            shutil.copy(patch, self._env[self.TEMPDIR_SOURCES])
        # copy SPEC file
        spec_name = os.path.basename(self.spec)
        self._env[self.TEMPDIR_SPEC] = os.path.join(self._env[self.TEMPDIR_SPECS], spec_name)
        shutil.copy(self.spec, self._env[self.TEMPDIR_SPEC])
        logger.debug(log_message, self.spec, self._env[self.TEMPDIR_SPEC])

        return obj

    def _create_directory_structure(self):
        """Function creating the directory structure in the TemporaryEnvironment."""
        raise NotImplementedError('The create directory function has to be implemented in child class!')

    def _build_env_exit_callback(self, results_dir, **kwargs):
        """
        The function that is called just before the destruction of the TemporaryEnvironment.
        It copies packages and logs into the results directory.

        :param results_dir: absolute path to results directory
        :return:
        """
        os.makedirs(results_dir)
        log_message = "Copying '%s' '%s' to '%s'"
        # copy logs
        for log in PathHelper.find_all_files(kwargs[self.TEMPDIR_RESULTS], '*.log'):
            logger.debug(log_message, 'log', log, results_dir)
            shutil.copy(log, results_dir)
        # copy packages
        for package in PathHelper.find_all_files(kwargs[self.TEMPDIR], '*.rpm'):
            logger.debug(log_message, 'package', package, results_dir)
            shutil.copy(package, results_dir)


class RpmbuildTemporaryEnvironment(BuildTemporaryEnvironment):
    """
    Class representing temporary environment for RpmbuildBuildTool.
    """

    TEMPDIR_RPMBUILD = TemporaryEnvironment.TEMPDIR + '_RPMBUILD'
    TEMPDIR_BUILD = TemporaryEnvironment.TEMPDIR + '_BUILD'
    TEMPDIR_BUILDROOT = TemporaryEnvironment.TEMPDIR + '_BUILDROOT'
    TEMPDIR_RPMS = TemporaryEnvironment.TEMPDIR + '_RPMS'
    TEMPDIR_SRPMS = TemporaryEnvironment.TEMPDIR + '_SRPMS'

    def _create_directory_structure(self):
        # create rpmbuild directory structure
        for dir_name in ['RESULTS', 'rpmbuild']:
            self._env[self.TEMPDIR + '_' + dir_name.upper()] = os.path.join(
                self._env[self.TEMPDIR], dir_name)
            logger.debug("Creating '%s'",
                         self._env[self.TEMPDIR + '_' + dir_name.upper()])
            os.makedirs(self._env[self.TEMPDIR + '_' + dir_name.upper()])
        for dir_name in ['BUILD', 'BUILDROOT', 'RPMS', 'SOURCES', 'SPECS',
                         'SRPMS']:
            self._env[self.TEMPDIR + '_' + dir_name] = os.path.join(
                self._env[self.TEMPDIR_RPMBUILD],
                dir_name)
            logger.debug("Creating '%s'",
                         self._env[self.TEMPDIR + '_' + dir_name])
            os.makedirs(self._env[self.TEMPDIR + '_' + dir_name])


class MockTemporaryEnvironment(BuildTemporaryEnvironment):
    """
    Class representing temporary environment for MockBuildTool.
    """

    def _create_directory_structure(self):
        # create directory structure
        for dir_name in ['SOURCES', 'SPECS', 'RESULTS']:
            self._env[self.TEMPDIR + '_' + dir_name] = os.path.join(
                self._env[self.TEMPDIR], dir_name)
            logger.debug("Creating '%s'",
                         self._env[self.TEMPDIR + '_' + dir_name])
            os.makedirs(self._env[self.TEMPDIR + '_' + dir_name])


class BuildToolBase(Plugin):
    """Build tool base class.

    Attributes:
        DEFAULT(bool): If True, the build tool is default tool.
        ACCEPTS_OPTIONS(bool): If True, the build tool accepts additional
            options passed via --builder-options.
        CREATES_TASKS(bool): If True, the build tool creates remote tasks.

    """

    DEFAULT = False
    ACCEPTS_OPTIONS = False
    CREATES_TASKS = False

    @classmethod
    def prepare(cls, spec, conf):
        """
        Prepare for building.

        :param spec: spec file object
        """
        # do nothing by default

    @classmethod
    def build(cls, spec, results_dir, srpm, **kwargs):
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

    @classmethod
    def get_logs(cls):
        """
        Get logs from previously failed build
        Returns:
        dict with
        'logs' -> list of absolute paths to logs
        """
        return dict(logs=getattr(cls, 'logs', None))

    @classmethod
    def wait_for_task(cls, build_dict, task_id, results_dir):  # pylint: disable=unused-argument
        """
        Waits until specified task is finished

        :param build_dict: build data
        :param results_dir: path to DIR where results should be stored
        :return: tuple with:
            list of absolute paths to RPMs
            list of absolute paths to logs
        """
        # do nothing by default
        return build_dict.get('rpm'), build_dict.get('logs')

    @classmethod
    def get_task_info(cls, build_dict):
        """
        Gets information about detached remote task

        :param build_dict: build data
        :return: task info
        """
        raise NotImplementedError()

    @classmethod
    def get_detached_task(cls, task_id, results_dir):
        """
        Gets packages and logs for specified task

        :param task_id: detached task id
        :param results_dir: path to DIR where results should be stored
        :return: tuple with:
            list of absolute paths to RPMs
            list of absolute paths to logs
        """
        raise NotImplementedError()

    @staticmethod
    def get_builder_options(**kwargs):
        builder_options = kwargs.get('builder_options')
        if builder_options:
            return shlex.split(builder_options)
        return None


class SRPMBuildToolBase(Plugin):
    """SRPM build tool base class.

    Attributes:
        DEFAULT(bool): If True, the build tool is default tool.

    """

    DEFAULT = False

    @staticmethod
    def get_srpm_builder_options(**kwargs):
        srpm_builder_options = kwargs.get('srpm_builder_options')
        if srpm_builder_options:
            return shlex.split(srpm_builder_options)
        return None

    @classmethod
    def get_logs(cls):
        """
        Get logs from previously failed build
        Returns:
        dict with
        'logs' -> list of absolute paths to logs
        """
        return dict(logs=getattr(cls, 'logs', None))

    @classmethod
    def build(cls, spec, results_dir, **kwargs):
        """
        Build SRPM with chosen SRPM Build Tool

        :param spec: SpecFile object
        :param results_dir: absolute path to DIR where results should be stored
        :return: absolute path to SRPM, list with absolute paths to logs
        """
        raise NotImplementedError()


class SRPMBuildHelper(object):
    def __init__(self):
        self.srpm_build_tools = PluginLoader.load('rebasehelper.srpm_build_tools')

    def get_all_tools(self):
        return list(self.srpm_build_tools)

    def get_supported_tools(self):
        return [k for k, v in six.iteritems(self.srpm_build_tools) if v]

    def get_default_tool(self):
        default = [k for k, v in six.iteritems(self.srpm_build_tools) if v and v.DEFAULT]
        return default[0] if default else None

    def get_tool(self, tool):
        try:
            return self.srpm_build_tools[tool]
        except KeyError:
            raise NotImplementedError('Unsupported SRPM build tool')


class BuildHelper(object):
    def __init__(self):
        self.build_tools = PluginLoader.load('rebasehelper.build_tools')

    def get_all_tools(self):
        return list(self.build_tools)

    def get_supported_tools(self):
        return [k for k, v in six.iteritems(self.build_tools) if v]

    def get_default_tool(self):
        default = [k for k, v in six.iteritems(self.build_tools) if v and v.DEFAULT]
        return default[0] if default else None

    def get_tool(self, tool):
        try:
            return self.build_tools[tool]
        except KeyError:
            raise NotImplementedError('Unsupported RPM build tool')


# Global instances of SRPMBuildHelper and BuildHelper. It is enough to load them once per application run.
srpm_build_helper = SRPMBuildHelper()
build_helper = BuildHelper()
