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

from __future__ import print_function
import os
import shutil
import logging
import six

from rebasehelper.archive import Archive
from rebasehelper.specfile import SpecFile, get_rebase_name, spec_hook_runner
from rebasehelper.logger import logger, logger_report, LoggerHelper
from rebasehelper import settings
from rebasehelper import output_tool
from rebasehelper.utils import PathHelper, RpmHelper, ConsoleHelper, GitHelper, KojiHelper, FileHelper, CoprHelper
from rebasehelper.checker import checkers_runner
from rebasehelper.build_helper import Builder, SourcePackageBuildError, BinaryPackageBuildError, koji_builder, \
    KojiBuildTool, CoprBuildTool, MockBuildTool, RpmbuildBuildTool
from rebasehelper.patch_helper import Patcher
from rebasehelper.exceptions import RebaseHelperError, CheckerNotFoundError
from rebasehelper.build_log_analyzer import BuildLogAnalyzer, BuildLogAnalyzerMissingError
from rebasehelper.results_store import results_store
from rebasehelper.build_log_analyzer import BuildLogAnalyzerMakeError, BuildLogAnalyzerPatchError
from rebasehelper import version


class Application(object):
    result_file = ""
    temp_dir = ""
    kwargs = {}
    old_sources = ""
    new_sources = ""
    old_rest_sources = []
    new_rest_sources = []
    spec_file = None
    spec_file_path = None
    rebase_spec_file = None
    rebase_spec_file_path = None
    debug_log_file = None
    report_log_file = None
    rebased_patches = {}
    upstream_monitoring = False

    def __init__(self, cli_conf, execution_dir, results_dir, debug_log_file, report_log_file):
        """
        Initialize the application

        :param cli_conf: CLI object with configuration gathered from commandline
        :return: 
        """
        results_store.clear()

        self.conf = cli_conf
        self.execution_dir = execution_dir

        self.debug_log_file = debug_log_file
        self.report_log_file = report_log_file

        # Temporary workspace for Builder, checks, ...
        self.kwargs['workspace_dir'] = self.workspace_dir = os.path.join(self.execution_dir,
                                                                         settings.REBASE_HELPER_WORKSPACE_DIR)
        # Directory where results should be put
        self.kwargs['results_dir'] = self.results_dir = results_dir

        self.kwargs['non_interactive'] = self.conf.non_interactive

        logger.debug("Rebase-helper version: %s" % version.VERSION)

        if self.conf.build_tasks is None:
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

    @staticmethod
    def setup(cli_conf):
        execution_dir = os.getcwd()
        results_dir = cli_conf.results_dir if cli_conf.results_dir else execution_dir
        results_dir = os.path.join(results_dir, settings.REBASE_HELPER_RESULTS_DIR)

        # if not continuing, check the results dir
        if not cli_conf.cont and not cli_conf.build_only and not cli_conf.comparepkgs:
            Application._check_results_dir(results_dir)

        # This is used if user executes rebase-helper with --continue
        # parameter even when directory does not exist
        if not os.path.exists(results_dir):
            os.makedirs(results_dir)
            os.makedirs(os.path.join(results_dir, settings.REBASE_HELPER_LOGS))

        debug_log_file = Application._add_debug_log_file(results_dir)
        report_log_file = Application._add_report_log_file(results_dir)

        return execution_dir, results_dir, debug_log_file, report_log_file

    @staticmethod
    def _add_debug_log_file(results_dir):
        """
        Add the application wide debug log file

        :return: log file path
        """
        debug_log_file = os.path.join(results_dir, settings.REBASE_HELPER_DEBUG_LOG)
        try:
            LoggerHelper.add_file_handler(logger,
                                          debug_log_file,
                                          logging.Formatter("%(asctime)s %(levelname)s\t%(filename)s"
                                                            ":%(lineno)s %(funcName)s: %(message)s"),
                                          logging.DEBUG)
        except (IOError, OSError):
            logger.warning("Can not create debug log '%s'", debug_log_file)
        else:
            return debug_log_file

    @staticmethod
    def _add_report_log_file(results_dir):
        """
        Add the application report log file

        :return: log file path
        """
        report_log_file = os.path.join(results_dir, settings.REBASE_HELPER_REPORT_LOG)
        try:
            LoggerHelper.add_file_handler(logger_report,
                                          report_log_file,
                                          None,
                                          logging.INFO)
        except (IOError, OSError):
            logger.warning("Can not create report log '%s'", report_log_file)
        else:
            return report_log_file

    def _prepare_spec_objects(self):
        """
        Prepare spec files and initialize objects

        :return: 
        """
        self.rebase_spec_file_path = get_rebase_name(self.results_dir, self.spec_file_path)

        self.spec_file = SpecFile(self.spec_file_path,
                                  self.execution_dir,
                                  download=not self.conf.not_download_sources)
        # Check whether test suite is enabled at build time
        if not self.spec_file.is_test_suite_enabled():
            results_store.set_info_text('WARNING', 'Test suite is not enabled at build time.')
        #  create an object representing the rebased SPEC file
        self.rebase_spec_file = self.spec_file.copy(self.rebase_spec_file_path)

        #  check if argument passed as new source is a file or just a version
        if [True for ext in Archive.get_supported_archives() if self.conf.sources.endswith(ext)]:
            logger.debug("argument passed as a new source is a file")
            self.rebase_spec_file.set_version_using_archive(self.conf.sources)
        else:
            logger.debug("argument passed as a new source is a version")
            version, extra_version, separator = SpecFile.split_version_string(self.conf.sources)
            self.rebase_spec_file.set_version(version)
            self.rebase_spec_file.set_extra_version_separator(separator)
            self.rebase_spec_file.set_extra_version(extra_version)
        self.run_spec_hooks()

    def _initialize_data(self):
        """Function fill dictionary with default data"""
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
        self.old_rest_sources = [os.path.abspath(x) for x in self.spec_file.get_sources()[1:]]
        self.new_rest_sources = [os.path.abspath(x) for x in self.rebase_spec_file.get_sources()[1:]]

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
                logger.error('Your path %s%s/RPM does not contain any RPM packages', dirname, version)
                found = False
            results_store.set_build_data(version, data)
        if not found:
            return False
        return True

    def _get_spec_file(self):
        """Function gets the spec file from the execution_dir directory"""
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
        if os.path.isdir(self.workspace_dir):
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

    @staticmethod
    def _check_results_dir(results_dir):
        """
        Check if  results dir exists, and removes it if yes.

        :return: 
        """
        # TODO: We may not want to delete the directory in the future
        if os.path.exists(results_dir):
            logger.warning("Results directory '%s' exists, removing it", os.path.basename(results_dir))
            shutil.rmtree(results_dir)
        os.makedirs(results_dir)
        os.makedirs(os.path.join(results_dir, settings.REBASE_HELPER_LOGS))
        os.makedirs(os.path.join(results_dir, 'old'))
        os.makedirs(os.path.join(results_dir, 'new'))

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
            raise RebaseHelperError('%s. Supported archives are %s' % six.text_type(ni_e),
                                    Archive.get_supported_archives())

        try:
            archive.extract_archive(destination)
        except IOError:
            raise RebaseHelperError("Archive '%s' can not be extracted" % archive_path)
        except (EOFError, SystemError):
            raise RebaseHelperError("Archive '%s' is damaged" % archive_path)

    @staticmethod
    def extract_sources(archive_path, destination):
        """Function extracts a given Archive and returns a full dirname to sources"""
        Application.extract_archive(archive_path, destination)

        try:
            sources_dir = os.listdir(destination)[0]
        except IndexError:
            raise RebaseHelperError('Extraction of sources failed!')

        if os.path.isdir(os.path.join(destination, sources_dir)):
            return os.path.join(destination, sources_dir)
        else:
            return destination

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

        # determine top-level directory in new_sources archive
        toplevel_dir = os.path.relpath(new_dir,
                                       os.path.join(self.execution_dir, settings.NEW_SOURCES_DIR))

        if toplevel_dir != '.':
            self.rebase_spec_file.update_setup_dirname(toplevel_dir)

        # extract rest of source archives to correct paths
        rest_sources = [self.old_rest_sources, self.new_rest_sources]
        spec_files = [self.spec_file, self.rebase_spec_file]
        sources_dirs = [settings.OLD_SOURCES_DIR, settings.NEW_SOURCES_DIR]
        for sources, spec_file, sources_dir in zip(rest_sources, spec_files, sources_dirs):
            for rest in sources:
                archive = [x for x in Archive.get_supported_archives() if rest.endswith(x)]
                if archive:
                    dest_dir = spec_file.find_archive_target_in_prep(rest)
                    if dest_dir:
                        Application.extract_sources(rest, os.path.join(self.execution_dir, sources_dir, dest_dir))

        return [old_dir, new_dir]

    def patch_sources(self, sources):
        # Patch sources
        git_helper = GitHelper(sources[0])
        if not self.conf.non_interactive:
            git_helper.check_git_config()
        patch = Patcher(GitHelper.GIT)
        self.rebase_spec_file.update_changelog(self.rebase_spec_file.get_new_log(git_helper))
        try:
            self.rebased_patches = patch.patch(sources[0],
                                               sources[1],
                                               self.old_rest_sources,
                                               git_helper,
                                               self.spec_file.get_applied_patches(),
                                               self.spec_file.get_prep_section(),
                                               **self.kwargs)
        except RuntimeError:
            raise RebaseHelperError('Patching failed')
        self.rebase_spec_file.write_updated_patches(self.rebased_patches)
        results_store.set_patches_results(self.rebased_patches)

    def build_packages(self):
        """Function calls build class for building packages"""
        if self.conf.buildtool == KojiBuildTool.CMD and not koji_builder:
            logger.info('Importing module koji failed. Switching to mock builder.')
            self.conf.buildtool = MockBuildTool.CMD
        try:
            builder = Builder(self.conf.buildtool)
        except NotImplementedError as ni_e:
            raise RebaseHelperError('%s. Supported build tools are %s' % six.text_type(ni_e),
                                    Builder.get_supported_tools())

        for version in ['old', 'new']:
            spec_object = self.spec_file if version == 'old' else self.rebase_spec_file
            build_dict = {}
            task_id = None
            if self.conf.build_tasks is None:
                build_dict['name'] = spec_object.get_package_name()
                build_dict['version'] = spec_object.get_version()
                patches = [x.get_path() for x in spec_object.get_patches()]
                spec = spec_object.get_path()
                sources = spec_object.get_sources()
                logger.info('Building packages for %s version %s',
                            spec_object.get_package_name(),
                            spec_object.get_full_version())
            else:
                if version == 'old':
                    task_id = self.conf.build_tasks[0]
                else:
                    task_id = self.conf.build_tasks[1]
            results_dir = os.path.join(self.results_dir, version)
            build_dict['builds_nowait'] = self.conf.builds_nowait
            build_dict['build_tasks'] = self.conf.build_tasks
            build_dict['builder_options'] = self.conf.builder_options

            files = {}
            number_retries = 0
            while self.conf.build_retries != number_retries:
                try:
                    if self.conf.build_tasks is None:
                        build_dict.update(builder.build(spec, sources, patches, results_dir, **build_dict))
                    if not self.conf.builds_nowait:
                        if self.conf.buildtool == KojiBuildTool.CMD:
                            while not build_dict['rpm']:
                                kh = KojiHelper()
                                build_dict['rpm'], build_dict['logs'] = kh.get_koji_tasks(
                                    build_dict['koji_task_id'],
                                    results_dir
                                )
                    else:
                        if self.conf.build_tasks:
                            if self.conf.buildtool == KojiBuildTool.CMD:
                                kh = KojiHelper()
                                try:
                                    build_dict['rpm'], build_dict['logs'] = kh.get_koji_tasks(task_id, results_dir)
                                    results_store.set_build_data(version, build_dict)
                                    if not build_dict['rpm']:
                                        return False
                                except TypeError:
                                    logger.info('Koji tasks are not finished yet. Try again later')
                                    return False
                            elif self.conf.buildtool == CoprBuildTool.CMD:
                                copr_helper = CoprHelper()
                                client = copr_helper.get_client()
                                build_id = int(task_id)
                                status = copr_helper.get_build_status(client, build_id)
                                if status in ['importing', 'pending', 'starting', 'running']:
                                    logger.info('Copr build is not finished yet. Try again later')
                                    return False
                                else:
                                    build_dict['rpm'], build_dict['logs'] = copr_helper.download_build(
                                        client,
                                        build_id,
                                        results_dir
                                    )
                                    if status not in ['succeeded', 'skipped']:
                                        logger.info('Copr build {} did not complete successfully'.format(build_id))
                                        return False
                    # Build finishes properly. Go out from while cycle
                    results_store.set_build_data(version, build_dict)
                    break

                except SourcePackageBuildError:
                    build_dict.update(builder.get_logs())
                    results_store.set_build_data(version, build_dict)
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
                    results_store.set_build_data(version, build_dict)
                    build_log = 'build.log'
                    build_log_path = os.path.join(rpm_dir, build_log)
                    if version == 'old':
                        error_message = 'Building old RPM package failed. Check logs: {} '.format(
                            builder.get_logs().get('logs', 'N/A')
                        )
                        raise RebaseHelperError(error_message)
                    logger.error('Building binary packages failed.')
                    msg = 'Building package failed'
                    try:
                        files = BuildLogAnalyzer.parse_log(rpm_dir, build_log)
                    except BuildLogAnalyzerMissingError:
                        raise RebaseHelperError('Build log %s does not exist', build_log_path)
                    except BuildLogAnalyzerMakeError:
                        raise RebaseHelperError('%s during build. Check log %s', msg, build_log_path)
                    except BuildLogAnalyzerPatchError:
                        raise RebaseHelperError('%s during patching. Check log %s', msg, build_log_path)
                    except RuntimeError:
                        if self.conf.build_retries == number_retries:
                            raise RebaseHelperError('%s with unknown reason. Check log %s', msg, build_log_path)

                    if 'missing' in files:
                        missing_files = '\n'.join(files['missing'])
                        logger.info('Files not packaged in the SPEC file:\n%s', missing_files)
                    elif 'deleted' in files:
                        deleted_files = '\n'.join(files['deleted'])
                        logger.warning('Removed files packaged in SPEC file:\n%s', deleted_files)
                    else:
                        if self.conf.build_retries == number_retries:
                            raise RebaseHelperError("Build failed, but no issues were found in the build log %s",
                                                    build_log)
                    self.rebase_spec_file.modify_spec_files_section(files)

                if not self.conf.non_interactive:
                        msg = 'Do you want rebase-helper to try build the packages one more time'
                        if not ConsoleHelper.get_message(msg):
                            raise KeyboardInterrupt
                else:
                    logger.warning('Some patches were not successfully applied')
                #  build just failed, otherwise we would break out of the while loop
                logger.debug('Number of retries is %s', self.conf.build_retries)
                if os.path.exists(os.path.join(results_dir, 'RPM')):
                    shutil.rmtree(os.path.join(results_dir, 'RPM'))
                if os.path.exists(os.path.join(results_dir, 'SRPM')):
                    shutil.rmtree(os.path.join(results_dir, 'SRPM'))
                number_retries += 1
            if self.conf.build_retries == number_retries:
                raise RebaseHelperError('Building package failed with unknown reason. Check all available log files.')

        return True

    def run_spec_hooks(self):
        """
        Runs spec hooks on spec files.
        :return: None
        """
        for spec_hook_name in spec_hook_runner.get_supported_tools():
            try:
                spec_hook_runner.run_spec_hooks(spec_hook_name, self.rebase_spec_file_path)
            except CheckerNotFoundError:
                logger.error("Rebase-helper did not find spec_hook '%s'." % spec_hook_name)

    def run_package_checkers(self, results_dir):
        """
        Runs checkers on packages and stores results in a given directory.

        :param results_dir: Path to directory in which to store the results.
        :type results_dir: str
        :return: None
        """
        results = dict()

        for checker_name in self.conf.pkgcomparetool:
            try:
                results[checker_name] = checkers_runner.run_checker(results_dir, checker_name)
            except CheckerNotFoundError:
                logger.error("Rebase-helper did not find checker '%s'." % checker_name)

        for diff_name, result in six.iteritems(results):
            results_store.set_checker_output(diff_name, result)

    def get_all_log_files(self):
        """
        Function returns all log_files created by rebase-helper
        First if debug log file and second is report summary log file

        :return: 
        """
        log_list = []
        if FileHelper.file_available(self.debug_log_file):
            log_list.append(self.debug_log_file)
        if FileHelper.file_available(self.report_log_file):
            log_list.append(self.report_log_file)
        return log_list

    def get_new_build_logs(self):
        result = {}
        result['build_ref'] = {}
        for version in ['old', 'new']:
            result['build_ref'][version] = results_store.get_build(version)
        return result

    def get_checker_outputs(self):
        checkers = {}
        if results_store.get_checkers():
            for check, data in six.iteritems(results_store.get_checkers()):
                if data:
                    for log in six.iterkeys(data):
                        if FileHelper.file_available(log):
                            checkers[check] = log
                else:
                    checkers[check] = None
        return checkers

    def get_rebased_patches(self):
        """
        Function returns a list of patches either
        '': [list_of_deleted_patches]
        :return:
        """
        patches = False
        output_patch_string = []
        if results_store.get_patches():
            for key, val in six.iteritems(results_store.get_patches()):
                if key:
                    output_patch_string.append('Following patches have been %s:\n%s' % (key, val))
                    patches = True
        if not patches:
            output_patch_string.append('Patches were not touched. All were applied properly')
        return output_patch_string

    def print_summary(self):
        output = output_tool.OutputTool(self.conf.outputtool)
        report_file = os.path.join(self.results_dir, self.conf.outputtool + settings.REBASE_HELPER_OUTPUT_SUFFIX)
        output.print_information(path=report_file)
        logger.info('Report file from rebase-helper is available here: %s', report_file)

    def print_koji_logs(self):
        logs = self.get_new_build_logs()['build_ref']
        message = "Scratch build for '%s' version is: http://koji.fedoraproject.org/koji/taskinfo?taskID=%s"
        for version in ['old', 'new']:
            data = logs[version]
            logger.info(message % (data['version'], data['koji_task_id']))

    def print_copr_logs(self):
        logs = self.get_new_build_logs()['build_ref']
        copr_helper = CoprHelper()
        client = copr_helper.get_client()
        message = "Copr build for '%s' version is: %s"
        for version in ['old', 'new']:
            data = logs[version]
            build_url = copr_helper.get_build_url(client, data['copr_build_id'])
            logger.info(message % (data['version'], build_url))

    def set_upstream_monitoring(self):
        # This function is used by the-new-hotness, do not remove it!
        self.upstream_monitoring = True

    def get_rebasehelper_data(self):
        rh_stuff = {}
        rh_stuff['build_logs'] = self.get_new_build_logs()
        rh_stuff['patches'] = self.get_rebased_patches()
        rh_stuff['checkers'] = self.get_checker_outputs()
        rh_stuff['logs'] = self.get_all_log_files()
        return rh_stuff

    def run_download_compare(self, tasks_dict, dir_name):
        # TODO: Add doc text with explanation
        self.set_upstream_monitoring()
        kh = KojiHelper()
        for version in ['old', 'new']:
            rh_dict = {}
            compare_dirname = os.path.join(dir_name, version)
            if not os.path.exists(compare_dirname):
                os.mkdir(compare_dirname, 0o777)
            (task, upstream_version, package) = tasks_dict[version]
            rh_dict['rpm'], rh_dict['logs'] = kh.get_koji_tasks([task], compare_dirname)
            rh_dict['version'] = upstream_version
            rh_dict['name'] = package
            results_store.set_build_data(version, rh_dict)
        if tasks_dict['status'] == 'CLOSED':
            self.run_package_checkers(dir_name)
        self.print_summary()
        rh_stuff = self.get_rebasehelper_data()
        logger.info(rh_stuff)
        return rh_stuff

    def run(self):
        # TODO: Move this check to CliHelper OR possibly to a private method validating the configuration.
        if self.conf.fedpkg_build_tasks:
            logger.warning("Option --fedpkg-build-tasks is deprecated, use --build-tasks instead.")
            if not self.conf.build_tasks:
                self.conf.build_tasks = self.conf.fedpkg_build_tasks

        # Certain options can be used only with specific build tools
        # here are checks for remote build tools
        if self.conf.buildtool not in [KojiBuildTool.CMD, CoprBuildTool.CMD]:
            options_used = []
            if self.conf.build_tasks is not None:
                options_used.append('--build-tasks')
            if self.conf.builds_nowait is True:
                options_used.append('--builds-nowait')
            if options_used:
                raise RebaseHelperError("%s can be used only with the following build tools: %s",
                                        ' and '.join(options_used),
                                        ', '.join([KojiBuildTool.CMD, CoprBuildTool.CMD])
                                        )
        # here are checks for local builders
        elif self.conf.buildtool not in [RpmbuildBuildTool.CMD, MockBuildTool.CMD]:
            options_used = []
            if self.conf.builder_options is not None:
                options_used.append('--builder-options')
            if options_used:
                raise RebaseHelperError("%s can be used only with the following build tools: %s",
                                        ' and '.join(options_used),
                                        ', '.join([RpmbuildBuildTool.CMD, MockBuildTool.CMD])
                                        )

        sources = None
        if self.conf.build_tasks is None:
            sources = self.prepare_sources()
            if not self.conf.build_only and not self.conf.comparepkgs:
                self.patch_sources(sources)

        build = False
        if not self.conf.patch_only:
            if not self.conf.comparepkgs:
                # check build dependencies for rpmbuild
                if self.conf.buildtool == RpmbuildBuildTool.CMD:
                    Application.check_build_requires(self.spec_file)
                # Build packages
                try:
                    build = self.build_packages()
                    if self.conf.builds_nowait and not self.conf.build_tasks:
                        if self.conf.buildtool == KojiBuildTool.CMD:
                            self.print_koji_logs()
                        elif self.conf.buildtool == CoprBuildTool.CMD:
                            self.print_copr_logs()
                        return
                except RuntimeError:
                    logger.error('Unknown error caused by build log analysis')
                    # TODO: exception should be raised instead of returning a value - it is never checked!
                    return 1
                # Perform checks
            else:
                build = self.get_rpm_packages(self.conf.comparepkgs)
                # We don't care dirname doesn't contain any RPM packages
                # Therefore return 1
            if build:
                self.run_package_checkers(self.results_dir)
            else:
                if not self.upstream_monitoring:
                    # TODO: This should be an ERROR
                    logger.info('Rebase package to %s FAILED. See for more details', self.conf.sources)
                # TODO: exception should be raised instead of returning a value - it is never checked!
                return 1
            self.print_summary()

        if not self.conf.keep_workspace:
            self._delete_workspace_dir()

        if self.debug_log_file:
            logger.info("Detailed debug log is located in '%s'", self.debug_log_file)
        if not self.upstream_monitoring and not self.conf.patch_only:
            logger.info('Rebase package to %s was SUCCESSFUL.\n', self.conf.sources)
        return 0


if __name__ == '__main__':
    a = Application(None, None, None, None, None)
    a.run()
