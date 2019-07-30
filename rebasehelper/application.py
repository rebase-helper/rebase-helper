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

import fnmatch
import os
import shutil
import logging

import git  # type: ignore

from typing import Any, Dict, List, Optional

from pkg_resources import parse_version

from rebasehelper.archive import Archive
from rebasehelper.specfile import SpecFile, get_rebase_name
from rebasehelper.logger import logger, log_formatter, debug_log_formatter, LoggerHelper, CustomLogger
from rebasehelper import constants
from rebasehelper.patcher import Patcher
from rebasehelper.plugins.plugin_manager import plugin_manager
from rebasehelper.plugins.checkers import CheckerCategory
from rebasehelper.exceptions import RebaseHelperError, CheckerNotFoundError
from rebasehelper.exceptions import SourcePackageBuildError, BinaryPackageBuildError
from rebasehelper.results_store import results_store
from rebasehelper.version import VERSION
from rebasehelper.helpers.path_helper import PathHelper
from rebasehelper.helpers.macro_helper import MacroHelper
from rebasehelper.helpers.input_helper import InputHelper
from rebasehelper.helpers.git_helper import GitHelper
from rebasehelper.helpers.koji_helper import KojiHelper
from rebasehelper.helpers.lookaside_cache_helper import LookasideCacheHelper


