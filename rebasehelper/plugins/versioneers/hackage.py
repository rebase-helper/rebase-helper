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

from rebasehelper.plugins.versioneers import BaseVersioneer
from rebasehelper.types import PackageCategories
from rebasehelper.specfile import PackageCategory
from rebasehelper.logger import logger
from rebasehelper.helpers.download_helper import DownloadHelper


class Hackage(BaseVersioneer):

    CATEGORIES: PackageCategories = [PackageCategory.haskell]

    BASE_URL: str = 'https://haskell.org'
    API_URL: str = 'https://hackage.haskell.org'

    @classmethod
    def _get_version(cls, package_name):
        if package_name.startswith('ghc-'):
            package_name = package_name.replace('ghc-', '', 1)

        r = DownloadHelper.request('{}/package/{}/preferred'.format(cls.API_URL, package_name),
                                   headers={'Accept': 'application/json'})
        if r is None or not r.ok:
            return None

        data = r.json()
        return data.get('normal-version')[0]

    @classmethod
    def run(cls, package_name):
        version = cls._get_version(package_name)
        if version:
            return version
        logger.error("Failed to determine latest upstream version!\n"
                     "Check that the package exists on %s.", cls.BASE_URL)
        return None
