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
import os
import shutil
import logging

from rebasehelper.archive import Archive
from rebasehelper.specfile import SpecFile, get_rebase_name
from rebasehelper.logger import logger, LoggerHelper
from rebasehelper import settings
from rebasehelper import output_tool
from rebasehelper.utils import get_value_from_kwargs, PathHelper, RpmHelper, get_message
from rebasehelper.checker import Checker
from rebasehelper.build_helper import Builder
from rebasehelper.patch_helper import Patch
from rebasehelper.exceptions import RebaseHelperError
from rebasehelper.build_log_analyzer import BuildLogAnalyzer
from rebasehelper.base_output import OutputLogger


class Application(object):
    result_file = ""
    temp_dir = ""
    kwargs = {}
    old_sources = ""
    new_sources = ""
    spec_file = None
    spec_file_path = None
    rebase_spec_file = None
    rebase_spec_file_path = None
    debug_log_file = None

    def __init__(self, cli_conf=None):
        """
        Initialize the application

        :param cli_conf: CLI object with configuration gathered from commandline
        :return:
        """
        self.conf = cli_conf

        if self.conf.verbose:
            LoggerHelper.add_stream_handler(logger, logging.DEBUG)
        else:
            LoggerHelper.add_stream_handler(logger, logging.INFO)

        # The directory in which rebase-helper was executed
        self.execution_dir = os.getcwd()
        # Temporary workspace for Builder, checks, ...
        self.kwargs['workspace_dir'] = self.workspace_dir = os.path.join(self.execution_dir,
                                                                         settings.REBASE_HELPER_WORKSPACE_DIR)
        # Directory where results should be put
        self.kwargs['results_dir'] = self.results_dir = os.path.join(self.execution_dir,
                                                                     settings.REBASE_HELPER_RESULTS_DIR)

        # if not continuing, check the results dir
        if not self.conf.cont and not self.conf.build_only:
            self._check_results_dir()

        self._add_debug_log_file()
        self._get_spec_file()
        self._prepare_spec_objects()

        self.kwargs['old'] = {}
        self.kwargs['new'] = {}
        # TODO: Remove the value from kwargs and use only CLI attribute!
        self.kwargs['continue'] = self.conf.cont
        self._initialize_data()

        # check the workspace dir
        self._check_workspace_dir()
        if self.conf.build_only:
            self._delete_old_builds()
            self._find_old_data()

    def _add_debug_log_file(self):
        """
        Add the application wide debug log file
        :return:
        """
        debug_log_file = os.path.join(self.results_dir, settings.REBASE_HELPER_DEBUG_LOG)
        try:
            LoggerHelper.add_file_handler(logger,
                                          debug_log_file,
                                          logging.Formatter("%(asctime)s %(levelname)s %(message)s"),
                                          logging.DEBUG)
        except (IOError, OSError):
            logger.warning("Can not create debug log '{0}'".format(debug_log_file))
        else:
            self.debug_log_file = debug_log_file

    def _prepare_spec_objects(self):
        """
        Prepare spec files and initialize objects
        :return:
        """
        self.rebase_spec_file_path = get_rebase_name(self.spec_file_path)

        self.spec_file = SpecFile(self.spec_file_path,
                                  download=not self.conf.not_download_sources)
        #  create an object representing the rebased SPEC file
        self.rebase_spec_file = self.spec_file.copy(self.rebase_spec_file_path)
        #  check if argument passed as new source is a file or just a version
        if os.path.isfile(os.path.join(self.execution_dir, self.conf.sources)):
            logger.debug("Application: argument passed as a new source is a file")
            self.rebase_spec_file.set_version_using_archive(self.conf.sources)
        else:
            logger.debug("Application: argument passed as a new source is a version")
            self.rebase_spec_file.set_version(self.conf.sources)

        self.kwargs['file_list'] = self.spec_file.get_combined_files_sections()

    def _find_old_data(self):
        """
        Function find data previously done
        """
        new_patches = self.kwargs['new'][settings.FULL_PATCHES]
        for file_name in PathHelper.find_all_files(self.kwargs.get('results_dir', ''), '*.patch'):
            for key, value in new_patches.items():
                if os.path.basename(file_name) in value[0]:
                    value[0] = file_name
                    break
        self.kwargs['new']['patches'] = self.kwargs['new'][settings.FULL_PATCHES]
        update_patches = self.spec_file.write_updated_patches(**self.kwargs)
        self.kwargs['summary_info'] = update_patches
        OutputLogger.set_patch_output('Patches:', update_patches)

    def _initialize_data(self):
        """
        Function fill dictionary with default data
        """
        # Get all tarballs before self.kwargs initialization
        self.old_sources = self.spec_file.get_archive()
        new_sources = self.rebase_spec_file.get_archive()

        # Fill self.kwargs with related items
        old_values = {}
        old_values['spec'] = self.spec_file_path
        self.kwargs['old'] = old_values
        self.kwargs['old'].update(self.spec_file.get_information())

        # Fill self.kwargs with related items
        new_values = {}
        new_values['spec'] = self.rebase_spec_file_path
        self.kwargs['new'] = new_values
        self.kwargs['new'].update(self.rebase_spec_file.get_information())
        self.old_sources = os.path.abspath(self.old_sources)
        if new_sources:
            self.conf.sources = new_sources

        if not self.conf.sources:
            raise RebaseHelperError('You have to define new sources.')
        else:
            self.new_sources = os.path.abspath(self.conf.sources)

    def _get_rebase_helper_log(self):
        return os.path.join(self.results_dir, settings.REBASE_HELPER_RESULTS_LOG)

    def _get_spec_file(self):
        """
        Function gets the spec file from the execution_dir directory
        """
        self.spec_file_path = PathHelper.find_first_file(self.execution_dir, '*.spec')

        if not self.spec_file_path:
            raise RebaseHelperError("Could not find any SPEC file in the current directory '{0}'".format(
                self.execution_dir))

    def _delete_old_builds(self):
        """
        Deletes the old and new result dir from previous build
        :return:
        """
        self._delete_new_results_dir()
        self._delete_old_results_dir()

    def _delete_old_results_dir(self):
        """
        Deletes old result dir
        :return:
        """
        if os.path.isdir(os.path.join(self.results_dir, 'old')):
            shutil.rmtree(os.path.join(self.results_dir, 'old'))

    def _delete_new_results_dir(self):
        """
        Deletes new result dir
        :return:
        """
        if os.path.isdir(os.path.join(self.results_dir, 'new')):
            shutil.rmtree(os.path.join(self.results_dir, 'new'))

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
        except NotImplementedError as ni_e:
            raise RebaseHelperError('{0}. Supported archives are {1}'.format(
                ni_e.message, Archive.get_supported_archives()))

        try:
            archive.extract(destination)
        except IOError:
            raise RebaseHelperError("Archive '{0}' can not be extracted".format(archive_path))

    @staticmethod
    def extract_sources(archive_path, destination):
        """
        Function extracts a given Archive and returns a full dirname to sources
        """
        Application.extract_archive(archive_path, destination)

        try:
            sources_dir = os.listdir(destination)[0]
        except IndexError:
            raise RebaseHelperError('Extraction of sources failed!')

        return os.path.join(destination, sources_dir)

    def check_build_requires(self, spec):
        """
        Check if all build dependencies are installed. If not, asks user they should be installed.
        If yes, it installs build dependencies using PolicyKit.
        :param spec: SpecFile object
        :return:
        """
        req_pkgs = spec.get_requires()
        if not RpmHelper.all_packages_installed(req_pkgs):
            if get_message('\nSome build dependencies are missing. Do you want to install them now? (y/n) ') in ['y', 'yes']:
                if RpmHelper.install_build_dependencies(spec.spec_file) != 0:
                    raise RebaseHelperError('Failed to install build dependencies')

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
        self.kwargs['old_dir'] = sources[0]
        self.kwargs['new_dir'] = sources[1]
        self.kwargs['diff_tool'] = self.conf.difftool
        patch = Patch(self.conf.patchtool)

        try:
            self.kwargs['new']['patches'] = patch.patch(**self.kwargs)
        except RuntimeError as run_e:
            raise RebaseHelperError(run_e.message)

        update_patches = self.rebase_spec_file.write_updated_patches(**self.kwargs)
        self.kwargs['summary_info'] = update_patches
        OutputLogger.set_patch_output('Patches:', update_patches)

    def build_packages(self):
        """
        Function calls build class for building packages
        """
        try:
            builder = Builder(self.conf.buildtool)
        except NotImplementedError as ni_e:
            raise RebaseHelperError('{0}. Supported build tools are {1}'.format(
                ni_e.message, Builder.get_supported_tools()))

        for version in ['old', 'new']:
            patches = get_value_from_kwargs(self.kwargs, settings.FULL_PATCHES, source=version)
            build_dict = self.kwargs[version]
            build_dict['patches'] = [p[0] for p in patches.itervalues()]
            build_dict['results_dir'] = os.path.join(self.results_dir, version)

            build_test = 0
            results_dir = build_dict.get('results_dir', '')
            build_success = False
            while int(build_test) < 10:
                try:
                    build_dict.update(builder.build(**build_dict))
                    build_test = 99
                    build_success = True
                    OutputLogger.set_build_data(version, build_dict)
                except RuntimeError as run_e:
                    logger.debug('Build failed {0}. {1}'.format(build_test, run_e.message))
                    build_log = os.path.join(results_dir, 'RPM'), 'build.log'
                    files = BuildLogAnalyzer.parse_log(os.path.join(results_dir, 'RPM'), 'build.log')
                    if not files['missing'] and not files['obsoletes']:
                        raise RebaseHelperError("Rebase helper didn't find any trouble in {0} file".format(build_log))
                    if files['missing']:
                        logger.warning('Following files are missing in {spec} file:\n{f}.'.
                                       format(f='\n'.join(files['missing']),
                                              spec=build_dict.get('spec')))
                    if files['obsoletes']:
                        logger.warning('Following files are obsoletes in sources: \n{f}'.
                                       format(f='\n'.join(files['obsoletes'])))
                    shutil.rmtree(results_dir)
                    if version == 'old':
                        self.spec_file.modify_spec_files_section(files)
                    else:
                        self.rebase_spec_file.modify_spec_files_section(files)
                    build_test += 1
            if build_success:
                logger.info('Building packages done')
            else:
                raise RebaseHelperError("Rebase-helper builds package several time and it's still failing. "
                                        "Look at the logs")

    def pkgdiff_packages(self):
        """
        Function calls pkgdiff class for comparing packages
        :return:
        """
        try:
            pkgchecker = Checker(self.conf.pkgcomparetool)
        except NotImplementedError:
            raise RebaseHelperError('You have to specify one of these check tools {0}'.format(
                Checker.get_supported_tools()))
        else:
            logger.info('Comparing packages using {0} ... running'.format(self.conf.pkgcomparetool))
            results = pkgchecker.run_check(**self.kwargs)
            OutputLogger.set_checker_output(self.conf.pkgcomparetool, results)
            logger.info('Comparing packages done')

    def print_summary(self):
        output_tool.check_output_argument(self.conf.outputtool)
        output = output_tool.OutputTool(self.conf.outputtool)
        output.print_information(path=self._get_rebase_helper_log())

    def run(self):
        sources = self.prepare_sources()

        if not self.conf.build_only:
            self.patch_sources(sources)

        if not self.conf.patch_only:
            # check build dependencies for rpmbuild
            if self.conf.buildtool == 'rpmbuild':
                self.check_build_requires(self.spec_file)
            # Build packages
            self.build_packages()
            # Perform checks
            self.pkgdiff_packages()

        # print summary information
        self.print_summary()

        if not self.conf.keep_workspace:
            self._delete_workspace_dir()

        if self.debug_log_file:
            logger.info("Detailed debug log is located in '{0}'".format(self.debug_log_file))

if __name__ == '__main__':
    a = Application(None)
    a.run()
