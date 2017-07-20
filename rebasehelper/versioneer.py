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


class BaseVersioneer(object):
    """Base class for a versioneer"""

    DEFAULT = False

    @classmethod
    def is_default(cls):
        """Checks if the versioneer is the default choice"""
        raise NotImplementedError()

    @classmethod
    def get_name(cls):
        """Returns the name of a versioneer"""
        raise NotImplementedError()

    @classmethod
    def run(cls, package_name):
        """
        Runs a versioneer.

        :param package_name: Name of a package
        :return: Latest upstream version of a package
        """
        raise NotImplementedError()


class VersioneersRunner(object):

    def __init__(self):
        self.versioneers = {}
        for entrypoint in pkg_resources.iter_entry_points('rebasehelper.versioneers'):
            try:
                versioneer = entrypoint.load()
            except ImportError:
                # silently skip broken plugin
                continue
            try:
                self.versioneers[versioneer.get_name()] = versioneer
            except (AttributeError, NotImplementedError):
                # silently skip broken plugin
                continue

    def get_available_versioneers(self):
        """Returns a list of available versioneers"""
        return [k for k, v in six.iteritems(self.versioneers)]

    def get_default_versioneer(self):
        """Returns default versioneer"""
        default = [k for k, v in six.iteritems(self.versioneers) if v.is_default()]
        return default[0] if default else None

    def run(self, versioneer, package_name):
        """
        Runs specified versioneer.

        :param versioneer: Name of a versioneer
        :param package_name: Name of a package
        :return: Latest upstream version of a package
        """
        logger.info("Running '%s' versioneer", versioneer)
        return self.versioneers[versioneer].run(package_name)


# Global instance of VersioneersRunner. It is enough to load it once per application run.
versioneers_runner = VersioneersRunner()
