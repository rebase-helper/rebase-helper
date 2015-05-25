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
import six

from rebasehelper.archive import Archive
from rebasehelper.specfile import SpecFile, get_rebase_name
from rebasehelper.logger import logger, LoggerHelper
from rebasehelper import settings
from rebasehelper import output_tool
from rebasehelper.utils import PathHelper, RpmHelper, ConsoleHelper, GitHelper
from rebasehelper.checker import Checker
from rebasehelper.build_helper import Builder, SourcePackageBuildError, BinaryPackageBuildError
from rebasehelper.patch_helper import Patcher
from rebasehelper.exceptions import RebaseHelperError
from rebasehelper.build_log_analyzer import BuildLogAnalyzer, BuildLogAnalyzerMissingError
from rebasehelper.base_output import OutputLogger
from rebasehelper.build_log_analyzer import BuildLogAnalyzerMakeError, BuildLogAnalyzerPatchError


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
    rebased_patches = {}

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

        self.kwargs['non_interactive'] = self.conf.non_interactive
        # if not continuing, check the results dir
        if not self.conf.cont and not self.conf.build_only:
            self._check_results_dir()
        # This is used if user executes rebase-helper with --continue
        # parameter even when directory does not exist
        if not os.path.exists(self.results_dir):
            os.makedirs(self.results_dir)

        self._add_debug_log_file()
        self._get_spec_file()
        self._prepare_spec_objects()

        # TODO: Remove the value from kwargs and use only CLI attribute!
        self.kwargs['continue'] = self.conf.cont
        self._initialize_data()

        # check the workspace dir
        if not self.conf.cont:
            self._check_workspace_dir()
        if self.conf.cont or self.conf.build_only:
            self._delete_old_builds()

    def _add_debug_log_file(self):
        """
        Add the application wide debug log file
        :return:
        """
        debug_log_file = os.path.join(self.results_dir, settings.REBASE_HELPER_DEBUG_LOG)
        try:
            LoggerHelper.add_file_handler(logger,
                                          debug_log_file,
                                          logging.Formatter("%(asctime)s %(levelname)s\t%(filename)s"
                                                            ":%(lineno)s %(funcName)s: %(message)s"),
                                          logging.DEBUG)
        except (IOError, OSError):
            logger.warning("Can not create debug log '%s'", debug_log_file)
        else:
            self.debug_log_file = debug_log_file

    def _prepare_spec_objects(self):
        """
        Prepare spec files and initialize objects
        :return:
        """
        self.rebase_spec_file_path = get_rebase_name(self.spec_file_path)

        self.spec_file = SpecFile(self.spec_file_path,
                                  self.execution_dir,
                                  download=not self.conf.not_download_sources)
        # Check whether test suite is enabled at build time
        if not self.spec_file.is_test_suite_enabled():
            OutputLogger.set_info_text('WARNING', 'Test suite is not enabled at build time.')
        #  create an object representing the rebased SPEC file
        self.rebase_spec_file = self.spec_file.copy(self.rebase_spec_file_path)

        #  check if argument passed as new source is a file or just a version
        if [True for ext in Archive.get_supported_archives() if self.conf.sources.endswith(ext)]:
            logger.debug("argument passed as a new source is a file")
            self.rebase_spec_file.set_version_using_archive(self.conf.sources)
        else:
            logger.debug("argument passed as a new source is a version")
            version, extra_version = SpecFile.split_version_string(self.conf.sources)
            self.rebase_spec_file.set_version(version)
            self.rebase_spec_file.set_extra_version(extra_version)

    def _initialize_data(self):
        """
        Function fill dictionary with default data
        """
        # Get all tarballs before self.kwargs initialization
        self.old_sources = self.spec_file.get_archive()
        new_sources = self.rebase_spec_file.get_archive()

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
        self.spec_file_path = PathHelper.find_first_file(self.execution_dir, '*.spec', 0)
        if not self.spec_file_path:
            raise RebaseHelperError("Could not find any SPEC file in the current directory '%s'", self.execution_dir)

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
        logger.debug("Removing the workspace directory '%s'", self.workspace_dir)
        shutil.rmtree(self.workspace_dir)

    def _check_workspace_dir(self):
        """
        Check if workspace dir exists, and removes it if yes.
        :return:
        """
        if os.path.exists(self.workspace_dir):
            logger.warning("Workspace directory '%s' exists, removing it", os.path.basename(self.workspace_dir))
            self._delete_workspace_dir()
        os.makedirs(self.workspace_dir)

    def _check_results_dir(self):
        """
        Check if  results dir exists, and removes it if yes.
        :return:
        """
        # TODO: We may not want to delete the directory in the future
        if os.path.exists(self.results_dir):
            logger.warning("Results directory '%s' exists, removing it", os.path.basename(self.results_dir))
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
            raise RebaseHelperError('%s. Supported archives are %s', ni_e.message, Archive.get_supported_archives())

        try:
            archive.extract(destination)
        except IOError:
            raise RebaseHelperError("Archive '%s' can not be extracted", archive_path)
        except (EOFError, SystemError):
            raise RebaseHelperError("Archive '%s' is damaged", archive_path)

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

    @staticmethod
    def check_build_requires(spec):
        """
        Check if all build dependencies are installed. If not, asks user they should be installed.
        If yes, it installs build dependencies using PolicyKit.
        :param spec: SpecFile object
        :return:
        """
        req_pkgs = spec.get_requires()
        if not RpmHelper.all_packages_installed(req_pkgs):
            if ConsoleHelper.get_message('\nSome build dependencies are missing. Do you want to install them now'):
                if RpmHelper.install_build_dependencies(spec.get_path()) != 0:
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
        git_helper = GitHelper(sources[0])
        git_helper.check_git_config()
        patch = Patcher(self.conf.patchtool)

        self.rebase_spec_file.update_changelog(self.rebase_spec_file.get_new_log(git_helper))
        try:
            self.rebased_patches = patch.patch(sources[0],
                                               sources[1],
                                               git_helper,
                                               self.spec_file.get_applied_patches(),
                                               **self.kwargs)
        except RuntimeError as run_e:
            raise RebaseHelperError(run_e.message)
        self.rebase_spec_file.write_updated_patches(self.rebased_patches)
        if self.conf.non_interactive:
            OutputLogger.set_patch_output('Unapplied patches:', self.rebased_patches['unapplied'])
        OutputLogger.set_patch_output('Patches:', self.rebased_patches)

    def build_packages(self):
        """
        Function calls build class for building packages
        """
        try:
            builder = Builder(self.conf.buildtool)
        except NotImplementedError as ni_e:
            raise RebaseHelperError('%s. Supported build tools are %s', ni_e.message, Builder.get_supported_tools())

        for version in ['old', 'new']:
            spec_object = self.spec_file if version == 'old' else self.rebase_spec_file
            build_dict = {}
            build_dict['name'] = spec_object.get_package_name()
            build_dict['version'] = spec_object.get_version()
            logger.debug(build_dict)
            patches = [x.get_path() for x in spec_object.get_patches()]
            results_dir = os.path.join(self.results_dir, version)
            spec = spec_object.get_path()
            sources = spec_object.get_sources()

            failed_before = False
            while True:
                try:
                    build_dict.update(builder.build(spec, sources, patches, results_dir, **build_dict))
                    OutputLogger.set_build_data(version, build_dict)
                    break

                except SourcePackageBuildError:
                    #  always fail for original version
                    if version == 'old':
                        raise RebaseHelperError('Creating old SRPM package failed.')
                    logger.error('Building source package failed.')
                    #  TODO: implement log analyzer for SRPMs and add the checks here!!!
                    raise

                except BinaryPackageBuildError:
                    #  always fail for original version
                    rpm_dir = os.path.join(results_dir, 'RPM')
                    build_log = 'build.log'
                    build_log_path = os.path.join(rpm_dir, build_log)
                    if version == 'old':
                        raise RebaseHelperError('Building old RPM package failed. Check log %s', build_log_path)
                    logger.error('Building binary packages failed.')
                    try:
                        files = BuildLogAnalyzer.parse_log(rpm_dir, build_log)
                    except BuildLogAnalyzerMissingError:
                        raise RebaseHelperError('Build log %s does not exist', build_log_path)
                    except BuildLogAnalyzerMakeError:
                        raise RebaseHelperError('Building package failed during build. Check log %s', build_log_path)
                    except BuildLogAnalyzerPatchError:
                        raise RebaseHelperError('Building package failed during patching. Check log %s' % build_log_path)

                    if files['missing']:
                        missing_files = '\n'.join(files['added'])
                        logger.info('Files not packaged in the SPEC file:\n%s', missing_files)
                    elif files['deleted']:
                        deleted_files = '\n'.join(files['deleted'])
                        logger.warning('Removed files packaged in SPEC file:\n%s', deleted_files)
                    else:
                        raise RebaseHelperError("Build failed, but no issues were found in the build log %s", build_log)
                    self.rebase_spec_file.modify_spec_files_section(files)

                if not self.conf.non_interactive:
                    if failed_before:
                        if not ConsoleHelper.get_message('Do you want rebase-helper to try build the packages one more time'):
                            raise KeyboardInterrupt
                else:
                    logger.warning('Some patches were not successfully applied')
                    shutil.rmtree(os.path.join(results_dir, 'RPM'))
                    shutil.rmtree(os.path.join(results_dir, 'SRPM'))
                    return False
                #  build just failed, otherwise we would break out of the while loop
                failed_before = True

                shutil.rmtree(os.path.join(results_dir, 'RPM'))
                shutil.rmtree(os.path.join(results_dir, 'SRPM'))
        return True

    def pkgdiff_packages(self):
        """
        Function calls pkgdiff class for comparing packages
        :return:
        """
        try:
            pkgchecker = Checker(self.conf.pkgcomparetool)
        except NotImplementedError:
            raise RebaseHelperError('You have to specify one of these check tools %s', Checker.get_supported_tools())
        else:
            logger.info('Comparing packages using %s...', self.conf.pkgcomparetool)
            results_dict = pkgchecker.run_check(self.results_dir)
            for key, val in six.iteritems(results_dict):
                if val:
                    OutputLogger.set_checker_output('Following files were ' + key, '\n'.join(val))

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
                Application.check_build_requires(self.spec_file)
            # Build packages
            build = self.build_packages()
            # Perform checks
            if build:
                self.pkgdiff_packages()

        # print summary information
        self.print_summary()

        if not self.conf.keep_workspace:
            self._delete_workspace_dir()

        if self.debug_log_file:
            logger.info("Detailed debug log is located in '%s'", self.debug_log_file)

if __name__ == '__main__':
    a = Application(None)
    a.run()
