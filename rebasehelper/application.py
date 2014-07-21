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

import os
import sys
import shutil
import logging

from rebasehelper.archive import Archive
from rebasehelper.specfile import SpecFile
from rebasehelper.logger import logger
from rebasehelper import settings, patch_helper
from rebasehelper import output_tool
from rebasehelper.utils import get_value_from_kwargs, PathHelper
from rebasehelper.checker import Checker
from rebasehelper.build_helper import Builder


class Application(object):
    result_file = ""
    temp_dir = ""
    kwargs = {}
    old_sources = ""
    new_sources = ""
    spec_file = None
    spec_file_path = None

    def __init__(self, cli_conf=None):
        """
        Initialize the application

        :param cli_conf: CLI object with configuration gathered from commandline
        :return:
        """
        self.conf = cli_conf
        # The directory in which rebase-helper was executed
        self.execution_dir = os.getcwd()
        # Temporary workspace for Builder, checks, ...
        self.kwargs['workspace_dir'] = self.workspace_dir = os.path.join(self.execution_dir,
                                                                         settings.REBASE_HELPER_WORKSPACE_DIR)
        # Directory where results should be put
        self.kwargs['results_dir'] = self.results_dir = os.path.join(self.execution_dir,
                                                                     settings.REBASE_HELPER_RESULTS_DIR)

        # check the workspace dir
        self._check_workspace_dir()
        # if not continuing, check the results dir
        if not self.conf.cont:
            self._check_results_dir()

        self._get_spec_file()
        self.spec_file = SpecFile(self.spec_file_path, self.conf.sources, download=not self.conf.not_download_sources)
        self.kwargs['old'] = {}
        self.kwargs['new'] = {}
        # TODO: Remove the value from kwargs and use only CLI attribute!
        self.kwargs['continue'] = self.conf.cont
        self._initialize_data()

        if self.conf.cont:
            self.kwargs['new']['patches'] = self._find_old_data()

    def _find_old_data(self):
        """
        Function find data previously done
        """
        patches = []
        for file_name in PathHelper.find_all_files(self.kwargs.get('results_dir', ''), '*.patch'):
            patches.append(file_name)
        return patches

    def _initialize_data(self):
        """
        Function fill dictionary with default data
        """
        # Get all tarballs before self.kwargs initialization
        self.old_sources, new_sources = self.spec_file.get_tarballs()

        # Fill self.kwargs with related items
        old_values = {}
        old_values['spec'] = self.spec_file_path
        self.kwargs['old'] = old_values
        self.kwargs['old'].update(self.spec_file.get_old_information())

        # Fill self.kwargs with related items
        new_values = {}
        new_values['spec'] = self.spec_file.get_rebased_spec()
        self.kwargs['new'] = new_values
        self.kwargs['new'].update(self.spec_file.get_new_information())
        self.old_sources = os.path.abspath(self.old_sources)
        if new_sources:
            self.conf.sources = new_sources

        if not self.conf.sources:
            raise ValueError('You have to define new sources.')
        else:
            self.new_sources = os.path.abspath(self.conf.sources)

    def _get_spec_file(self):
        """
        Function gets the spec file from the execution_dir directory
        """
        self.spec_file_path = PathHelper.find_first_file(self.execution_dir, '*.spec')

        if not self.spec_file_path:
            raise IOError("Could not find any SPEC file in the current directory '{0}'".format(self.execution_dir))

    def _delete_workspace_dir(self):
        """
        Deletes workspace directory and loggs message
        :return:
        """
        logger.debug("Removing the workspace directory '{0}'".format(self.workspace_dir))
        shutil.rmtree(self.workspace_dir)

    def _check_workspace_dir(self):
        """
        Check if workspace dir exists, and removes it if yes.
        :return:
        """
        if os.path.exists(self.workspace_dir):
            logger.warning("Workspace directory '{0}' exists, removing it".format(os.path.basename(self.workspace_dir)))
            self._delete_workspace_dir()
        os.makedirs(self.workspace_dir)

    def _check_results_dir(self):
        """
        Check if  results dir exists, and removes it if yes.
        :return:
        """
        # TODO: We may not want to delete the directory in the future
        if os.path.exists(self.results_dir):
            logger.warning("Results directory '{0}' exists, removing it".format(os.path.basename(self.results_dir)))
            shutil.rmtree(self.results_dir)
        os.makedirs(self.results_dir)

    @staticmethod
    def extract_archive(archive_path, destination):
        """
        Extracts given archive into the destination and handle all exceptions.

        :param archive_path: path to the archive to be extracted
        :param destination: path to a destination, where the archive should be extracted to
        :return:
        """
        try:
            archive = Archive(archive_path)
        except NotImplementedError as e:
            raise NotImplementedError('{0}. Supported archives are {1}'.format(
                e.message, Archive.get_supported_archives()))

        try:
            archive.extract(destination)
        except IOError:
            raise IOError("Archive '{0}' can not be extracted".format(archive_path))

    @staticmethod
    def extract_sources(archive_path, destination):
        """
        Function extracts a given Archive and returns a full dirname to sources
        """
        Application.extract_archive(archive_path, destination)

        try:
            sources_dir = os.listdir(destination)[0]
        except IndexError:
            raise RuntimeError('Extraction of sources failed!')

        return os.path.join(destination, sources_dir)

    def prepare_sources(self):
        """
        Function prepares a sources.
        :return:
        """
        old_dir = Application.extract_sources(self.old_sources,
                                              os.path.join(self.execution_dir, settings.OLD_SOURCES_DIR))
        new_dir = Application.extract_sources(self.new_sources,
                                              os.path.join(self.execution_dir, settings.NEW_SOURCES_DIR))

        return [old_dir, new_dir]

    def patch_sources(self, sources):
        # Patch sources
        # TODO: WTF??
        if not patch_helper.check_difftool_argument(self.conf.difftool):
            sys.exit(1)
        self.kwargs['old_dir'] = sources[0]
        self.kwargs['new_dir'] = sources[1]
        self.kwargs['diff_tool'] = self.conf.difftool
        patch = patch_helper.Patch(self.conf.patchtool)

        self.kwargs['new']['patches'] = patch.patch(**self.kwargs)

        update_patches = self.spec_file.write_updated_patches(**self.kwargs)
        self.kwargs['summary_info'] = update_patches

    def build_packages(self):
        """
        Function calls build class for building packages
        """
        try:
            builder = Builder(self.conf.buildtool)
        except NotImplementedError as e:
            raise NotImplementedError('{0}. Supported build tools are {1}'.format(
                e.message, Builder.get_supported_tools()))

        old_patches = get_value_from_kwargs(self.kwargs, settings.FULL_PATCHES)
        self.kwargs['old']['patches'] = [p[0] for p in old_patches.itervalues()]
        new_patches = get_value_from_kwargs(self.kwargs, settings.FULL_PATCHES, source='new')
        self.kwargs['new']['patches'] = [p[0] for p in new_patches.itervalues()]

        builder.build_packages(**self.kwargs)
        logger.info('Building packages done')

    def pkgdiff_packages(self):
        """
        Function calls pkgdiff class for comparing packages
        :return:
        """
        try:
            pkgchecker = Checker(self.conf.pkgcomparetool)
        except NotImplementedError:
            raise NotImplementedError('You have to specify one of these check tools {0}'.format(
                Checker.get_supported_tools()))
        else:
            logger.info('Comparing packages using {0} ... running'.format(self.conf.pkgcomparetool))
            self.kwargs['pkgcompareinfo'] = pkgchecker.run_check(**self.kwargs)
            logger.info('Comparing packages done')

    def print_summary(self):
        output_tool.check_output_argument(self.conf.outputtool)
        output = output_tool.OutputTool(self.conf.outputtool)
        output.print_information(**self.kwargs)

    def run(self):
        if self.conf.verbose:
            logger.setLevel(logging.DEBUG)

        sources = self.prepare_sources()

        if not self.conf.build_only:
            self.patch_sources(sources)

        if not self.conf.patch_only:
            # Build packages
            self.build_packages()
            # Perform checks
            self.pkgdiff_packages()

        # print summary information
        self.print_summary()

        if not self.conf.keep_workspace:
            self._delete_workspace_dir()


if __name__ == '__main__':
    a = Application(None)
    a.run()
