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


class BuildToolBase(Plugin):
    """Build tool base class.

    Attributes:
        DEFAULT(bool): If True, the build tool is default tool.
        ACCEPTS_OPTIONS(bool): If True, the build tool accepts additional
            options passed via --builder-options.
        CREATES_TASKS(bool): If True, the build tool creates remote tasks.

    """

    DEFAULT: bool = False
    ACCEPTS_OPTIONS: bool = False
    CREATES_TASKS: bool = False

    @classmethod
    def prepare(cls, spec, conf):
        """
        Prepare for building.

        :param spec: spec file object
        """
        # do nothing by default

    @classmethod
    def build(cls, spec, results_dir, srpm, **kwargs):
        """
        Build binaries from the sources.

        Keyword arguments:
        spec -- path to a SPEC file
        sources -- list with absolute paths to SOURCES
        patches -- list with absolute paths to PATCHES
        results_dir -- path to DIR where results should be stored

        Returns:
        dict with:
        'srpm' -> absolute path to SRPM
        'rpm' -> list of absolute paths to RPMs
        'logs' -> list of absolute paths to logs
        """
        raise NotImplementedError()

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
    def wait_for_task(cls, build_dict, task_id, results_dir):  # pylint: disable=unused-argument
        """
        Waits until specified task is finished

        :param build_dict: build data
        :param results_dir: path to DIR where results should be stored
        :return: tuple with:
            list of absolute paths to RPMs
            list of absolute paths to logs
        """
        # do nothing by default
        return build_dict.get('rpm'), build_dict.get('logs')

    @classmethod
    def get_task_info(cls, build_dict):
        """
        Gets information about detached remote task

        :param build_dict: build data
        :return: task info
        """
        raise NotImplementedError()

    @classmethod
    def get_detached_task(cls, task_id, results_dir):
        """
        Gets packages and logs for specified task

        :param task_id: detached task id
        :param results_dir: path to DIR where results should be stored
        :return: tuple with:
            list of absolute paths to RPMs
            list of absolute paths to logs
        """
        raise NotImplementedError()

    @staticmethod
    def get_builder_options(**kwargs):
        builder_options = kwargs.get('builder_options')
        if builder_options:
            return shlex.split(builder_options)
        return None


class BuildToolCollection(PluginCollection):
    """Collection of RPM build tools."""
