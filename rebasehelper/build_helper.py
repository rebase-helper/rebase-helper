# -*- coding: utf-8 -*-
#
# This tool helps you to rebase package to the latest version
# Copyright (C) 2013-2014 Red Hat, Inc.
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
# Authors: Petr Hracek <phracek@redhat.com>
#          Tomas Hozza <thozza@redhat.com>

import shlex
import shutil
import os

import six
import pkg_resources

from rebasehelper.utils import PathHelper
from rebasehelper.utils import TemporaryEnvironment
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


class BuildToolBase(object):
    """
    Base class for various build tools
    """

    DEFAULT = False

    @classmethod
    def match(cls, cmd=None):
        """Checks if tool name matches the desired one."""
        raise NotImplementedError()

    @classmethod
    def get_build_tool_name(cls):
        """Returns the name of the build tool."""
        raise NotImplementedError()

    @classmethod
    def is_default(cls):
        """Checks if the tool is the default build tool."""
        raise NotImplementedError()

    @classmethod
    def accepts_options(cls):
        """Checks if the tool accepts additional command line options."""
        raise NotImplementedError()

    @classmethod
    def creates_tasks(cls):
        """Checks if the tool creates build tasks."""
        raise NotImplementedError()

    @classmethod
    def prepare(cls, spec, conf):
        """
        Prepare for building.

        :param spec: spec file object
        """
        # do nothing by default
        pass

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


class SRPMBuildToolBase(object):
    """
    Base class for SRPM builder tools
    """

    DEFAULT = False

    @classmethod
    def get_build_tool_name(cls):
        """Returns name of the SRPM Build Tool"""
        return NotImplementedError()

    @classmethod
    def is_default(cls):
        """Returns true if the SRPM Build Tool is set to be default"""
        return NotImplementedError()

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


class SRPMBuilder(object):
    """
    Builder class for building SRPMs.
    """

    srpm_build_tools = {}

    def __init__(self, tool=None):
        if tool is None:
            raise TypeError("Expected argument 'tool' (pos 1) is missing")
        self._tool_name = tool
        self._tool = None

        for build_tool in self.srpm_build_tools.values():
            if build_tool.get_build_tool_name() == self._tool_name:
                self._tool = build_tool

        if self._tool is None:
            raise NotImplementedError("Unsupported SRPM build tool")

    def __str__(self):
        return "<SRPM Builder tool_name='{_tool_name}' tool='{_tool}'>".format(**vars(self))

    @classmethod
    def load_srpm_build_tools(cls):
        for entrypoint in pkg_resources.iter_entry_points('rebasehelper.srpm_build_tools'):
            try:
                srpm_build_tool = entrypoint.load()
            except ImportError:
                # silently skip broken plugin
                continue
            try:
                cls.srpm_build_tools[srpm_build_tool.get_build_tool_name()] = srpm_build_tool
            except (AttributeError, NotImplementedError):
                # silently skip broken plugin
                continue

    def get_logs(self):
        """Get logs."""
        logger.debug("Getting logs '%s'", self._tool_name)
        return self._tool.get_logs()

    def build(self, *args, **kwargs):
        logger.debug("Building SRPM using '%s'", self._tool_name)
        return self._tool.build(*args, **kwargs)

    @classmethod
    def get_supported_tools(cls):
        """Returns list of supported srpm build tools"""
        return cls.srpm_build_tools.keys()

    @classmethod
    def get_default_tool(cls):
        """Returns default build tool"""
        default = [k for k, v in six.iteritems(cls.srpm_build_tools) if v.is_default()]
        return default[0] if default else None


class Builder(object):
    """
    Class representing a process of building binaries from sources.
    """

    build_tools = {}

    @classmethod
    def load_build_tools(cls):
        cls.build_tools = {}
        for entrypoint in pkg_resources.iter_entry_points('rebasehelper.build_tools'):
            try:
                build_tool = entrypoint.load()
            except ImportError:
                # silently skip broken plugin
                continue
            try:
                cls.build_tools[build_tool.get_build_tool_name()] = build_tool
            except (AttributeError, NotImplementedError):
                # silently skip broken plugin
                continue

    def __init__(self, tool=None):
        if tool is None:
            raise TypeError("Expected argument 'tool' (pos 1) is missing")
        self._tool_name = tool
        self._tool = None

        for build_tool in self.build_tools.values():
            if build_tool.match(self._tool_name):
                self._tool = build_tool

        if self._tool is None:
            raise NotImplementedError("Unsupported build tool")

    def __str__(self):
        return "<Builder tool_name='{_tool_name}' tool='{_tool}'>".format(**vars(self))

    def accepts_options(self):
        return self._tool.accepts_options()

    def creates_tasks(self):
        return self._tool.creates_tasks()

    def prepare(self, spec, conf):
        """Prepare for build"""
        logger.debug("Preparing for build using '%s'", self._tool_name)
        self._tool.prepare(spec, conf)

    def build(self, *args, **kwargs):
        """Build sources."""
        logger.debug("Building RPMs using '%s'", self._tool_name)
        return self._tool.build(*args, **kwargs)

    def get_logs(self):
        """Get logs."""
        logger.debug("Getting logs '%s'", self._tool_name)
        return self._tool.get_logs()

    def wait_for_task(self, build_dict, task_id, results_dir):
        """Wait for task"""
        logger.debug("Waiting for task using '%s'", self._tool_name)
        return self._tool.wait_for_task(build_dict, task_id, results_dir)

    def get_task_info(self, build_dict):
        """Get task info"""
        logger.debug("Getting task info using '%s'", self._tool_name)
        return self._tool.get_task_info(build_dict)

    def get_detached_task(self, task_id, results_dir):
        """Get detached task"""
        logger.debug("Getting detached task using '%s'", self._tool_name)
        return self._tool.get_detached_task(task_id, results_dir)

    @classmethod
    def get_supported_tools(cls):
        """
        Returns a list of supported build tools

        :return: list of supported build tools
        """
        return cls.build_tools.keys()

    @classmethod
    def get_default_tool(cls):
        """Returns default build tool"""
        default = [k for k, v in six.iteritems(cls.build_tools) if v.is_default()]
        return default[0] if default else None


SRPMBuilder.load_srpm_build_tools()
Builder.load_build_tools()
