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
from rebasehelper.logger import logger, logger_report, LoggerHelper
from rebasehelper import settings
from rebasehelper import output_tool
from rebasehelper.utils import PathHelper, RpmHelper, ConsoleHelper, GitHelper
from rebasehelper.checker import Checker
from rebasehelper.build_helper import Builder, SourcePackageBuildError, BinaryPackageBuildError, koji_builder
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
    rest_sources = []
    new_sources = ""
    spec_file = None
    spec_file_path = None
    rebase_spec_file = None
    rebase_spec_file_path = None
    debug_log_file = None
    report_log_file = None
    rebased_patches = {}
    upstream_monitoring = False

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
        if not self.conf.cont and not self.conf.build_only and not self.conf.comparepkgs:
            self._check_results_dir()
        # This is used if user executes rebase-helper with --continue
        # parameter even when directory does not exist
        if not os.path.exists(self.results_dir):
            os.makedirs(self.results_dir)
            os.makedirs(os.path.join(self.results_dir, settings.REBASE_HELPER_LOGS))

        self._add_debug_log_file()
        self._add_report_log_file()
        self._get_spec_file()
        self._prepare_spec_objects()

        # check the workspace dir
        if not self.conf.cont:
            self._check_workspace_dir()

        # TODO: Remove the value from kwargs and use only CLI attribute!
        self.kwargs['continue'] = self.conf.cont
        self._initialize_data()

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

    def _add_report_log_file(self):
        """
        Add the application report log file
        :return:
        """
        report_log_file = os.path.join(self.results_dir, settings.REBASE_HELPER_REPORT_LOG)
        try:
            LoggerHelper.add_file_handler(logger_report,
                                          report_log_file,
                                          None,
                                          logging.INFO)
        except (IOError, OSError):
            logger.warning("Can not create report log '%s'", report_log_file)
        else:
            self.report_log_file = report_log_file

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
        # Contains all source except the Source0
        self.rest_sources = self.spec_file.get_sources()[1:]
        self.rest_sources = [os.path.abspath(x) for x in self.rest_sources]

        # We want to inform user immediatelly if compare tool doesn't exists
        if self.conf.pkgcomparetool and self.conf.pkgcomparetool not in Checker.get_supported_tools():
            raise RebaseHelperError('You have to specify one of these check tools %s' % Checker.get_supported_tools())

    def _get_rebase_helper_log(self):
        return os.path.join(self.results_dir, settings.REBASE_HELPER_RESULTS_LOG)

    def get_rpm_packages(self, dirname):
        """
        Function returns RPM packages stored in dirname/old and dirname/new directories
        :param dirname: directory where are stored old and new RPMS
        :return:
        """
        found = True
        for version in ['old', 'new']:
            data = {}
            data['name'] = self.spec_file.get_package_name()
            if version == 'old':
                spec_version = self.spec_file.get_version()
            else:
                spec_version = self.rebase_spec_file.get_version()
            data['version'] = spec_version
            data['rpm'] = PathHelper.find_all_files(os.path.join(os.path.realpath(dirname), version, 'RPM'), '*.rpm')
            if not data['rpm']:
                logger.error('Your path %s%s/RPM does not contain any RPM packages' % (dirname, version))
                found = False
            OutputLogger.set_build_data(version, data)
        if not found:
            return False
        return True

    def _get_spec_file(self):
        """
        Function gets the spec file from the execution_dir directory
        """
        self.spec_file_path = PathHelper.find_first_file(self.execution_dir, '*.spec', 0)
        if not self.spec_file_path:
            raise RebaseHelperError("Could not find any SPEC file in the current directory '%s'" % self.execution_dir)

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
        os.makedirs(os.path.join(self.results_dir, settings.REBASE_HELPER_LOGS))

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
            raise RebaseHelperError('%s. Supported archives are %s' % (ni_e.message, Archive.get_supported_archives()))

        try:
            archive.extract_archive(destination)
        except IOError:
            raise RebaseHelperError("Archive '%s' can not be extracted" % archive_path)
        except (EOFError, SystemError):
            raise RebaseHelperError("Archive '%s' is damaged" % archive_path)

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

        # This copies other sources to extracted sources marked as 0
        for rest in self.rest_sources:
            for source_dir in [old_dir, new_dir]:
                archive = [x for x in Archive.get_supported_archives() if rest.endswith(x)]
                # if the source is a remote file, download it
                if archive:
                    Application.extract_sources(rest, os.path.join(self.execution_dir, source_dir))

        return [old_dir, new_dir]

    def patch_sources(self, sources):
        # Patch sources
        git_helper = GitHelper(sources[0])
        if not self.conf.non_interactive:
            git_helper.check_git_config()
        patch = Patcher(self.conf.patchtool)
        self.rebase_spec_file.update_changelog(self.rebase_spec_file.get_new_log(git_helper))
        try:
            self.rebased_patches = patch.patch(sources[0],
                                               sources[1],
                                               self.rest_sources,
                                               git_helper,
                                               self.spec_file.get_applied_patches(),
                                               self.spec_file.get_prep_section(),
                                               **self.kwargs)
        except RuntimeError as run_e:
            raise RebaseHelperError('Patching failed')
        self.rebase_spec_file.write_updated_patches(self.rebased_patches)
        if self.conf.non_interactive:
            if 'unapplied' in self.rebased_patches:
                OutputLogger.set_patch_output('Unapplied patches:', self.rebased_patches['unapplied'])
        OutputLogger.set_patch_output('Patches:', self.rebased_patches)

    def build_packages(self):
        """
        Function calls build class for building packages
        """
        if self.conf.buildtool == 'fedpkg' and not koji_builder:
            print ('Importing module koji failed. Switching to mockbuild.')
            self.conf.buildtool = 'mock'
        try:
            builder = Builder(self.conf.buildtool)
        except NotImplementedError as ni_e:
            raise RebaseHelperError('%s. Supported build tools are %s' % (ni_e.message, Builder.get_supported_tools()))

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
            logger.info('Building packages for %s version %s' %
                        (spec_object.get_package_name(), spec_object.get_version()))
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
                    build_dict.update(builder.get_logs())
                    OutputLogger.set_build_data(version, build_dict)
                    build_log = 'build.log'
                    build_log_path = os.path.join(rpm_dir, build_log)
                    if version == 'old':
                        raise RebaseHelperError('Building old RPM package failed. Check log %s' % build_log_path)
                    logger.error('Building binary packages failed.')
                    try:
                        files = BuildLogAnalyzer.parse_log(rpm_dir, build_log)
                    except BuildLogAnalyzerMissingError:
                        raise RebaseHelperError('Build log %s does not exist' % build_log_path)
                    except BuildLogAnalyzerMakeError:
                        raise RebaseHelperError('Building package failed during build. Check log %s' % build_log_path)
                    except BuildLogAnalyzerPatchError:
                        raise RebaseHelperError('Building package failed during patching. Check log %s' % build_log_path)
                    except RuntimeError:
                        raise RebaseHelperError('Building package failed with unknown reason. Check log %s' % build_log_path)

                    if files['missing']:
                        missing_files = '\n'.join(files['added'])
                        logger.info('Files not packaged in the SPEC file:\n%s', missing_files)
                    elif files['deleted']:
                        deleted_files = '\n'.join(files['deleted'])
                        logger.warning('Removed files packaged in SPEC file:\n%s', deleted_files)
                    else:
                        raise RebaseHelperError("Build failed, but no issues were found in the build log %s" % build_log)
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

    def _execute_checkers(self, checker):
        """
        Function executes a checker based on command line arguments
        :param checker: checker name based from command line
        :return: Nothing
        """
        pkgchecker = Checker(checker)
        logger.info('Comparing packages using %s...', checker)
        text = pkgchecker.run_check(os.path.join(self.results_dir, settings.REBASE_HELPER_LOGS))
        return text

    def pkgdiff_packages(self):
        """
        Function calls pkgdiff class for comparing packages
        :return:
        """
        pkgdiff_results = {}
        if not self.conf.pkgcomparetool:
            for checker in Checker.get_supported_tools():
                results = self._execute_checkers(checker)
                pkgdiff_results[checker] = results

        else:
            text = self._execute_checkers(self.conf.pkgcomparetool)
            pkgdiff_results[self.conf.pkgcomparetool] = text
        for diff_name, result in six.iteritems(pkgdiff_results):
            OutputLogger.set_checker_output(diff_name, result)

    def get_all_log_files(self):
        """
        Function returns all log_files created by rebase-helper
        First if debug log file and second is report summary log file
        :return:
        """
        log_list = []
        log_list.append(self.debug_log_file)
        log_list.append(self.report_log_file)
        return log_list

    def print_summary(self):
        output_tool.check_output_argument(self.conf.outputtool)
        output = output_tool.OutputTool(self.conf.outputtool)
        output.print_information(path=self._get_rebase_helper_log())
        logger.info('Report file from rebase-helper is available here: %s' % self.report_log_file)

    def set_upstream_monitoring(self):
        self.upstream_monitoring = True

    def run(self):
        sources = self.prepare_sources()

        if not self.conf.build_only and not self.conf.comparepkgs:
            self.patch_sources(sources)

        if not self.conf.patch_only:
            if not self.conf.comparepkgs:
                # check build dependencies for rpmbuild
                if self.conf.buildtool == 'rpmbuild':
                    Application.check_build_requires(self.spec_file)
                # Build packages
                try:
                    build = self.build_packages()
                except RuntimeError:
                    logger.error('Not know error caused by build log analysis')
                    return 1
                # Perform checks
            else:
                build = self.get_rpm_packages(self.conf.comparepkgs)
                # We don't care dirname doesn't contain any RPM packages
                # Therefore return 1
            if build:
                self.pkgdiff_packages()
            else:
                if not self.upstream_monitoring:
                    logger.info('Rebase package to %s FAILED. See for more details' % self.conf.sources)
                return 1
            self.print_summary()

        if not self.conf.keep_workspace:
            self._delete_workspace_dir()

        if self.debug_log_file:
            logger.info("Detailed debug log is located in '%s'", self.debug_log_file)
        if not self.upstream_monitoring and not self.conf.patch_only:
            logger.info('Rebase package to %s was SUCCESSFUL.\n' % self.conf.sources)
        return 0

if __name__ == '__main__':
    a = Application(None)
    a.run()
