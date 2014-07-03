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
from rebasehelper import settings, patch_helper, build_helper
from rebasehelper import output_tool
from rebasehelper.utils import get_value_from_kwargs, PathHelper
from rebasehelper.checker import Checker


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

        self._check_working_dirs()

        self._get_spec_file()
        self.spec_file = SpecFile(self.spec_file_path, self.conf.sources)

        self.kwargs['old'] = {}
        self.kwargs['new'] = {}
        self._initialize_data()

    def _initialize_data(self):
        """
        Function fill dictionary with default data
        """
        old_values = {}
        old_values['spec'] = self.spec_file_path
        self.kwargs['old'] = old_values
        self.kwargs['old'].update(self.spec_file.get_old_information())
        new_values = {}
        new_values['spec'] = self.spec_file.get_rebased_spec()
        self.kwargs['new'] = new_values
        self.kwargs['new'].update(self.spec_file.get_new_information())

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
        if os.path.exists(self.results_dir):
            logger.warning("'{0}' exists, removing...".format(self.results_dir))
            shutil.rmtree(self.results_dir)
        os.makedirs(self.results_dir)

        # TODO: We may not want to delete the directory in the future
        if os.path.exists(self.workspace_dir):
            logger.warning("'{0}' exists, removing...".format(self.workspace_dir))
            shutil.rmtree(self.workspace_dir)
        os.makedirs(self.workspace_dir)

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

    def build_packages(self):
        """
        Function calls build class for building packages
        """
        if not build_helper.check_build_argument(self.conf.buildtool):
            sys.exit(0)
        builder = build_helper.Builder(self.conf.buildtool)

        old_patches = get_value_from_kwargs(self.kwargs, settings.FULL_PATCHES)
        self.kwargs['old']['patches'] = [p[0] for p in old_patches.itervalues()]
        new_patches = get_value_from_kwargs(self.kwargs, settings.FULL_PATCHES, source='new')
        self.kwargs['new']['patches'] = [p[0] for p in new_patches.itervalues()]

        logger.info('Building packages using {0} ... running'.format(self.conf.buildtool))
        builder.build_packages(**self.kwargs)
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

        self.old_sources, new_sources = self.spec_file.get_tarballs()
        self.old_sources = os.path.abspath(self.old_sources)
        if new_sources:
            self.conf.sources = new_sources

        if not self.conf.sources:
            logger.error('You have to define a new sources.')
            sys.exit(1)
        else:
            self.new_sources = os.path.abspath(self.conf.sources)

        old_dir = Application.extract_sources(self.old_sources,
                                              os.path.join(self.workspace_dir, settings.OLD_SOURCES_DIR))
        new_dir = Application.extract_sources(self.new_sources,
                                              os.path.join(self.workspace_dir, settings.NEW_SOURCES_DIR))

        if not self.conf.build_only:
            # Patch sources
            if not patch_helper.check_difftool_argument(self.conf.difftool):
                sys.exit(1)
            self.kwargs['old_dir'] = old_dir
            self.kwargs['new_dir'] = new_dir
            self.kwargs['diff_tool'] = self.conf.difftool
            patch = patch_helper.Patch(self.conf.patchtool)
            try:
                self.kwargs['new']['patches'] = patch.patch(**self.kwargs)
            except Exception as e:
                logger.error(e.message)
                sys.exit(1)

            update_patches = self.spec_file.write_updated_patches(**self.kwargs)
            self.kwargs['summary_info'] = update_patches
            if self.conf.patch_only:
                self.print_summary()
                sys.exit(0)
        # Build packages
        self.build_packages()

        # Perform checks
        self.pkgdiff_packages()

        # print summary information
        self.print_summary()


if __name__ == '__main__':
    a = Application(None)
    a.run()
