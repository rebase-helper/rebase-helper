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

import pkg_resources
import os

import six

from rebasehelper.logger import logger
from rebasehelper.constants import RESULTS_DIR, DOCS_BUILD


class BaseChecker(object):
    """Base class of package checkers.

    Attributes:
        NAME(str): Name of the checker.
        DEFAULT(bool): If True, the checker is run by default.
        CATEGORY(str): Category which determines when the checker is run. Valid options: SRPM/RPM/SOURCE.
        results_dir(str): Path where the results are stored.
    """

    NAME = None
    DEFAULT = False
    CATEGORY = None
    results_dir = None

    @classmethod
    def match(cls, cmd):
        """
        Checks if the tool name match the class implementation. If yes, returns
        True, otherwise returns False.
        """
        if cmd == cls.NAME:
            return True
        else:
            return False

    @classmethod
    def get_checker_output_dir_short(cls):
        """Return short version of checker output directory"""
        return os.path.join(RESULTS_DIR, 'checkers', cls.NAME)

    @classmethod
    def get_checker_name(cls):
        """Returns a name of the checker"""
        return cls.NAME

    @classmethod
    def is_default(cls):
        return cls.DEFAULT

    @classmethod
    def is_available(cls):
        return False

    @classmethod
    def run_check(cls, results_dir, **kwargs):
        """Perform the check itself and return results."""
        raise NotImplementedError()

    @classmethod
    def get_category(cls):
        return cls.CATEGORY

    @classmethod
    def get_underlined_title(cls, text, separator='='):
        return "\n{}\n{}".format(text, separator * len(text))

    @classmethod
    def get_important_changes(cls, checker_output):
        """
        Each checker has an opportunity to highlight some of its output.
        This function is optional, as not all checkers provide output with critical information.

        Args:
            checker_output (dict): Dictionary with output from the given checker.

        Returns:
            list: List of strings to be output to CLI as warning messages.
        """
        pass


class CheckersRunner(object):
    """
    Class representing the process of running various checkers on final packages.
    """

    def __init__(self):
        """
        Constructor of a CheckersRunner class.
        """
        self.plugin_classes = {}
        for entrypoint in pkg_resources.iter_entry_points('rebasehelper.checkers'):
            try:
                checker = entrypoint.load()
            except ImportError:
                # silently skip broken plugin
                continue
            try:
                self.plugin_classes[checker.get_checker_name()] = checker
            except (AttributeError, NotImplementedError):
                # silently skip broken plugin
                continue

    def run_checker(self, results_dir, checker_name, **kwargs):
        """
        Runs a particular checker and returns the results.

        :param results_dir: Path to a directory in which the checker should store the results.
        :type results_dir: str
        :param checker_name: Name of the checker to run. Ideally this should be name of existing checker.
        :type checker_name: str
        :raises NotImplementedError: If checker with the given name does not exist.
        :return: results from the checker
        """
        checker = None
        for check_tool in six.itervalues(self.plugin_classes):
            if check_tool.get_category() != kwargs.get('category'):
                continue
            if check_tool.match(checker_name):
                # we found the checker we are looking for
                checker = check_tool
                break

        if checker is None:
            # Appropriate checker not found
            return None

        logger.info("Running tests on packages using '%s'", checker_name)
        return checker.run_check(results_dir, **kwargs)

    def get_supported_tools(self):
        """Return list of supported tools"""
        return [k for k, v in six.iteritems(self.plugin_classes) if v.is_available()]

    @staticmethod
    def get_all_tools():
        """Returns a list of all checkers."""
        return [entrypoint.name for entrypoint in pkg_resources.iter_entry_points('rebasehelper.checkers')]

    def get_tools(self):
        return self.get_all_tools() if DOCS_BUILD else self.get_supported_tools()

    def get_default_tools(self):
        """Return list of default tools"""
        return [k for k, v in six.iteritems(self.plugin_classes) if v.is_default()]


# Global instance of CheckersRunner. It is enough to load it once per application run.
checkers_runner = CheckersRunner()
