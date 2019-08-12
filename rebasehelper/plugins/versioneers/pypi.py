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

import logging
import re
from typing import cast

from rebasehelper.logger import CustomLogger
from rebasehelper.plugins.versioneers import BaseVersioneer
from rebasehelper.types import PackageCategories
from rebasehelper.specfile import PackageCategory
from rebasehelper.helpers.download_helper import DownloadHelper


logger: CustomLogger = cast(CustomLogger, logging.getLogger(__name__))


class PyPI(BaseVersioneer):

    CATEGORIES: PackageCategories = [PackageCategory.python]

    BASE_URL: str = 'https://pypi.org'
    API_URL: str = '{}/pypi'.format(BASE_URL)

    @classmethod
    def _get_version(cls, package_name):
        r = DownloadHelper.request('{}/{}/json'.format(cls.API_URL, package_name))
        if r is None or not r.ok:
            # try to strip python prefix
            package_name = re.sub(r'^python[23]?-', '', package_name)
            r = DownloadHelper.request('{}/{}/json'.format(cls.API_URL, package_name))
            if r is None or not r.ok:
                return None

        data = r.json()
        try:
            return data['info']['version']
        except KeyError:
            return None

    @classmethod
    def run(cls, package_name):
        version = cls._get_version(package_name)
        if version:
            return version
        logger.error("Failed to determine latest upstream version!\n"
                     "Check that the package exists on %s.", cls.BASE_URL)
        return None
