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

import re

from typing import List, Type

from rebasehelper.plugins.plugin_collection import PluginCollection
from rebasehelper.plugins.build_log_hooks import BuildLogHookCollection
from rebasehelper.plugins.build_tools.rpm import BuildToolCollection
from rebasehelper.plugins.build_tools.srpm import SRPMBuildToolCollection
from rebasehelper.plugins.checkers import CheckerCollection
from rebasehelper.plugins.output_tools import OutputToolCollection
from rebasehelper.plugins.spec_hooks import SpecHookCollection
from rebasehelper.plugins.versioneers import VersioneerCollection


class PluginManager:

    COLLECTIONS: List[Type[PluginCollection]] = [
        BuildLogHookCollection,
        BuildToolCollection,
        SRPMBuildToolCollection,
        CheckerCollection,
        OutputToolCollection,
        SpecHookCollection,
        VersioneerCollection,
    ]

    def __init__(self):
        def convert_class_name(class_name):
            # Converts class name of a collection to the corresponding entrypoint name,
            # e.g. BuildLogHookCollection => build_log_hooks
            class_name = re.sub(r'(.)([A-Z][a-z]+)', r'\1_\2', class_name)
            return re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', class_name).lower().replace('_collection', '') + 's'

        self.plugin_collections = {}
        for collection in self.COLLECTIONS:
            name = convert_class_name(collection.__name__)
            entrypoint = 'rebasehelper.' + name
            self.plugin_collections[name] = collection(entrypoint, self)

    def get_options(self):
        """Gets options of all plugins.

        Returns:
            list: List of plugins' options.

        """
        options = []
        for collection in self.plugin_collections.values():
            options.extend(collection.get_options())

        return options

    def __getattr__(self, name):
        return self.plugin_collections.get(name)


# Global instance of PluginManager, it is enough to load it once per application run.
plugin_manager: PluginManager = PluginManager()