class Application:
    result_file: str = ''
    temp_dir: str = ''
    kwargs: Dict[str, Any] = {}
    old_sources: str = ''
    new_sources: str = ''
    old_rest_sources: List[str] = []
    new_rest_sources: List[str] = []
    spec_file: Optional[SpecFile] = None
    spec_file_path: Optional[str] = None
    rebase_spec_file: Optional[SpecFile] = None
    rebase_spec_file_path: Optional[str] = None
    debug_log_file: Optional[str] = None
    report_log_file: Optional[str] = None
    rebased_patches: Dict[str, List[str]] = {}
    rebased_repo: Optional[git.Repo] = None

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

        self.kwargs.update(self.conf.config)
        # Temporary workspace for Builder, checks, ...
        self.kwargs['workspace_dir'] = self.workspace_dir = os.path.join(self.execution_dir, constants.WORKSPACE_DIR)
        # Directory where results should be put
        self.kwargs['results_dir'] = self.results_dir = results_dir
        # Directory contaning only those files, which are relevant for the new rebased version
        self.kwargs['rebased_sources_dir'] = self.rebased_sources_dir

        logger.verbose("Rebase-helper version: %s", VERSION)

        if self.conf.build_tasks is None:
            # check the workspace dir
            if not self.conf.cont:
                self._check_workspace_dir()

            self._get_spec_file()
            self._prepare_spec_objects()

            # verify all sources for the new version are present
            missing_sources = [os.path.basename(s) for s in self.rebase_spec_file.sources
                               if not os.path.isfile(os.path.basename(s))]
            if missing_sources:
                raise RebaseHelperError('The following sources are missing: {}'.format(','.join(missing_sources)))

            if self.conf.update_sources:
                sources = [os.path.basename(s) for s in self.spec_file.sources]
                rebased_sources = [os.path.basename(s) for s in self.rebase_spec_file.sources]
                uploaded = LookasideCacheHelper.update_sources('fedpkg', self.rebased_sources_dir,
                                                               self.rebase_spec_file.get_package_name(),
                                                               sources, rebased_sources,
                                                               upload=not self.conf.skip_upload)
                self._update_gitignore(uploaded, self.rebased_sources_dir)

            # TODO: Remove the value from kwargs and use only CLI attribute!
            self.kwargs['continue'] = self.conf.cont
            self._initialize_data()

        if self.conf.cont or self.conf.build_only:
            self._delete_old_builds()

    @staticmethod
    def setup(cli_conf):
        execution_dir = os.getcwd()
        results_dir = os.path.abspath(cli_conf.results_dir) if cli_conf.results_dir else execution_dir
        results_dir = os.path.join(results_dir, constants.RESULTS_DIR)

        # if not continuing, check the results dir
        if not cli_conf.cont and not cli_conf.build_only and not cli_conf.comparepkgs:
            Application._check_results_dir(results_dir)

        # This is used if user executes rebase-helper with --continue
        # parameter even when directory does not exist
        if not os.path.exists(results_dir):
            os.makedirs(results_dir)
            os.makedirs(os.path.join(results_dir, constants.LOGS_DIR))

        debug_log_file = Application.setup_logging(results_dir)

        return execution_dir, results_dir, debug_log_file

    @staticmethod
    def setup_logging(results_dir):
        """Adds file handlers of various verbosity to loggers.

        Args:
            results_dir: Path to directory which results are stored in.

        Returns:
            string: Path to debug log.

        """
        logs_dir = os.path.join(results_dir, constants.LOGS_DIR)
        debug_log = os.path.join(logs_dir, constants.DEBUG_LOG)
        LoggerHelper.add_file_handler(logger, debug_log, debug_log_formatter, logging.DEBUG)
        verbose_log = os.path.join(logs_dir, constants.VERBOSE_LOG)
        LoggerHelper.add_file_handler(logger, verbose_log, log_formatter, CustomLogger.VERBOSE)
        info_log = os.path.join(logs_dir, constants.INFO_LOG)
        LoggerHelper.add_file_handler(logger, info_log, log_formatter, logging.INFO)

        return debug_log

    def _prepare_spec_objects(self):
        """
        Prepare spec files and initialize objects

        :return:
        """
        self.rebase_spec_file_path = get_rebase_name(self.rebased_sources_dir, self.spec_file_path)

        self.spec_file = SpecFile(self.spec_file_path, self.execution_dir)
        # Check whether test suite is enabled at build time
        if not self.spec_file.is_test_suite_enabled():
            results_store.set_info_text('WARNING', 'Test suite is not enabled at build time.')
        # create an object representing the rebased SPEC file
        self.rebase_spec_file = self.spec_file.copy(self.rebase_spec_file_path)

        if not self.conf.sources:
            self.conf.sources = plugin_manager.versioneers.run(self.conf.versioneer,
                                                               self.spec_file.get_package_name(),
                                                               self.spec_file.category,
                                                               self.conf.versioneer_blacklist)
            if self.conf.sources:
                logger.info("Determined latest upstream version '%s'", self.conf.sources)
            else:
                raise RebaseHelperError('Could not determine latest upstream version '
                                        'and no SOURCES argument specified!')

        # Prepare rebased_sources_dir
        self.rebased_repo = self._prepare_rebased_repository(self.spec_file.patches,
                                                             self.execution_dir,
                                                             self.rebased_sources_dir)

        # check if argument passed as new source is a file or just a version
        if [True for ext in Archive.get_supported_archives() if self.conf.sources.endswith(ext)]:
            logger.verbose("argument passed as a new source is a file")
            self.rebase_spec_file.set_version_using_archive(self.conf.sources)
        else:
            logger.verbose("argument passed as a new source is a version")
            version, extra_version, separator = SpecFile.split_version_string(self.conf.sources)
            self.rebase_spec_file.set_version(version)
            self.rebase_spec_file.extra_version_separator = separator
            self.rebase_spec_file.set_extra_version(extra_version)

        if not self.conf.skip_version_check and parse_version(self.rebase_spec_file.get_version()) \
                <= parse_version(self.spec_file.get_version()):
            raise RebaseHelperError("Current version is equal to or newer than the requested version, nothing to do.")

        self.rebase_spec_file.update_changelog(self.conf.changelog_entry)

        # run spec hooks
        plugin_manager.spec_hooks.run(self.spec_file, self.rebase_spec_file, **self.kwargs)

        # spec file object has been sanitized downloading can proceed
        if not self.conf.not_download_sources:
            for spec_file in [self.spec_file, self.rebase_spec_file]:
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
            raise RebaseHelperError("Could not find any SPEC file "
                                    "in the current directory '{}'".format(self.execution_dir))

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
        logger.verbose("Removing the workspace directory '%s'", self.workspace_dir)
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
        os.makedirs(os.path.join(results_dir, constants.LOGS_DIR))
        os.makedirs(os.path.join(results_dir, constants.OLD_BUILD_DIR))
        os.makedirs(os.path.join(results_dir, constants.NEW_BUILD_DIR))
        os.makedirs(os.path.join(results_dir, constants.CHECKERS_DIR))
        os.makedirs(os.path.join(results_dir, constants.REBASED_SOURCES_DIR))

    @staticmethod
    def extract_archive(archive_path, destination):
        """
        Extracts given archive into the destination and handle all exceptions.

        :param archive_path: path to the archive to be extracted
        :param destination: path to a destination, where the archive should be extracted to
        :return:
        """
        archive = Archive(archive_path)

        try:
            archive.extract_archive(destination)
        except IOError:
            raise RebaseHelperError("Archive '{}' can not be extracted".format(archive_path))
        except (EOFError, SystemError):
            raise RebaseHelperError("Archive '{}' is damaged".format(archive_path))

    @staticmethod
    def extract_sources(archive_path, destination):
        """Function extracts a given Archive and returns a full dirname to sources"""
        try:
            Application.extract_archive(archive_path, destination)
        except NotImplementedError:
            # not a standard archive type, can't extract it, fallback to copying
            os.makedirs(destination)
            shutil.copy(archive_path, destination)

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

        old_sources_dir = os.path.join(self.execution_dir, constants.WORKSPACE_DIR, constants.OLD_SOURCES_DIR)
        new_sources_dir = os.path.join(self.execution_dir, constants.WORKSPACE_DIR, constants.NEW_SOURCES_DIR)

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
        sources_dirs = [
            os.path.join(constants.WORKSPACE_DIR, constants.OLD_SOURCES_DIR),
            os.path.join(constants.WORKSPACE_DIR, constants.NEW_SOURCES_DIR),
        ]
        for sources, spec_file, sources_dir in zip(rest_sources, spec_files, sources_dirs):
            for rest in sources:
                archive = [x for x in Archive.get_supported_archives() if rest.endswith(x)]
                if archive:
                    dest_dir = spec_file.find_archive_target_in_prep(rest)
                    if dest_dir:
                        Application.extract_sources(rest, os.path.join(self.execution_dir, sources_dir, dest_dir))

        return [old_dir, new_dir]

    def patch_sources(self, sources):
        try:
            # Patch sources
            self.rebased_patches = Patcher.patch(sources[0],
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
    def _update_gitignore(cls, sources, rebased_sources_dir):
        """Adds new entries into .gitignore file.

        Args:
            sources (list): List of new source files.
            rebased_sources_dir (str): Target directory.

        """
        gitignore = os.path.join(rebased_sources_dir, '.gitignore')

        if not os.path.isfile(gitignore):
            return

        with open(gitignore) as f:
            entries = f.readlines()

        def match(source):
            source = source.lstrip(os.path.sep).rstrip('\n')
            for entry in entries:
                if fnmatch.fnmatch(source, entry.lstrip(os.path.sep).rstrip('\n')):
                    return True
            return False

        with open(gitignore, 'a') as f:
            for src in [s for s in sources if not match(s)]:
                f.write(os.path.sep + src + '\n')

    @classmethod
    def _prepare_rebased_repository(cls, patches, execution_dir, rebased_sources_dir):
        """
        Initialize git repository in the rebased directory
        :return: git.Repo instance of rebased_sources
        """
        for patch in patches['applied'] + patches['not_applied']:
            shutil.copy(patch.path, rebased_sources_dir)

        sources = os.path.join(execution_dir, 'sources')
        if os.path.isfile(sources):
            shutil.copy(sources, rebased_sources_dir)

        gitignore = os.path.join(execution_dir, '.gitignore')
        if os.path.isfile(gitignore):
            shutil.copy(gitignore, rebased_sources_dir)

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
        return {k: v for k, v in build_dict.items() if k not in blacklist}

    def build_source_packages(self):
        try:
            builder = plugin_manager.srpm_build_tools.get_plugin(self.conf.srpm_buildtool)
        except NotImplementedError as e:
            raise RebaseHelperError('{}. Supported SRPM build tools are {}'.format(
                str(e), ', '.join(plugin_manager.srpm_build_tools.get_supported_plugins())))

        for version in ['old', 'new']:
            koji_build_id = None
            results_dir = '{}-build'.format(os.path.join(self.results_dir, version))
            spec = self.spec_file if version == 'old' else self.rebase_spec_file
            package_name = spec.get_package_name()
            package_version = spec.get_version()
            logger.info('Building source package for %s version %s', package_name, package_version)

            if version == 'old' and self.conf.get_old_build_from_koji:
                koji_build_id, ver = KojiHelper.get_old_build_info(package_name, package_version)
                if ver:
                    package_version = ver

            build_dict = dict(
                name=package_name,
                version=package_version,
                srpm_buildtool=self.conf.srpm_buildtool,
                srpm_builder_options=self.conf.srpm_builder_options)
            try:
                if koji_build_id:
                    session = KojiHelper.create_session()
                    build_dict['srpm'], build_dict['logs'] = KojiHelper.download_build(session,
                                                                                       koji_build_id,
                                                                                       os.path.join(
                                                                                           results_dir,
                                                                                           'SRPM'
                                                                                       ),
                                                                                       arches=['src'])

                else:
                    build_dict.update(builder.build(spec, results_dir, **build_dict))
                build_dict = self._sanitize_build_dict(build_dict)
                results_store.set_build_data(version, build_dict)
            except RebaseHelperError:  # pylint: disable=try-except-raise
                raise
            except SourcePackageBuildError as e:
                build_dict.update(builder.get_logs())
                build_dict['source_package_build_error'] = str(e)
                build_dict = self._sanitize_build_dict(build_dict)
                results_store.set_build_data(version, build_dict)
                if e.logfile:
                    msg = 'Building {} SRPM packages failed; see {} for more information'.format(version, e.logfile)
                else:
                    msg = 'Building {} SRPM packages failed; see logs in {} for more information'.format(
                        version, os.path.join(results_dir, 'SRPM'))
                logger.error(msg)
                raise RebaseHelperError(msg, logfiles=builder.get_logs().get('logs'))
            except Exception:
                raise RebaseHelperError('Building package failed with unknown reason. '
                                        'Check all available log files.')

    def build_binary_packages(self):
        """Function calls build class for building packages"""
        try:
            builder = plugin_manager.build_tools.get_plugin(self.conf.buildtool)
        except NotImplementedError as e:
            raise RebaseHelperError('{}. Supported build tools are {}'.format(
                str(e), ', '.join(plugin_manager.build_tools.get_supported_plugins())))

        for version in ['old', 'new']:
            results_dir = '{}-build'.format(os.path.join(self.results_dir, version))
            spec = None
            task_id = None
            koji_build_id = None
            build_dict = {}

            if self.conf.build_tasks is None:
                spec = self.spec_file if version == 'old' else self.rebase_spec_file
                package_name = spec.get_package_name()
                package_version = spec.get_version()

                if version == 'old' and self.conf.get_old_build_from_koji:
                    koji_build_id, ver = KojiHelper.get_old_build_info(package_name, package_version)
                    if ver:
                        package_version = ver

                build_dict = dict(
                    name=package_name,
                    version=package_version,
                    builds_nowait=self.conf.builds_nowait,
                    build_tasks=self.conf.build_tasks,
                    builder_options=self.conf.builder_options,
                    srpm=results_store.get_build(version).get('srpm'),
                    srpm_logs=results_store.get_build(version).get('logs'))

                # prepare for building
                builder.prepare(spec, self.conf)

                logger.info('Building binary packages for %s version %s', package_name, package_version)
            else:
                task_id = self.conf.build_tasks[0] if version == 'old' else self.conf.build_tasks[1]

            try:
                if self.conf.build_tasks is None:
                    if koji_build_id:
                        session = KojiHelper.create_session()
                        build_dict['rpm'], build_dict['logs'] = KojiHelper.download_build(session,
                                                                                          koji_build_id,
                                                                                          os.path.join(
                                                                                              results_dir,
                                                                                              'RPM',
                                                                                          ),
                                                                                          arches=['noarch', 'x86_64'])
                    else:
                        build_dict.update(builder.build(spec, results_dir, **build_dict))
                if builder.CREATES_TASKS and task_id and not koji_build_id:
                    if not self.conf.builds_nowait:
                        build_dict['rpm'], build_dict['logs'] = builder.wait_for_task(build_dict,
                                                                                      task_id,
                                                                                      results_dir)
                    elif self.conf.build_tasks:
                        build_dict['rpm'], build_dict['logs'] = builder.get_detached_task(task_id, results_dir)
                build_dict = self._sanitize_build_dict(build_dict)
                results_store.set_build_data(version, build_dict)
            except RebaseHelperError:  # pylint: disable=try-except-raise
                # Proper RebaseHelperError instance was created already. Re-raise it.
                raise
            except BinaryPackageBuildError as e:
                build_dict.update(builder.get_logs())
                build_dict['binary_package_build_error'] = str(e)
                build_dict = self._sanitize_build_dict(build_dict)
                results_store.set_build_data(version, build_dict)

                if e.logfile is None:
                    msg = 'Building {} RPM packages failed; see logs in {} for more information'.format(
                        version, os.path.join(results_dir, 'RPM')
                    )
                else:
                    msg = 'Building {} RPM packages failed; see {} for more information'.format(version, e.logfile)

                logger.error(msg)
                raise RebaseHelperError(msg, logfiles=builder.get_logs().get('logs'))
            except Exception:
                raise RebaseHelperError('Building package failed with unknown reason. '
                                        'Check all available log files.')

        if self.conf.builds_nowait and not self.conf.build_tasks:
            if builder.CREATES_TASKS:
                self.print_task_info(builder)

    def run_package_checkers(self, results_dir, **kwargs):
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
                data = plugin_manager.checkers.run(os.path.join(results_dir, 'checkers'),
                                                   checker_name,
                                                   **kwargs)
                if data:
                    results[checker_name] = data
            except CheckerNotFoundError:
                logger.error("Rebase-helper did not find checker '%s'.", checker_name)

        for diff_name, result in results.items():
            results_store.set_checker_output(diff_name, result)

    def get_all_log_files(self):
        """
        Function returns all log_files created by rebase-helper
        First if debug log file and second is report summary log file

        :return:
        """
        log_list = []
        if PathHelper.file_available(self.debug_log_file):
            log_list.append(self.debug_log_file)
        if PathHelper.file_available(self.report_log_file):
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
        for check, data in results_store.get_checkers().items():
            if data:
                for log in data:
                    if PathHelper.file_available(log):
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
            for key, val in results_store.get_patches().items():
                if key:
                    output_patch_string.append('Following patches have been {}:\n{}'.format(key, val))
                    patches = True
        if not patches:
            output_patch_string.append('Patches were not touched. All were applied properly')
        return output_patch_string

    def print_summary(self, exception=None):
        """
        Save rebase-helper result and print the summary using output tools.
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

        plugin_manager.output_tools.run(self.conf.outputtool, logs, self)

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

    def apply_changes(self):
        try:
            repo = git.Repo(self.execution_dir)
        except git.InvalidGitRepositoryError:
            repo = git.Repo.init(self.execution_dir)
        patch = results_store.get_changes_patch()
        if not patch:
            logger.warning('Cannot apply changes.patch. No patch file was created')
        try:
            repo.git.am(patch['changes_patch'])
        except git.GitCommandError as e:
            logger.warning('changes.patch was not applied properly. Please review changes manually.'
                           '\nThe error message is: %s', str(e))

    def prepare_next_run(self, results_dir):
        # Running build log hooks only makes sense after a failed build
        # of new RPM packages. The folder results_dir/new-build/RPM
        # doesn't exist unless the build of new RPM packages has been run.
        changes_made = False
        if os.path.exists(os.path.join(results_dir, 'new-build', 'RPM')):
            changes_made = plugin_manager.build_log_hooks.run(self.spec_file, self.rebase_spec_file, **self.kwargs)
        # Save current rebase spec file content
        self.rebase_spec_file.save()
        if not self.conf.non_interactive and \
                InputHelper.get_message('Do you want to try it one more time'):
            logger.info('Now it is time to make changes to  %s if necessary.', self.rebase_spec_file.path)
        elif self.conf.non_interactive and changes_made:
            logger.info('Build log hooks made some changes to the SPEC file, starting the build process again.')
        else:
            return False
        if not self.conf.non_interactive and not \
                InputHelper.get_message('Do you want to continue with the rebuild now'):
            return False
        # Update rebase spec file content after potential manual modifications
        self.rebase_spec_file.reload()
        # clear current version output directories
        if os.path.exists(os.path.join(results_dir, 'old-build')):
            shutil.rmtree(os.path.join(results_dir, 'old-build'))
        if os.path.exists(os.path.join(results_dir, 'new-build')):
            shutil.rmtree(os.path.join(results_dir, 'new-build'))
        return True

    def run(self):
        # Certain options can be used only with specific build tools
        tools_creating_tasks = []
        for tool_name, tool in plugin_manager.build_tools.plugins.items():
            if tool and tool.CREATES_TASKS:
                tools_creating_tasks.append(tool_name)
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
            raise RebaseHelperError("{} can't be used with: {}".format('--builds-nowait', '--get-old-build-from-koji'))

        tools_accepting_options = []
        for tool_name, tool in plugin_manager.build_tools.plugins.items():
            if tool and tool.ACCEPTS_OPTIONS:
                tools_accepting_options.append(tool_name)
        if self.conf.buildtool not in tools_accepting_options:
            options_used = []
            if self.conf.builder_options is not None:
                options_used.append('--builder-options')
            if options_used:
                raise RebaseHelperError("{} can be used only with the following build tools: {}".format(
                                        " and ".join(options_used),
                                        ", ".join(tools_accepting_options)))

        if self.conf.build_tasks is None:
            old_sources, new_sources = self.prepare_sources()
            self.run_package_checkers(self.results_dir,
                                      category=CheckerCategory.SOURCE,
                                      old_dir=old_sources,
                                      new_dir=new_sources)
            if not self.conf.build_only and not self.conf.comparepkgs:
                try:
                    self.patch_sources([old_sources, new_sources])
                except RebaseHelperError as e:
                    # Print summary and return error
                    self.print_summary(e)
                    raise

        if not self.conf.patch_only:
            if not self.conf.comparepkgs:
                # Build packages
                while True:
                    try:
                        if self.conf.build_tasks is None:
                            self.build_source_packages()
                        self.run_package_checkers(self.results_dir, category=CheckerCategory.SRPM)
                        self.build_binary_packages()
                        if self.conf.builds_nowait and not self.conf.build_tasks:
                            return
                        self.run_package_checkers(self.results_dir, category=CheckerCategory.RPM)
                    # Print summary and return error
                    except RebaseHelperError as e:
                        if self.prepare_next_run(self.results_dir):
                            continue
                        self.print_summary(e)
                        raise
                    else:
                        break
            else:
                if self.get_rpm_packages(self.conf.comparepkgs):
                    self.run_package_checkers(self.results_dir, category=CheckerCategory.SRPM)
                    self.run_package_checkers(self.results_dir, category=CheckerCategory.RPM)

        if not self.conf.keep_workspace:
            self._delete_workspace_dir()

        if self.debug_log_file:
            self.print_summary()
        if self.conf.apply_changes:
            self.apply_changes()
        return 0


if __name__ == '__main__':
    a = Application(None, None, None, None)
    a.run()
