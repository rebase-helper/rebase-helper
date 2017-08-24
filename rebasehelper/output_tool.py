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
import six
import pkg_resources

from rebasehelper.logger import logger
from rebasehelper.results_store import results_store
from rebasehelper.utils import ConsoleHelper


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
        return os.path.join(app.results_dir, 'report.' + cls.get_extension())

    @classmethod
    def get_extension(cls):
        raise NotImplementedError

    @classmethod
    def print_cli_summary(cls, app):
        """
        Print report of the rebase

        :param app: Application instance
        """
        cls.app = app
        cls.print_patches_cli()

        ConsoleHelper.cprint('\nAvailable logs:', color='yellow')
        print('{0}:\n{1}'.format('Debug log', app.debug_log_file))
        if results_store.get_old_build() is not None:
            print('{0}:\n{1}'.format('Old build logs and (S)RPMs', os.path.join(app.results_dir, 'old-build')))
        if results_store.get_new_build() is not None:
            print('{0}:\n{1}'.format('New build logs and (S)RPMs', os.path.join(app.results_dir, 'new-build')))
        print('')

        ConsoleHelper.cprint('%s:' % 'Rebased sources', color='yellow')
        print("%s" % app.rebased_sources_dir)

        ConsoleHelper.cprint('%s:' % 'Generated patch', color='yellow')
        print("%s\n" % os.path.join(app.results_dir, 'changes.patch'))

        cls.print_report_file_path()

        result = results_store.get_result_message()

        if not app.conf.patch_only:
            if 'success' in result:
                ConsoleHelper.cprint('\n%s' % result['success'], color='green')
            # Error is printed out through exception caught in CliHelper.run()
        else:
            if results_store.get_patches()['success']:
                ConsoleHelper.cprint("\nPatching successful", color='green')
            elif results_store.get_patches()['success']:
                ConsoleHelper.cprint("\nPatching failed", color='red')

    @classmethod
    def print_report_file_path(cls):
        """Print path to the report file"""
        ConsoleHelper.cprint('%s report:' % cls.NAME, color='yellow')
        print('%s' % os.path.join(cls.app.results_dir, 'report.' + cls.get_extension()))

    @classmethod
    def print_patches_cli(cls):
        """Print info about patches"""
        patch_dict = {
            'inapplicable': 'red',
            'modified': 'green',
            'deleted': 'green'}

        for patch_type, color in six.iteritems(patch_dict):
            cls.print_patches_section_cli(color, patch_type)

    @classmethod
    def print_patches_section_cli(cls, color, patch_type):
        """
        Print info about one of the patches key section

        :param color: color used for the message printing
        :param patch_type: string containing key for the patch_dict
        """
        patches = results_store.get_patches()
        if not patches:
            return

        if patch_type in patches:
            print('\n%s patches:' % patch_type)
            for patch in patches[patch_type]:
                ConsoleHelper.cprint(patch, color=color)

    @classmethod
    def run(cls):
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

    def run_output_tools(self, log=None, app=None):
        """
        Runs all output tools.

        :param log: Log that probably contains the important message concerning the rebase fail
        :param app: Application class instance
        """
        for name, output_tool in six.iteritems(self.output_tools):
            if output_tool.match(app.conf.outputtool):
                logger.info("Running '%s' output tool." % output_tool.get_name())
                output_tool.run(log, app=app)
                output_tool.print_cli_summary(app)

# Global instance of OutputToolRunner. It is enough to load it once per application run.
output_tools_runner = OutputToolRunner()
