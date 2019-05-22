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

import os

from rebasehelper.plugins.output_tools import BaseOutputTool
from rebasehelper.logger import LoggerHelper, logger, logger_report
from rebasehelper.results_store import results_store


class Text(BaseOutputTool):

    """ Text output tool. """

    DEFAULT: bool = True
    EXTENSION: str = 'txt'

    @classmethod
    def print_success_message(cls):
        """Print result message"""
        results = cls.results_store.get_result_message()
        if 'success' in results:
            logger_report.info(results['success'])
        else:
            logger_report.info(results['fail'])

    @classmethod
    def print_changes_patch(cls):
        """Print info about the location of changes.patch"""
        patch = cls.results_store.get_changes_patch()
        if patch is not None:
            logger_report.info('\nPatch with differences between old and new version source files:')
            logger_report.info(cls.prepend_results_dir_name(os.path.basename(patch['changes_patch'])))

    @classmethod
    def print_message_and_separator(cls, message="", separator='='):
        logger_report.info(message)
        logger_report.info(separator * (len(message) - 1))

    @classmethod
    def print_patches(cls, patches):
        cls.print_message_and_separator("\nDownstream Patches")
        if not patches:
            logger_report.info("Patches were neither modified nor deleted.")
            return

        logger_report.info("Rebased patches are located in %s", cls.prepend_results_dir_name('rebased-sources'))
        logger_report.info("Legend:")
        logger_report.info("[-] = already applied, patch removed")
        logger_report.info("[*] = merged, patch modified")
        logger_report.info("[!] = conflicting or inapplicable, patch skipped")
        logger_report.info("[ ] = patch untouched")

        patches_out = list()
        for patch_type, patch_list in sorted(patches.items()):
            if patch_list:
                symbols = dict(deleted='-', modified='*', inapplicable='!')
                for patch in sorted(patch_list):
                    patches_out.append(' * {0:40} [{1}]'.format(os.path.basename(patch),
                                                                symbols.get(patch_type, ' ')))
        logger_report.info('\n'.join(sorted(patches_out)))

    @classmethod
    def print_rpms_and_logs(cls, rpms, version):
        """
        Prints information about location of RPMs and logs created during rebase
        :param rpms: dictionary of (S)RPM paths
        :param version: new/old version string
        :return:
        """
        pkgs = ['srpm', 'rpm']
        if not rpms.get('rpm', None):
            return
        message = '\n{} packages'.format(version)
        cls.print_message_and_separator(message=message, separator='-')
        for type_rpm in pkgs:
            srpm = rpms.get(type_rpm, None)
            if not srpm:
                continue

            if type_rpm == 'srpm':
                message = "\nSource packages and logs are in directory %s:"
            else:
                message = "\nBinary packages and logs are in directory %s:"

            if isinstance(srpm, str):
                # Print SRPM path
                dirname = os.path.dirname(srpm)
                logger_report.info(message, cls.prepend_results_dir_name(version.lower() + '-build', 'SRPM'))
                logger_report.info(" - %s", os.path.basename(srpm))
                # Print SRPM logs
                cls.print_build_logs(rpms, dirname)

            else:
                # Print RPMs paths
                dirname = os.path.dirname(srpm[0])
                logger_report.info(message, cls.prepend_results_dir_name(version.lower() + '-build', 'RPM'))
                for pkg in sorted(srpm):
                    logger_report.info(" - %s", os.path.basename(pkg))
                # Print RPMs logs
                cls.print_build_logs(rpms, dirname)

    @classmethod
    def print_build_logs(cls, rpms, dirpath):
        """Function is used for printing rpm build logs"""
        if rpms.get('logs', None) is None:
            return
        for logs in sorted(rpms.get('logs', []) + rpms.get('srpm_logs', [])):
            if dirpath not in logs:
                # Skip logs that do not belong to curent rpms(and version)
                continue
            logger_report.info(' - %s', os.path.basename(logs))

    @classmethod
    def print_summary(cls, path, results):
        """Function is used for printing summary information"""
        if results.get_summary_info():
            for key, value in results.get_summary_info().items():
                logger.info("%s %s\n", key, value)

        LoggerHelper.add_file_handler(logger_report, path)

        cls.results_store = results

        cls.print_success_message()
        logger_report.info("All result files are stored in %s", os.path.dirname(path))

        cls.print_changes_patch()

        cls.print_checkers_text_output(results.get_checkers())

        cls.print_build_log_hooks_result(results.get_build_log_hooks())

        if results.get_patches():
            cls.print_patches(results.get_patches())

        cls.print_message_and_separator("\nRPMS")
        for pkg_version in ['old', 'new']:
            pkg_results = results.get_build(pkg_version)
            if pkg_results:
                cls.print_rpms_and_logs(pkg_results, pkg_version.capitalize())

    @classmethod
    def print_checkers_text_output(cls, checkers_results):
        """Function prints text output for every checker"""
        for check_tool in cls.manager.checkers.plugins.values():
            if check_tool:
                for check, data in sorted(checkers_results.items()):
                    if check == check_tool.name:
                        logger_report.info('\n'.join(check_tool.format(data)))

    @classmethod
    def print_build_log_hooks_result(cls, build_log_hooks_result):
        for hook, data in build_log_hooks_result.items():
            if data:
                cls.print_message_and_separator('\n{} build log hook'.format(hook))
                logger_report.info('\n'.join(cls.manager.build_log_hooks.get_plugin(hook).format(data)))

    @classmethod
    def run(cls, logs, app):  # pylint: disable=unused-argument
        cls.print_summary(cls.get_report_path(app), results_store)
