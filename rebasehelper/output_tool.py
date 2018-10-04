# -*- coding: utf-8 -*-
#
# This tool helps you to rebase package to the latest version
# Copyright (C) 2013-2014 Red Hat, Inc.
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
# Authors: Petr Hracek <phracek@redhat.com>
#          Tomas Hozza <thozza@redhat.com>

import os
import six
import pkg_resources

from rebasehelper.logger import logger, logger_output
from rebasehelper.results_store import results_store
from rebasehelper.checker import checkers_runner
from rebasehelper.constants import RESULTS_DIR, REPORT, DOCS_BUILD


class BaseOutputTool(object):
    """
    Base class for OutputTools.
    print_cli_summary must be overridden in order to produce different CLI output
    """

    DEFAULT = False
    NAME = 'name'
    EXTENSION = 'ext'

    @classmethod
    def get_report_path(cls, app):
        return os.path.join(app.results_dir, REPORT + '.' + cls.get_extension())

    @classmethod
    def get_extension(cls):
        raise NotImplementedError

    @classmethod
    def prepend_results_dir_name(cls, *path_members):
        return os.path.join(RESULTS_DIR, *path_members)

    @classmethod
    def print_cli_summary(cls, app):
        """
        Print report of the rebase

        :param app: Application instance
        """
        cls.app = app
        cls.print_patches_cli()
        result = results_store.get_result_message()

        cls.print_important_checkers_output()

        logger_output.heading('\nAvailable logs:')
        logger_output.info('%s:\n%s', 'Debug log', cls.prepend_results_dir_name(app.debug_log_file))
        if results_store.get_old_build() is not None:
            logger_output.info('%s:\n%s', 'Old build logs and (S)RPMs', cls.prepend_results_dir_name('old-build'))
        if results_store.get_new_build() is not None:
            logger_output.info('%s:\n%s', 'New build logs and (S)RPMs', cls.prepend_results_dir_name('new-build'))
        logger_output.info('')

        logger_output.heading('%s:', 'Rebased sources')
        logger_output.info("%s", cls.prepend_results_dir_name(os.path.relpath(app.rebased_sources_dir,
                                                                              app.results_dir)))

        patch = results_store.get_changes_patch()
        if 'changes_patch' in patch:
            logger_output.heading('%s:', 'Generated patch')
            logger_output.info("%s\n", cls.prepend_results_dir_name(os.path.basename(patch['changes_patch'])))

        cls.print_report_file_path()

        if not app.conf.patch_only:
            if 'success' in result:
                logger_output.success('\n%s' % result['success'])
            # Error is printed out through exception caught in CliHelper.run()
        else:
            if results_store.get_patches()['success']:
                logger_output.success("\nPatching successful")
            elif results_store.get_patches()['success']:
                logger_output.error("\nPatching failed")

    @classmethod
    def print_important_checkers_output(cls):
        """Iterates over all checkers output to highlight important checkers warning"""
        checkers_results = results_store.get_checkers()
        for check_tool in six.itervalues(checkers_runner.plugin_classes):
            for check, data in sorted(six.iteritems(checkers_results)):
                if check == check_tool.get_checker_name():
                    out = check_tool.get_important_changes(data)
                    if out:
                        logger_output.warning('\n'.join(out))

    @classmethod
    def print_report_file_path(cls):
        """Print path to the report file"""
        logger_output.heading('%s report:' % cls.NAME)
        logger_output.info('%s', cls.prepend_results_dir_name('report.' + cls.get_extension()))

    @classmethod
    def print_patches_cli(cls):
        """Print info about patches"""
        patch_dict = {
            'inapplicable': logger_output.error,
            'modified': logger_output.success,
            'deleted': logger_output.success,
        }

        for patch_type, logger_method in six.iteritems(patch_dict):
            cls.print_patches_section_cli(logger_method, patch_type)

    @classmethod
    def print_patches_section_cli(cls, logger_method, patch_type):
        """
        Print info about one of the patches key section

        :param logger_method: method to be used for logging
        :param patch_type: string containing key for the patch_dict
        """
        patches = results_store.get_patches()
        if not patches:
            return

        if patch_type in patches:
            logger_output.info('\n%s patches:', patch_type)
            for patch in sorted(patches[patch_type]):
                logger_method(patch)

    @classmethod
    def run(cls, logs, app):  # pylint: disable=unused-argument
        raise NotImplementedError()

    @classmethod
    def match(cls, cmd=None):
        """Checks if tool name matches the desired one."""
        raise NotImplementedError()

    @classmethod
    def get_name(cls):
        raise NotImplementedError()

    @staticmethod
    def get_supported_tools():
        """Returns list of supported output tools"""
        return output_tools_runner.output_tools.keys()

    @staticmethod
    def get_all_tools():
        """Returns a list of all output tools."""
        return [entrypoint.name for entrypoint in pkg_resources.iter_entry_points('rebasehelper.output_tools')]

    @classmethod
    def get_tools(cls):
        return cls.get_all_tools() if DOCS_BUILD else cls.get_supported_tools()

    @staticmethod
    def get_default_tool():
        """Returns default output tool"""
        default = [k for k, v in six.iteritems(output_tools_runner.output_tools) if v.DEFAULT]
        return default[0] if default else None


class OutputToolRunner(object):
    """
    Class representing the process of running various output tools.
    """

    def __init__(self):
        """
        Constructor of OutputToolRunner class.
        """
        self.output_tools = {}
        for entrypoint in pkg_resources.iter_entry_points('rebasehelper.output_tools'):
            try:
                output_tool = entrypoint.load()
            except ImportError:
                # silently skip broken plugin
                continue
            try:
                self.output_tools[output_tool.get_name()] = output_tool
            except (AttributeError, NotImplementedError):
                # silently skip broken plugin
                continue

    def run_output_tools(self, logs=None, app=None):
        """
        Runs all output tools.

        :param log: Log that probably contains the important message concerning the rebase fail
        :param app: Application class instance
        """
        for output_tool in six.itervalues(self.output_tools):
            if output_tool.match(app.conf.outputtool):
                logger.info("Running '%s' output tool.", output_tool.get_name())
                output_tool.run(logs, app=app)
                output_tool.print_cli_summary(app)


# Global instance of OutputToolRunner. It is enough to load it once per application run.
output_tools_runner = OutputToolRunner()
