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

import logging
import os
from typing import cast

from rebasehelper.logger import CustomLogger
from rebasehelper.plugins.plugin import Plugin
from rebasehelper.plugins.plugin_collection import PluginCollection
from rebasehelper.results_store import results_store
from rebasehelper.constants import RESULTS_DIR, REPORT, LOGS_DIR, DEBUG_LOG, OLD_BUILD_DIR, NEW_BUILD_DIR


logger: CustomLogger = cast(CustomLogger, logging.getLogger(__name__))
logger_summary: CustomLogger = cast(CustomLogger, logging.getLogger('rebasehelper.summary'))


class BaseOutputTool(Plugin):
    """Base class for an output tool"""

    DEFAULT: bool = False
    EXTENSION: str = ''

    @classmethod
    def get_report_path(cls, app):
        return os.path.join(app.results_dir, REPORT + '.' + cls.EXTENSION)

    @classmethod
    def prepend_results_dir_name(cls, app, *path_members):
        """Prepends a path with path to rebase-helper-results.

        Takes directory changes (such as cd into cloned repo with --bugzilla-id)
        into account.

        Args:
            app: Application instance.
            path_members: Path members to prepend the results dir to.

        Returns:
            Prepended path.

        """
        if app.conf.results_dir:
            if os.path.isabs(app.conf.results_dir):
                prepend = app.conf.results_dir
            else:
                # make the path relative to start_dir
                prepend = os.path.relpath(os.path.join(app.execution_dir, app.conf.results_dir), app.start_dir)
            path = os.path.join(prepend, RESULTS_DIR, *path_members)
        else:
            path = os.path.join(os.path.relpath(os.getcwd(), app.start_dir), RESULTS_DIR, *path_members)
        if not path.startswith(os.pardir) and not path.startswith(os.curdir):
            path = os.path.join(os.curdir, path)
        return path

    @classmethod
    def print_cli_summary(cls, app):
        """Outputs a summary of a rebase-helper run.

        Args:
            app: Application instance.
        """
        cls.print_patches_cli()
        result = results_store.get_result_message()

        cls.print_important_checkers_output()

        logger_summary.heading('\nAvailable logs:')
        logger_summary.info('%s:\n%s', 'Debug log', cls.prepend_results_dir_name(app,
                                                                                 os.path.join(LOGS_DIR, DEBUG_LOG)))
        if results_store.get_old_build() is not None:
            logger_summary.info('%s:\n%s', 'Old build logs and (S)RPMs',
                                cls.prepend_results_dir_name(app, OLD_BUILD_DIR))
        if results_store.get_new_build() is not None:
            logger_summary.info('%s:\n%s', 'New build logs and (S)RPMs',
                                cls.prepend_results_dir_name(app, NEW_BUILD_DIR))
        logger_summary.info('')

        logger_summary.heading('%s:', 'Rebased sources')
        logger_summary.info("%s", cls.prepend_results_dir_name(app, os.path.relpath(app.rebased_sources_dir,
                                                                                    app.results_dir)))

        patch = results_store.get_changes_patch()
        if 'changes_patch' in patch:
            logger_summary.heading('%s:', 'Generated patch')
            logger_summary.info("%s\n", cls.prepend_results_dir_name(app, os.path.basename(patch['changes_patch'])))

        cls.print_report_file_path(app)

        if 'success' in result:
            logger_summary.success('\n%s', result['success'])
        # Error is printed out through exception caught in CliHelper.run()

    @classmethod
    def print_important_checkers_output(cls):
        """Iterates over all checkers output to highlight important checkers warning"""
        checkers_results = results_store.get_checkers()
        for check_tool in cls.manager.checkers.plugins.values():
            if check_tool:
                for check, data in sorted(checkers_results.items()):
                    if check == check_tool.name:
                        out = check_tool.get_important_changes(data)
                        if out:
                            logger_summary.warning('\n'.join(out))

    @classmethod
    def print_report_file_path(cls, app):
        """Outputs path to the report file"""
        logger_summary.heading('%s report:', cls.name)
        logger_summary.info('%s', cls.prepend_results_dir_name(app, 'report.' + cls.EXTENSION))

    @classmethod
    def print_patches_cli(cls):
        """Outputs info about patches"""
        patch_dict = {
            'inapplicable': logger_summary.error,
            'modified': logger_summary.success,
            'deleted': logger_summary.success,
        }

        for patch_type, logger_method in patch_dict.items():
            cls.print_patches_section_cli(logger_method, patch_type)

    @classmethod
    def print_patches_section_cli(cls, logger_method, patch_type):
        """Outputs information about one of the patch types.

        Args:
            logger_method: Method to use for logging
            patch_type: A key to use for filtering patch dictionary obtained
                        from results_store.
        """
        patches = results_store.get_patches()
        if not patches:
            return

        if patch_type in patches:
            logger_summary.info('\n%s patches:', patch_type)
            for patch in sorted(patches[patch_type]):
                logger_method(patch)

    @classmethod
    def run(cls, logs, app):  # pylint: disable=unused-argument
        raise NotImplementedError()


class OutputToolCollection(PluginCollection):
    """
    Class representing the process of running various output tools.
    """

    def run(self, tool, logs=None, app=None):
        """Runs specified output tool.

        Args:
            tool(str): Tool to run.
            logs (list): Build logs containing information about the failed rebase.
            app (rebasehelper.application.Application): Application class instance.

        """
        output_tool = self.plugins[tool]
        logger.info("Running '%s' output tool.", tool)
        output_tool.run(logs, app=app)
        output_tool.print_cli_summary(app)
