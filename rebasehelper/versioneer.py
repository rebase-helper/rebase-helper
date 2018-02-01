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

    @classmethod
    def get_name(cls):
        """Returns the name of a versioneer"""
        raise NotImplementedError()

    @classmethod
    def get_categories(cls):
        """Returns list of categories of a versioneer"""
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
        return self.versioneers.keys()

    def run(self, versioneer, package_name, category, versioneer_blacklist=None):
        """
        Runs specified versioneer or all versioneers subsequently until one of them succeeds.

        :param versioneer: Name of a versioneer
        :param package_name: Name of a package
        :param category: Package category
        :param versioneer_blacklist: List of versioneers that will be skipped
        :return: Latest upstream version of a package
        """
        if versioneer_blacklist is None:
            versioneer_blacklist = []

        if versioneer:
            logger.info("Running '%s' versioneer", versioneer)
            return self.versioneers[versioneer].run(package_name)
        # run all versioneers, except those disabled in config, categorized first
        allowed_versioneers = [v for k, v in six.iteritems(self.versioneers) if k not in versioneer_blacklist]
        for versioneer in sorted(allowed_versioneers, key=lambda v: not v.get_categories()):
            categories = versioneer.get_categories()
            if not categories or category in categories:
                logger.info("Running '%s' versioneer", versioneer.get_name())
                result = versioneer.run(package_name)
                if result:
                    return result
        return None


# Global instance of VersioneersRunner. It is enough to load it once per application run.
versioneers_runner = VersioneersRunner()
