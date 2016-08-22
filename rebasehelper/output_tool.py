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

import sys
import os
import six
import json

from rebasehelper.exceptions import RebaseHelperError
from rebasehelper.logger import LoggerHelper, logger, logger_report
from rebasehelper.results_store import results_store

output_tools = {}


def register_output_tool(output_tool):
    output_tools[output_tool.PRINT] = output_tool
    return output_tool


class BaseOutputTool(object):

    """
    Class used for testing and other future stuff, ...
    Each method should overwrite method like run_check
    """

    DEFAULT = False

    @classmethod
    def match(cls, cmd=None, *args, **kwargs):
        """Checks if tool name matches the desired one."""
        raise NotImplementedError()

    def print_summary(self, path, results, **kwargs):
        """
        Return list of files which has been changed against old version
        This will be used by checkers
        """
        raise NotImplementedError()


@register_output_tool
class TextOutputTool(BaseOutputTool):

    """ Text output tool. """

    PRINT = "text"
    DEFAULT = True

    @classmethod
    def match(cls, cmd=None):
        if cmd == cls.PRINT:
            return True
        else:
            return False

    @classmethod
    def print_message_and_separator(cls, message="", separator='='):
        logger_report.info(message)
        logger_report.info(separator * len(message))

    @classmethod
    def print_patches(cls, patches, summary):
        if not patches:
            logger_report.info("Patches were neither modified nor deleted.")
            return
        logger_report.info(summary)
        max_name = 0
        for value in six.itervalues(patches):
            if value:
                new_max = max([len(os.path.basename(x)) for x in value])
                if new_max > max_name:
                    max_name = new_max
        max_key = max([len(x) for x in six.iterkeys(patches)])
        for key, value in six.iteritems(patches):
            if value:
                for patch in value:
                    logger_report.info('Patch %s [%s]', os.path.basename(patch).ljust(max_name), key.ljust(max_key))

    @classmethod
    def print_rpms(cls, rpms, version):
        pkgs = ['srpm', 'rpm']
        if not rpms.get('srpm', None):
            return
        message = '\n{0} (S)RPM packages:'.format(version)
        cls.print_message_and_separator(message=message, separator='-')
        for type_rpm in pkgs:
            srpm = rpms.get(type_rpm, None)
            if not srpm:
                continue
            message = "%s package(s): are in directory %s :"
            if isinstance(srpm, str):
                logger_report.info(message, type_rpm.upper(), os.path.dirname(srpm))
                logger_report.info("- %s", os.path.basename(srpm))
            else:
                logger_report.info(message, type_rpm.upper(), os.path.dirname(srpm[0]))
                for pkg in srpm:
                    logger_report.info("- %s", os.path.basename(pkg))

    @classmethod
    def print_build_logs(cls, rpms, version):
        """
        Function is used for printing rpm build logs

        :param kwargs: 
        :return: 
        """
        if rpms.get('logs', None) is None:
            return
        logger_report.info('Available %s logs:', version)
        for logs in rpms.get('logs', None):
            logger_report.info('- %s', logs)

    @classmethod
    def print_summary(cls, path, results=results_store):
        """
        Function is used for printing summary informations

        :return: 
        """
        if results.get_summary_info():
            for key, value in six.iteritems(results.get_summary_info()):
                logger.info("%s %s\n", key, value)

        try:
            LoggerHelper.add_file_handler(logger_report, path)
        except (OSError, IOError):
            raise RebaseHelperError("Can not create results file '%s'" % path)

        type_pkgs = ['old', 'new']
        if results.get_patches():
            cls.print_patches(results.get_patches(), '\nSummary information about patches:')
        for pkg in type_pkgs:
            type_pkg = results.get_build(pkg)
            if type_pkg:
                cls.print_rpms(type_pkg, pkg.capitalize())
                cls.print_build_logs(type_pkg, pkg.capitalize())

        cls.print_pkgdiff_tool(results.get_checkers())

    @classmethod
    def print_pkgdiff_tool(cls, checkers_results):
        """Function prints a summary information about pkgcomparetool"""
        if checkers_results:
            for check, data in six.iteritems(checkers_results):
                logger_report.info("=== Checker %s results ===", check)
                if data:
                    for checker, output in six.iteritems(data):
                        if output is None:
                            logger_report.info("Log is available here: %s\n", checker)
                        else:
                            if isinstance(output, list):
                                logger_report.info("%s See for more details %s", ','.join(output), checker)
                            else:
                                logger_report.info("%s See for more details %s", output, checker)


@register_output_tool
class JSONOutputTool(BaseOutputTool):

    """ JSON output tool. """

    PRINT = "json"

    @classmethod
    def match(cls, cmd=None):
        if cmd == cls.PRINT:
            return True
        else:
            return False

    @classmethod
    def print_summary(cls, path, results=results_store):
        """
        Function is used for storing output dictionary into JSON structure
        JSON output file is stored into path
        :return:
        """
        with open(path, 'w') as outputfile:
            json.dump(results.get_all(), outputfile, indent=4, sort_keys=True)


class OutputTool(object):

    """Class representing printing the final results."""

    def __init__(self, output_tool=None):
        if output_tool is None:
            raise TypeError("Expected argument 'tool' (pos 1) is missing")
        self._output_tool_name = output_tool
        self._tool = None

        for output in output_tools.values():
            if output.match(self._output_tool_name):
                self._tool = output

        if self._tool is None:
            raise NotImplementedError("Unsupported output tool")

    def print_information(self, path, results=results_store):
        """Build sources."""
        logger.debug("Printing information using '%s'", self._output_tool_name)
        return self._tool.print_summary(path, results)

    @classmethod
    def get_supported_tools(cls):
        """Returns list of supported output tools"""
        return output_tools.keys()

    @classmethod
    def get_default_tool(cls):
        """Returns default output tool"""
        default = [k for k, v in six.iteritems(output_tools) if v.DEFAULT]
        return default[0] if default else None
