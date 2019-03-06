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

import pkg_resources


class Plugin(object):
    name = None


class PluginLoader(object):
    @classmethod
    def load(cls, entrypoint):
        result = {}
        for ep in pkg_resources.iter_entry_points(entrypoint):
            result[ep.name] = None
            try:
                plugin = ep.load()
            except ImportError:
                # skip broken plugin
                continue
            try:
                if not issubclass(plugin, Plugin):
                    raise TypeError
            except TypeError:
                # skip broken plugin
                continue
            else:
                plugin.name = ep.name
            result[ep.name] = plugin
        return result
