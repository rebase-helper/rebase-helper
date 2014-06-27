# -*- coding: utf-8 -*-

# This tool helps you to rebase package to the latest version
# Copyright (C) 2013 Petr Hracek
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


import sys
import os

from rebasehelper.logger import logger
from rebasehelper import settings

output_tools = {}


def register_build_tool(output_tool):
    output_tools[output_tool.PRINT] = output_tool
    return output_tool


def check_output_argument(output_tool):
    """
    Function checks whether pkgdifftool argument is allowed
    """
    if output_tool not in output_tools.keys():
        logger.error('You have to specify one of these printint output tools {0}'.format(output_tools.keys()))
        sys.exit(0)


class BaseOutputTool(object):
    """ Class used for testing and other future stuff, ...
        Each method should overwrite method like run_check
    """

    def print_summary(self, **kwargs):
        """ Return list of files which has been changed against old version
        This will be used by checkers
        """
        raise NotImplementedError()


@register_build_tool
class TextOutputTool(BaseOutputTool):
    """ Text output tool. """
    PRINT = "text"

    @classmethod
    def match(cls, cmd=None):
        if cmd == cls.PRINT:
            return True
        else:
            return False

    @classmethod
    def print_message_and_separator(cls, message="", separator='='):
        logger.info(message)
        logger.info(separator * len(message))

    @classmethod
    def print_patches(cls, patches, summary):
        logger.info("Patches:")
        if not patches:
            logger.info("Patches were neither modified nor deleted.")
            return
        max_number = max(x for x in [len(str(y)) for y in patches.keys()]) + 2
        max_name = max(x for x in [len(os.path.basename(y[0])) for y in patches.values()]) + 2
        for key, value in patches.items():
            patch_name = os.path.basename(value[0])
            for status, patches in summary.items():
                found = [x for x in patches if patch_name in x]
                if not found:
                    continue
                logger.info("Patch{0} {1} [{2}]".format(str(key).ljust(max_number),
                                                        patch_name.ljust(max_name),
                                                        status))
                break
    @classmethod
    def print_rpms(cls, rpms, version):
        pkgs = ['srpm', 'rpm']
        if not rpms.get('srpm', None):
            return
        message = '{0} (S)RPM packages:'.format(version)
        cls.print_message_and_separator(message=message, separator='-')
        for type_rpm in pkgs:
            srpm = rpms.get(type_rpm, None)
            if not srpm:
                continue
            logger.info("{0} package(s):".format(type_rpm.upper()))
            if isinstance(srpm, str):
                logger.info("- {0}".format(srpm))
            else:
                for pkg in srpm:
                    logger.info("- {0}".format(pkg))

    @classmethod
    def print_summary(cls, **kwargs):
        """
        Function is used for printing summary informations
        :return:
        """
        cls.print_message_and_separator(message="Summary information:")
        summary = kwargs['summary_info']
        old = kwargs.get('old')
        new = kwargs.get('new')
        cls.print_patches(old.get(settings.FULL_PATCHES, None), summary)

        cls.print_rpms(old, 'Old')
        cls.print_rpms(new, 'New')
        cls.print_pkgdiff_tool(**kwargs)

    @classmethod
    def print_pkgdiff_tool(cls, **kwargs):
        """
        Function prints a summary information about pkgcomparetool
        """
        logger.info("Results from pkgcompare tool are stored in directory:")
        try:
            logger.info(kwargs['pkgcompareinfo'])
        except KeyError as ke:
            logger.error('Comparing information was not found.')


class OutputTool(object):
    """
    Class representing a process of building binaries from sources.
    """

    def __init__(self, output_tool=None):
        if output_tool is None:
            raise TypeError("Expected argument 'tool' (pos 1) is missing")
        self._output_tool_name = output_tool
        self._tool = None

        for output in output_tools.values():
            if output.match(self._output_tool_name):
                self._tool = output

        if self._tool is None:
            raise NotImplementedError("Unsupported build tool")

    def print_information(self, **kwargs):
        """ Build sources. """
        logger.debug("OutputTool: Printing information using '{0}'".format(self._output_tool_name))
        return self._tool.print_summary(**kwargs)
