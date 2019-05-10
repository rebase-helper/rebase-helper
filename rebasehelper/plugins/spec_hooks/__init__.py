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

import six

from rebasehelper.plugins.plugin import Plugin
from rebasehelper.plugins.plugin_loader import PluginLoader
from rebasehelper.logger import logger


class BaseSpecHook(Plugin):
    """Base class for a spec hook"""

    # spec hook categories, see PACKAGE_CATEGORIES in constants for a complete list
    CATEGORIES = None

    @classmethod
    def run(cls, spec_file, rebase_spec_file, **kwargs):
        """
        Runs a spec hook.

        :param spec_file: Original spec file object
        :param rebase_spec_file: Rebased spec file object
        :param kwargs: Keyword arguments from Application instance
        """
        raise NotImplementedError()


class SpecHooksRunner(object):
    """
    Class representing the process of running various spec file hooks.
    """

    def __init__(self):
        self.spec_hooks = PluginLoader.load('rebasehelper.spec_hooks')

    def get_all_spec_hooks(self):
        return list(self.spec_hooks)

    def get_available_spec_hooks(self):
        return [k for k, v in six.iteritems(self.spec_hooks) if v]

    def run_spec_hooks(self, spec_file, rebase_spec_file, **kwargs):
        """
        Runs all non-blacklisted spec hooks.

        :param spec_file: Original spec file object
        :param rebase_spec_file: Rebased spec file object
        :param kwargs: Keyword arguments from Application instance
        """
        blacklist = kwargs.get("spec_hook_blacklist", [])

        for name, spec_hook in six.iteritems(self.spec_hooks):
            if not spec_hook or name in blacklist:
                continue
            categories = spec_hook.CATEGORIES
            if not categories or spec_file.category in categories:
                logger.info("Running '%s' spec hook", name)
                spec_hook.run(spec_file, rebase_spec_file, **kwargs)


# Global instance of SpecHooksRunner. It is enough to load it once per application run.
spec_hooks_runner = SpecHooksRunner()
