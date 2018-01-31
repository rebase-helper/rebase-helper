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

import git
import six

from pkg_resources import parse_version

from rebasehelper.archive import Archive
from rebasehelper.specfile import SpecFile, get_rebase_name, spec_hooks_runner
from rebasehelper.logger import logger, logger_report, LoggerHelper
from rebasehelper import settings
from rebasehelper.output_tool import output_tools_runner
from rebasehelper.utils import PathHelper, GitHelper, KojiHelper, FileHelper, MacroHelper, ConsoleHelper
from rebasehelper.checker import checkers_runner
from rebasehelper.build_helper import SRPMBuilder, Builder, SourcePackageBuildError, BinaryPackageBuildError
from rebasehelper.patch_helper import Patcher
from rebasehelper.exceptions import RebaseHelperError, CheckerNotFoundError
from rebasehelper.results_store import results_store
from rebasehelper.versioneer import versioneers_runner
from rebasehelper.version import VERSION


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
    rebased_repo = None

    def __init__(self, cli_conf, execution_dir, results_dir, debug_log_file):
        """
        Initialize the application

        :param cli_conf: CLI object with configuration gathered from commandline
        :return:
        """
        results_store.clear()

        self.conf = cli_conf
        self.execution_dir = execution_dir
        self.rebased_sources_dir = os.path.join(results_dir, 'rebased-sources')

        self.debug_log_file = debug_log_file

        # Temporary workspace for Builder, checks, ...
        self.kwargs['workspace_dir'] = self.workspace_dir = os.path.join(self.execution_dir,
                                                                         settings.REBASE_HELPER_WORKSPACE_DIR)
        # Directory where results should be put
        self.kwargs['results_dir'] = self.results_dir = results_dir

        # Directory contaning only those files, which are relevant for the new rebased version
        self.kwargs['rebased_sources_dir'] = self.rebased_sources_dir

        self.kwargs['non_interactive'] = self.conf.non_interactive

        self.kwargs['changelog_entry'] = self.conf.changelog_entry

        self.kwargs['spec_hook_blacklist'] = self.conf.spec_hook_blacklist

        logger.debug("Rebase-helper version: %s", VERSION)

        if self.conf.build_tasks is None:
            # check the workspace dir
            if not self.conf.cont:
                self._check_workspace_dir()

            self._get_spec_file()
            self._prepare_spec_objects()

            # TODO: Remove the value from kwargs and use only CLI attribute!
            self.kwargs['continue'] = self.conf.cont
            self._initialize_data()

        if self.conf.cont or self.conf.build_only:
            self._delete_old_builds()

    @staticmethod
    def setup(cli_conf):
        execution_dir = os.getcwd()
        results_dir = os.path.abspath(cli_conf.results_dir) if cli_conf.results_dir else execution_dir
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

        return execution_dir, results_dir, debug_log_file

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
        self.rebase_spec_file_path = get_rebase_name(self.rebased_sources_dir, self.spec_file_path)

        self.spec_file = SpecFile(self.spec_file_path,
                                  self.conf.changelog_entry,
                                  self.execution_dir,
                                  download=not self.conf.not_download_sources)
        # Check whether test suite is enabled at build time
        if not self.spec_file.is_test_suite_enabled():
            results_store.set_info_text('WARNING', 'Test suite is not enabled at build time.')
        # create an object representing the rebased SPEC file
        self.rebase_spec_file = self.spec_file.copy(self.rebase_spec_file_path)

        if not self.conf.sources:
            self.conf.sources = versioneers_runner.run(self.conf.versioneer,
                                                       self.spec_file.get_package_name(),
                                                       self.spec_file.category,
                                                       self.conf.versioneer_blacklist)
            if self.conf.sources:
                logger.info("Determined latest upstream version '%s'", self.conf.sources)
            else:
                raise RebaseHelperError('Could not determine latest upstream version '
                                        'and no SOURCES argument specified!')

        # Prepare rebased_sources_dir
        self.rebased_repo = self._prepare_rebased_repository(self.spec_file.patches, self.rebased_sources_dir)

        # check if argument passed as new source is a file or just a version
        if [True for ext in Archive.get_supported_archives() if self.conf.sources.endswith(ext)]:
            logger.debug("argument passed as a new source is a file")
            self.rebase_spec_file.set_version_using_archive(self.conf.sources)
        else:
            logger.debug("argument passed as a new source is a version")
            version, extra_version, separator = SpecFile.split_version_string(self.conf.sources)
            self.rebase_spec_file.set_version(version)
            self.rebase_spec_file.set_extra_version_separator(separator)
            self.rebase_spec_file.set_extra_version(extra_version)

        if not self.conf.skip_version_check and parse_version(self.rebase_spec_file.get_version()) \
                <= parse_version(self.spec_file.get_version()):
            raise RebaseHelperError("Current version is equal to or newer than the requested version, nothing to do.")

        # run spec hooks
        spec_hooks_runner.run_spec_hooks(self.spec_file, self.rebase_spec_file, **self.kwargs)

        # spec file object has been sanitized downloading can proceed
        for spec_file in [self.spec_file, self.rebase_spec_file]:
            if spec_file.download:
                spec_file.download_remote_sources()
                # parse spec again with sources downloaded to properly expand %prep section
                spec_file._update_data()  # pylint: disable=protected-access

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
        os.makedirs(os.path.join(results_dir, 'old-build'))
        os.makedirs(os.path.join(results_dir, 'new-build'))
        os.makedirs(os.path.join(results_dir, 'checkers'))
        os.makedirs(os.path.join(results_dir, 'rebased-sources'))

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
            raise RebaseHelperError('%s. Supported archives are %s' % (six.text_type(ni_e),
                                    Archive.get_supported_archives()))

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

        files = os.listdir(destination)

        if not files:
            raise RebaseHelperError('Extraction of sources failed!')
        # if there is only one directory, we can assume it's top-level directory
        elif len(files) == 1:
            sources_dir = os.path.join(destination, files[0])
            if os.path.isdir(sources_dir):
                return sources_dir

        # archive without top-level directory
        return destination

    def prepare_sources(self):
        """
        Function prepares a sources.

        :return:
        """

        old_sources_dir = os.path.join(self.execution_dir, settings.OLD_SOURCES_DIR)
        new_sources_dir = os.path.join(self.execution_dir, settings.NEW_SOURCES_DIR)

        old_dir = Application.extract_sources(self.old_sources, old_sources_dir)
        new_dir = Application.extract_sources(self.new_sources, new_sources_dir)

        old_tld = os.path.relpath(old_dir, old_sources_dir)
        new_tld = os.path.relpath(new_dir, new_sources_dir)

        dirname = self.spec_file.get_setup_dirname()

        if dirname and os.sep in dirname:
            dirs = os.path.split(dirname)
            if old_tld == dirs[0]:
                old_dir = os.path.join(old_dir, *dirs[1:])
            if new_tld == dirs[0]:
                new_dir = os.path.join(new_dir, *dirs[1:])

        new_dirname = os.path.relpath(new_dir, new_sources_dir)

        if new_dirname != '.':
            self.rebase_spec_file.update_setup_dirname(new_dirname)

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

        self.run_package_checkers(self.results_dir, category="SOURCE")
        return [old_dir, new_dir]

    def patch_sources(self, sources):
        # Patch sources
        patch = Patcher('git')
        self.rebase_spec_file.update_changelog(self.rebase_spec_file.get_new_log())
        try:
            self.rebased_patches = patch.patch(sources[0],
                                               sources[1],
                                               self.old_rest_sources,
                                               self.spec_file.get_applied_patches(),
                                               **self.kwargs)
        except RuntimeError:
            raise RebaseHelperError('Patching failed')
        self.rebase_spec_file.write_updated_patches(self.rebased_patches,
                                                    self.conf.disable_inapplicable_patches)
        results_store.set_patches_results(self.rebased_patches)

    def generate_patch(self):
        """
        Generates patch to the results_dir containing all needed changes for
        the rebased package version
        """
        # Delete removed patches from rebased_sources_dir from git
        removed_patches = self.rebase_spec_file.removed_patches
        if removed_patches:
            self.rebased_repo.index.remove(removed_patches, working_tree=True)

        self.rebase_spec_file.update_paths_to_patches()

        # Generate patch
        self.rebased_repo.git.add(all=True)
        self.rebase_spec_file._update_data()  # pylint: disable=protected-access
        self.rebased_repo.index.commit(MacroHelper.expand(self.conf.changelog_entry, self.conf.changelog_entry))
        patch = self.rebased_repo.git.format_patch('-1', stdout=True, stdout_as_string=False)
        with open(os.path.join(self.results_dir, 'changes.patch'), 'wb') as f:
            f.write(patch)
            f.write(b'\n')

        results_store.set_changes_patch('changes_patch', os.path.join(self.results_dir, 'changes.patch'))

    @classmethod
    def _prepare_rebased_repository(cls, patches, rebased_sources_dir):
        """
        Initialize git repository in the rebased directory
        :return: git.Repo instance of rebased_sources
        """
        for patch in patches['applied'] + patches['not_applied']:
            shutil.copy(patch.path, rebased_sources_dir)

        repo = git.Repo.init(rebased_sources_dir)
        repo.git.config('user.name', GitHelper.get_user(), local=True)
        repo.git.config('user.email', GitHelper.get_email(), local=True)
        repo.git.add(all=True)
        repo.index.commit('Initial commit', skip_hooks=True)
        return repo

    @staticmethod
    def _sanitize_build_dict(build_dict):
        blacklist = [
            'builds_nowait',
            'build_tasks',
            'builder_options',
            'srpm_builder_options',
        ]
        return {k: v for k, v in six.iteritems(build_dict) if k not in blacklist}

    def build_source_packages(self):
        try:
            builder = SRPMBuilder(self.conf.srpm_buildtool)
        except NotImplementedError as e:
            raise RebaseHelperError('{}. Supported SRPM build tools are {}'.format(
                six.text_type(e), SRPMBuilder.get_supported_tools()))

        for version in ['old', 'new']:
            results_dir = '{}-build'.format(os.path.join(self.results_dir, version))
            spec = self.spec_file if version == 'old' else self.rebase_spec_file
            package_name = spec.get_package_name()
            package_version = spec.get_version()
            package_full_version = spec.get_full_version()
            logger.info('Building source package for %s version %s', package_name, package_full_version)
            build_dict = dict(
                name=package_name,
                version=package_version,
                srpm_buildtool=self.conf.srpm_buildtool,
                srpm_builder_options=self.conf.srpm_builder_options)
            try:
                build_dict.update(builder.build(spec, results_dir, **build_dict))
                build_dict = self._sanitize_build_dict(build_dict)
                results_store.set_build_data(version, build_dict)
            except RebaseHelperError:
                raise
            except SourcePackageBuildError as e:
                build_dict.update(builder.get_logs())
                build_dict['source_package_build_error'] = six.text_type(e)
                build_dict = self._sanitize_build_dict(build_dict)
                results_store.set_build_data(version, build_dict)
                if e.logfile:
                    msg = 'Building {} SRPM packages failed; see {} for more information'.format(version, e.logfile)
                else:
                    msg = 'Building {} SRPM packages failed; see logs in {} for more information'.format(
                        version, os.path.join(results_dir, 'SRPM'))
                raise RebaseHelperError(msg, logfiles=builder.get_logs().get('logs'))
            except Exception:
                raise RebaseHelperError('Building package failed with unknown reason. '
                                        'Check all available log files.')

    def build_binary_packages(self):
        """Function calls build class for building packages"""
        try:
            builder = Builder(self.conf.buildtool)
        except NotImplementedError as e:
            raise RebaseHelperError('{}. Supported build tools are {}'.format(
                six.text_type(e), Builder.get_supported_tools()))

        for version in ['old', 'new']:
            successful_builds = 0
            try_build_again = False
            while successful_builds < 1:
                results_dir = '{}-build'.format(os.path.join(self.results_dir, version))
                spec = None
                task_id = None
                koji_build_id = None
                build_dict = {}

                if self.conf.build_tasks is None:
                    spec = self.spec_file if version == 'old' else self.rebase_spec_file
                    package_name = spec.get_package_name()
                    package_version = spec.get_version()
                    package_full_version = spec.get_full_version()

                    if version == 'old' and self.conf.get_old_build_from_koji:
                        if KojiHelper.functional:
                            session = KojiHelper.create_session()
                            koji_version, koji_build_id = KojiHelper.get_latest_build(session, package_name)
                            if koji_version:
                                if koji_version != package_version:
                                    logger.warning('Version of the latest Koji build (%s) with id (%s) '
                                                   'differs from version in SPEC file (%s)!',
                                                   koji_version, koji_build_id, package_version)
                                package_version = package_full_version = koji_version
                            else:
                                logger.warning('Unable to find the latest Koji build!')
                        else:
                            logger.warning('Unable to get the latest Koji build!')

                    build_dict = dict(
                        name=package_name,
                        version=package_version,
                        builds_nowait=self.conf.builds_nowait,
                        build_tasks=self.conf.build_tasks,
                        builder_options=self.conf.builder_options,
                        srpm=results_store.get_build(version).get('srpm'))

                    # prepare for building
                    builder.prepare(spec, self.conf)

                    logger.info('Building binary packages for %s version %s', package_name, package_full_version)
                else:
                    task_id = self.conf.build_tasks[0] if version == 'old' else self.conf.build_tasks[1]

                try:
                    if self.conf.build_tasks is None:
                        if koji_build_id:
                            session = KojiHelper.create_session()
                            build_dict['rpm'], build_dict['logs'] = KojiHelper.download_build(session,
                                                                                              koji_build_id,
                                                                                              results_dir)
                        else:
                            build_dict.update(builder.build(spec, results_dir, **build_dict))
                    if builder.creates_tasks() and task_id and not koji_build_id:
                        if not self.conf.builds_nowait:
                            build_dict['rpm'], build_dict['logs'] = builder.wait_for_task(build_dict,
                                                                                          task_id,
                                                                                          results_dir)
                        elif self.conf.build_tasks:
                            build_dict['rpm'], build_dict['logs'] = builder.get_detached_task(task_id, results_dir)
                    build_dict = self._sanitize_build_dict(build_dict)
                    results_store.set_build_data(version, build_dict)
                    successful_builds += 1
                except RebaseHelperError:
                    # Proper RebaseHelperError instance was created already. Re-raise it.
                    raise
                except BinaryPackageBuildError as e:
                    build_dict.update(builder.get_logs())
                    build_dict['binary_package_build_error'] = six.text_type(e)
                    build_dict = self._sanitize_build_dict(build_dict)
                    results_store.set_build_data(version, build_dict)

                    if e.logfile is None:
                        msg = 'Building {} RPM packages failed; see logs in {} for more information'.format(
                            version, os.path.join(results_dir, 'RPM')
                        )
                    else:
                        msg = 'Building {} RPM packages failed; see {} for more information'.format(version, e.logfile)

                    logger.info(msg)
                    if self.rebase_spec_file:
                        # Save current rebase spec file content
                        self.rebase_spec_file.save()
                    if not self.conf.non_interactive and \
                            ConsoleHelper.get_message('Do you want to try it one more time'):
                        try_build_again = True
                    else:
                        raise RebaseHelperError(msg, logfiles=builder.get_logs().get('logs'))
                except Exception:
                    raise RebaseHelperError('Building package failed with unknown reason. '
                                            'Check all available log files.')

                if try_build_again:
                    successful_builds = 0
                    try_build_again = False

                    logger.info('Now it is time to make changes to  %s if necessary.', self.rebase_spec_file.path)
                    if not ConsoleHelper.get_message('Do you want to continue with the rebuild now'):
                        raise KeyboardInterrupt
                    # Update rebase spec file content after potential manual modifications
                    self.rebase_spec_file._read_spec_content()  # pylint: disable=protected-access
                    self.rebase_spec_file._update_data()  # pylint: disable=protected-access
                    # clear current version output directories
                    if os.path.exists(os.path.join(results_dir, 'RPM')):
                        shutil.rmtree(os.path.join(results_dir, 'RPM'))

        if self.conf.builds_nowait and not self.conf.build_tasks:
            if builder.creates_tasks():
                self.print_task_info(builder)

    def run_package_checkers(self, results_dir, category):
        """
        Runs checkers on packages and stores results in a given directory.

        :param results_dir: Path to directory in which to store the results.
        :type results_dir: str
        :param category: checker type(SOURCE/SRPM/RPM)
        :type category: str
        :return: None
        """
        results = dict()

        for checker_name in self.conf.pkgcomparetool:
            try:
                data = checkers_runner.run_checker(os.path.join(results_dir, 'checkers'),
                                                   checker_name,
                                                   workspace_dir=self.workspace_dir,
                                                   category=category)
                if data:
                    results[checker_name] = data
            except CheckerNotFoundError:
                logger.error("Rebase-helper did not find checker '%s'.", checker_name)

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

    def print_summary(self, exception=None):
        """
        Save rebase-helper result and print the summary using output_tools_runner
        :param exception: Error message from rebase-helper
        :return:
        """
        logs = None
        # Store rebase helper result exception
        if exception:
            if exception.logfiles:
                logs = exception.logfiles

            results_store.set_result_message('fail', exception.msg)
        else:
            result = "Rebase from {}-{} to {}-{} completed without an error".format(
                self.spec_file.get_package_name(), self.spec_file.get_version(),
                self.rebase_spec_file.get_package_name(), self.rebase_spec_file.get_version())
            results_store.set_result_message('success', result)

        if self.rebase_spec_file:
            self.rebase_spec_file.update_paths_to_patches()
            self.generate_patch()

        output_tools_runner.run_output_tools(logs, self)

    def print_task_info(self, builder):
        logs = self.get_new_build_logs()['build_ref']
        for version in ['old', 'new']:
            logger.info(builder.get_task_info(logs[version]))

    def get_rebasehelper_data(self):
        rh_stuff = {}
        rh_stuff['build_logs'] = self.get_new_build_logs()
        rh_stuff['patches'] = self.get_rebased_patches()
        rh_stuff['checkers'] = self.get_checker_outputs()
        rh_stuff['logs'] = self.get_all_log_files()
        return rh_stuff

    def run(self):
        # Certain options can be used only with specific build tools
        tools_creating_tasks = [k for k, v in six.iteritems(Builder.build_tools) if v.creates_tasks()]
        if self.conf.buildtool not in tools_creating_tasks:
            options_used = []
            if self.conf.build_tasks is not None:
                options_used.append('--build-tasks')
            if self.conf.builds_nowait is True:
                options_used.append('--builds-nowait')
            if options_used:
                raise RebaseHelperError("{} can be used only with the following build tools: {}".format(
                                        " and ".join(options_used),
                                        ", ".join(tools_creating_tasks)))
        elif self.conf.builds_nowait and self.conf.get_old_build_from_koji:
            raise RebaseHelperError("%s can't be used with: %s" %
                                    ('--builds-nowait', '--get-old-build-from-koji')
                                    )

        tools_accepting_options = [k for k, v in six.iteritems(Builder.build_tools) if v.accepts_options()]
        if self.conf.buildtool not in tools_accepting_options:
            options_used = []
            if self.conf.builder_options is not None:
                options_used.append('--builder-options')
            if options_used:
                raise RebaseHelperError("{} can be used only with the following build tools: {}".format(
                                        " and ".join(options_used),
                                        ", ".join(tools_accepting_options)))

        if self.conf.build_tasks is None:
            sources = self.prepare_sources()
            if not self.conf.build_only and not self.conf.comparepkgs:
                try:
                    self.patch_sources(sources)
                except RebaseHelperError as e:
                    # Print summary and return error
                    self.print_summary(e)
                    raise

        if not self.conf.patch_only:
            if not self.conf.comparepkgs:
                # Build packages
                try:
                    if self.conf.build_tasks is None:
                        self.build_source_packages()
                    self.run_package_checkers(self.results_dir, 'SRPM')
                    self.build_binary_packages()
                    if self.conf.builds_nowait and not self.conf.build_tasks:
                        return
                    self.run_package_checkers(self.results_dir, 'RPM')
                # Print summary and return error
                except RebaseHelperError as e:
                    self.print_summary(e)
                    raise
            else:
                if self.get_rpm_packages(self.conf.comparepkgs):
                    self.run_package_checkers(self.results_dir, 'SRPM')
                    self.run_package_checkers(self.results_dir, 'RPM')

        if not self.conf.keep_workspace:
            self._delete_workspace_dir()

        if self.debug_log_file:
            self.print_summary()
        return 0


if __name__ == '__main__':
    a = Application(None, None, None, None)
    a.run()
