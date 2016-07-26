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

from __future__ import print_function
import os
import imp
import six

from rebasehelper.logger import logger


class BaseChecker(object):
    """ Base class used for testing tool run on final pkgs. """

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
    def run_check(cls, results_dir):
        """Perform the check itself and return results."""
        raise NotImplementedError()


class Checker(object):
    """
    Class representing a process of checking final packages.
    """

    def __init__(self, dir_name=os.path.join(os.path.dirname(__file__), 'checkers')):
        """
        Constructor of a Checker class.

        :param dir_name: Path to directory witch contains various checkers. By default the it looks for checkers inside
        'checkers' subdirectory in the project's installation location.
        :type dir_name: str
        """
        self._injector_type = 'BaseChecker'
        self.plugin_classes = self.load_checkers(dir_name)

    def _checker_find_injector(self, module):
        injectors = []
        for n in dir(module):
            attr = getattr(module, n)
            if hasattr(attr, '__base__') and attr.__base__.__name__ == self._injector_type:
                injectors.append(attr)
        return injectors

    def load_checkers(self, plugins_dir):
        """
        Load checker implementations from the given location.

        :param plugins_dir: Path to directory from which to load the checkers.
        :type plugins_dir: str
        :return: Dictionary with names of the checkers and the actual checker objects.
        :rtype: dict
        """
        plugin_checkers = {}
        for plugin in os.listdir(plugins_dir):
            if not plugin.endswith('.py'):
                continue
            modname, suffix = plugin.rsplit('.', 1)
            if suffix == 'py':
                fullpath = os.path.abspath(plugins_dir)
                f, filename, description = imp.find_module(modname, [fullpath])
                m = imp.load_module(modname, open(filename, 'U'), filename, description)
                try:
                    injs = self._checker_find_injector(m)
                    for i in injs:
                        obj = i()
                        plugin_checkers[obj.get_checker_name()] = obj
                except AttributeError:
                    print ("Module '%s' does not implement `register(context)`" % modname)
        return plugin_checkers

    def run_check(self, results_dir, checker_name=None):
        """Run the check"""
        _tool = None
        for check_tool in six.itervalues(self.plugin_classes):
            if check_tool.match(checker_name):
                _tool = checker_name

        if _tool is None:
            raise NotImplementedError("Unsupported checking tool")
        logger.info("Running tests on packages using '%s'", _tool)
        return self.plugin_classes[_tool].run_check(results_dir)

    def get_supported_tools(self):
        """Return list of supported tools"""
        return self.plugin_classes.keys()
