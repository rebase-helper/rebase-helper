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

import six

from rebasehelper.plugins import Plugin, PluginLoader
from rebasehelper.logger import logger
from rebasehelper.constants import RESULTS_DIR


class BaseChecker(Plugin):
    """Base class of package checkers.

    Attributes:
        DEFAULT(bool): If True, the checker is run by default.
        CATEGORY(str): Category which determines when the checker is run. Valid options: SRPM/RPM/SOURCE.
        results_dir(str): Path where the results are stored.
    """

    DEFAULT = False
    CATEGORY = None
    results_dir = None

    @classmethod
    def get_checker_output_dir_short(cls):
        """Return short version of checker output directory"""
        return os.path.join(RESULTS_DIR, 'checkers', cls.name)

    @classmethod
    def is_available(cls):
        raise NotImplementedError()

    @classmethod
    def run_check(cls, results_dir, **kwargs):
        """Perform the check itself and return results."""
        raise NotImplementedError()

    @classmethod
    def format(cls, data):
        """Formats checker output to a readable text form."""
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


class CheckersRunner(object):
    """
    Class representing the process of running various checkers on final packages.
    """

    def __init__(self):
        self.checkers = PluginLoader.load('rebasehelper.checkers')

    def get_all_tools(self):
        return list(self.checkers)

    def get_supported_tools(self):
        return [k for k, v in six.iteritems(self.checkers) if v]

    def get_default_tools(self):
        return [k for k, v in six.iteritems(self.checkers) if v and v.DEFAULT]

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
        try:
            checker = self.checkers[checker_name]
        except KeyError:
            return None
        if checker.CATEGORY != kwargs.get('category'):
            return None

        logger.info("Running checks on packages using '%s'", checker_name)
        return checker.run_check(results_dir, **kwargs)


# Global instance of CheckersRunner. It is enough to load it once per application run.
checkers_runner = CheckersRunner()
