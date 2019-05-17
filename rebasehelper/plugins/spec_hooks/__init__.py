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

from typing import List, Optional

from rebasehelper.plugins.plugin import Plugin
from rebasehelper.plugins.plugin_collection import PluginCollection
from rebasehelper.types import PackageCategories
from rebasehelper.logger import logger


class BaseSpecHook(Plugin):
    """Base class for a spec hook"""

    CATEGORIES: PackageCategories = []

    @classmethod
    def run(cls, spec_file, rebase_spec_file, **kwargs):
        """
        Runs a spec hook.

        :param spec_file: Original spec file object
        :param rebase_spec_file: Rebased spec file object
        :param kwargs: Keyword arguments from Application instance
        """
        raise NotImplementedError()


class SpecHookCollection(PluginCollection):
    """
    Class representing the process of running various spec file hooks.
    """

    def run(self, spec_file, rebase_spec_file, **kwargs):
        """Runs all non-blacklisted spec hooks.

        Args:
            spec_file (rebasehelper.specfile.SpecFile): Original SpecFile object.
            rebase_spec_file (rebasehelper.specfile.SpecFile): Rebased SpecFile object.
            **kwargs: Keyword arguments from Application instance.

        """
        blacklist = kwargs.get("spec_hook_blacklist", [])

        for name, spec_hook in self.plugins.items():
            if not spec_hook or name in blacklist:
                continue
            categories = spec_hook.CATEGORIES
            if not categories or spec_file.category in categories:
                logger.info("Running '%s' spec hook", name)
                spec_hook.run(spec_file, rebase_spec_file, **kwargs)
