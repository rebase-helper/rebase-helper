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
        self.kwargs['continue'] = 0

        args_dict = vars(self.conf.args)
        if not args_dict.get('continue', 0):
            self._check_working_dirs()

        self._get_spec_file()
        self.spec_file = SpecFile(self.spec_file_path, self.conf.sources, download=not self.conf.not_download_sources)
        self.kwargs['old'] = {}
        self.kwargs['new'] = {}
        self._initialize_data()
        if args_dict.get('continue'):
            # Cleaning sources directories
            old_sources = os.path.join(self.execution_dir, settings.OLD_SOURCES_DIR)
            if os.path.exists(old_sources):
                shutil.rmtree(old_sources)
            new_sources = os.path.join(self.execution_dir, settings.NEW_SOURCES_DIR)
            if os.path.exists(new_sources):
                shutil.rmtree(new_sources)
            self.kwargs['continue'] = args_dict.get('continue')
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
            logger.error('You have to define a new sources.')
            sys.exit(1)
        else:
            self.new_sources = os.path.abspath(self.conf.sources)

    def _get_spec_file(self):
        """
        Function gets the spec file from the execution_dir directory
        """
        self.spec_file_path = PathHelper.find_first_file(self.execution_dir, '*.spec')

        if not self.spec_file_path:
            logger.error("Could not find any SPEC file in the current directory '{0}'".format(self.execution_dir))
            sys.exit(1)

    def _check_working_dirs(self):
        """
        Check if workspace and results dir exist, and remove them if yes.
        :return:
        """
        # TODO: We may not want to delete the directory in the future
        if os.path.exists(self.results_dir):
            logger.warning("Results directory '{0}' exists, removing it".format(os.path.basename(self.results_dir)))
            shutil.rmtree(self.results_dir)
        os.makedirs(self.results_dir)

        if os.path.exists(self.workspace_dir):
            logger.warning("Workspace direcotry '{0}' exists, removing it".format(os.path.basename(self.workspace_dir)))
            shutil.rmtree(self.workspace_dir)
        os.makedirs(self.workspace_dir)

    def _delete_workspace_dir(self):
        """
        Deletes workspace directory and loggs message
        :return:
        """
        logger.debug("Removing the workspace directory '{0}'".format(self.workspace_dir))
        shutil.rmtree(self.workspace_dir)

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
            logger.error("{0}, '{1}'".format(e.message, archive_path))
            logger.error("Supported archive types are '{0}'".format(str(Archive.get_supported_archives())))
            sys.exit(1)

        try:
            archive.extract(destination)
        except IOError as e:
            logger.error("Archive '{0}' can not be extracted: '{1}'".format(archive_path, e.message))
            sys.exit(1)

    @staticmethod
    def extract_sources(archive_path, destination):
        """
        Function extracts a given Archive and returns a full dirname to sources
        """
        Application.extract_archive(archive_path, destination)

        try:
            sources_dir = os.listdir(destination)[0]
        except IndexError:
            # TODO Maybe we should raise a RuntimeError
            sources_dir = ""

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
        return_value = None
        if not patch_helper.check_difftool_argument(self.conf.difftool):
            sys.exit(1)
        self.kwargs['old_dir'] = sources[0]
        self.kwargs['new_dir'] = sources[1]
        self.kwargs['diff_tool'] = self.conf.difftool
        patch = patch_helper.Patch(self.conf.patchtool)
        try:
            self.kwargs['new']['patches'] = patch.patch(**self.kwargs)
        except Exception as e:
            logger.error(e.message)
            return_value = 1

        update_patches = self.spec_file.write_updated_patches(**self.kwargs)
        self.kwargs['summary_info'] = update_patches
        if self.conf.patch_only:
            # TODO: We should solve the run path somehow better to not duplicate code
            self.print_summary()
            if not self.conf.keep_workspace:
                self._delete_workspace_dir()
            return_value = 0
        return return_value

    def build_packages(self):
        """
        Function calls build class for building packages
        """
        try:
            builder = Builder(self.conf.buildtool)
        except NotImplementedError as e:
            logger.error("{0}, '{1}'".format(e.message, self.conf.buildtool))
            logger.error("Supported build tools are '{0}'".format(str(Builder.get_supported_tools())))
            sys.exit(1)

        old_patches = get_value_from_kwargs(self.kwargs, settings.FULL_PATCHES)
        self.kwargs['old']['patches'] = [p[0] for p in old_patches.itervalues()]
        new_patches = get_value_from_kwargs(self.kwargs, settings.FULL_PATCHES, source='new')
        self.kwargs['new']['patches'] = [p[0] for p in new_patches.itervalues()]

        try:
            builder.build_packages(**self.kwargs)
        except RuntimeError:
            # Building failed
            sys.exit(1)
        logger.info('Building package done')

    def pkgdiff_packages(self):
        """
        Function calls pkgdiff class for comparing packages
        :return:
        """
        try:
            pkgchecker = Checker(self.conf.pkgcomparetool)
        except NotImplementedError:
            logger.error('You have to specify one of these check tools {0}'.format(Checker.get_supported_tools()))
            sys.exit(1)
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
            return_value = self.patch_sources(sources)
            if return_value is not None:
                sys.exit(return_value)

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
