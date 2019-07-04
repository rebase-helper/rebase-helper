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

import os
import shutil

import pam  # type: ignore

from rebasehelper.helpers.path_helper import PathHelper
from rebasehelper.temporary_environment import TemporaryEnvironment
from rebasehelper.logger import logger


def check_mock_privileges() -> bool:
    # try to authenticate as superuser using mock PAM service
    return pam.pam().authenticate('root', '', service='mock')


class BuildTemporaryEnvironment(TemporaryEnvironment):
    """Class representing temporary environment."""

    TEMPDIR_SOURCES: str = TemporaryEnvironment.TEMPDIR + '_SOURCES'
    TEMPDIR_SPEC: str = TemporaryEnvironment.TEMPDIR + '_SPEC'
    TEMPDIR_SPECS: str = TemporaryEnvironment.TEMPDIR + '_SPECS'
    TEMPDIR_RESULTS: str = TemporaryEnvironment.TEMPDIR + '_RESULTS'

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
    """Class representing temporary environment for RpmbuildBuildTool."""

    TEMPDIR_RPMBUILD: str = TemporaryEnvironment.TEMPDIR + '_RPMBUILD'
    TEMPDIR_BUILD: str = TemporaryEnvironment.TEMPDIR + '_BUILD'
    TEMPDIR_BUILDROOT: str = TemporaryEnvironment.TEMPDIR + '_BUILDROOT'
    TEMPDIR_RPMS: str = TemporaryEnvironment.TEMPDIR + '_RPMS'
    TEMPDIR_SRPMS: str = TemporaryEnvironment.TEMPDIR + '_SRPMS'

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
    """Class representing temporary environment for MockBuildTool."""

    def _create_directory_structure(self):
        # create directory structure
        for dir_name in ['SOURCES', 'SPECS', 'RESULTS']:
            self._env[self.TEMPDIR + '_' + dir_name] = os.path.join(
                self._env[self.TEMPDIR], dir_name)
            logger.debug("Creating '%s'",
                         self._env[self.TEMPDIR + '_' + dir_name])
            os.makedirs(self._env[self.TEMPDIR + '_' + dir_name])
