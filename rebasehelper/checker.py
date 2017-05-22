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

import six
import pkg_resources

from rebasehelper.logger import logger


class BaseChecker(object):
    """ Base class used for testing tool run on final pkgs. """

    DEFAULT = False

    @classmethod
    def match(cls, cmd):
        """
        Checks if the tool name match the class implementation. If yes, returns
        True, otherwise returns False.
        """
        raise NotImplementedError()

    @classmethod
    def get_checker_name(cls):
        """Returns a name of the checker"""
        raise NotImplementedError()

    @classmethod
    def is_default(cls):
        """Checks if the tool is the default checker."""
        raise NotImplementedError()

    @classmethod
    def run_check(cls, results_dir):
        """Perform the check itself and return results."""
        raise NotImplementedError()


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

    def run_checker(self, results_dir, checker_name):
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
            if check_tool.match(checker_name):
                # we found the checker we are looking for
                checker = check_tool
                break

        if checker is None:
            raise NotImplementedError("Unsupported checking tool '{}'".format(checker_name))

        logger.info("Running tests on packages using '%s'", checker_name)
        return checker.run_check(results_dir)

    def get_supported_tools(self):
        """Return list of supported tools"""
        return self.plugin_classes.keys()

    def get_default_tools(self):
        """Return list of default tools"""
        return [k for k, v in six.iteritems(self.plugin_classes) if v.is_default()]


# Global instance of CheckersRunner. It is enough to load it once per application run.
checkers_runner = CheckersRunner()
