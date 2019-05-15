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

import shlex

from rebasehelper.plugins.plugin import Plugin
from rebasehelper.plugins.plugin_collection import PluginCollection


class SRPMBuildToolBase(Plugin):
    """SRPM build tool base class.

    Attributes:
        DEFAULT(bool): If True, the build tool is default tool.

    """

    DEFAULT: bool = False

    @staticmethod
    def get_srpm_builder_options(**kwargs):
        srpm_builder_options = kwargs.get('srpm_builder_options')
        if srpm_builder_options:
            return shlex.split(srpm_builder_options)
        return None

    @classmethod
    def get_logs(cls):
        """
        Get logs from previously failed build
        Returns:
        dict with
        'logs' -> list of absolute paths to logs
        """
        return dict(logs=getattr(cls, 'logs', None))

    @classmethod
    def build(cls, spec, results_dir, **kwargs):
        """
        Build SRPM with chosen SRPM Build Tool

        :param spec: SpecFile object
        :param results_dir: absolute path to DIR where results should be stored
        :return: absolute path to SRPM, list with absolute paths to logs
        """
        raise NotImplementedError()


class SRPMBuildToolCollection(PluginCollection):
    """Collection of SRPM build tools."""
