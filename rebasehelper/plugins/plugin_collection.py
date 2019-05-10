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

from rebasehelper.plugins.plugin_loader import PluginLoader


class PluginCollection(object):
    def __init__(self, entrypoint, manager):
        self.plugins = PluginLoader.load(entrypoint, manager)

    def get_all_plugins(self):
        return list(self.plugins)

    def get_supported_plugins(self):
        return [k for k, v in six.iteritems(self.plugins) if v]

    def get_default_plugins(self, return_one=False):
        default = [k for k, v in six.iteritems(self.plugins) if v and getattr(v, 'DEFAULT', False)]
        return default if not return_one else default[0] if default else None

    def get_plugin(self, tool):
        try:
            return self.plugins[tool]
        except KeyError:
            raise NotImplementedError("Unsupported plugin")

    def get_options(self):
        """Gets options of all plugins of one type.

        Returns:
            list: List of plugins' options.

        """
        options = []
        for plugin in six.itervalues(self.plugins):
            if plugin:
                options.extend(plugin.OPTIONS)

        return options
