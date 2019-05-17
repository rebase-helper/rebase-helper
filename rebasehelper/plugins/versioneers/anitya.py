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

from pkg_resources import parse_version

from rebasehelper.plugins.versioneers import BaseVersioneer
from rebasehelper.types import PackageCategories
from rebasehelper.logger import logger
from rebasehelper.helpers.download_helper import DownloadHelper


class Anitya(BaseVersioneer):

    CATEGORIES: PackageCategories = []

    BASE_URL: str = 'https://release-monitoring.org'
    API_URL: str = '{}/api'.format(BASE_URL)

    @classmethod
    def _get_version_using_distro_api(cls, package_name):
        r = DownloadHelper.request('{}/project/Fedora/{}'.format(cls.API_URL, package_name))

        if r is None or not r.ok:
            return None
        data = r.json()
        return data.get('version')

    @classmethod
    def _get_version_using_pattern_api(cls, package_name):
        r = DownloadHelper.request('{}/projects'.format(cls.API_URL), params=dict(pattern=package_name))

        if r is None or not r.ok:
            return None
        data = r.json()
        try:
            versions = [p['version'] for p in data['projects'] if p['name'] == package_name and p['version']]
        except KeyError:
            return None
        if not versions:
            return None
        # there can be multiple matching projects, just return the highest version of all of them
        return sorted(versions, key=parse_version, reverse=True)[0]

    @classmethod
    def run(cls, package_name):
        version = cls._get_version_using_distro_api(package_name)
        if version:
            return version
        version = cls._get_version_using_pattern_api(package_name)
        if version:
            return version
        logger.error("Failed to determine latest upstream version!\n"
                     "Check that the package exists on %s.", cls.BASE_URL)
        return None
