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

from rebasehelper.plugins.versioneers import BaseVersioneer
from rebasehelper.types import PackageCategories
from rebasehelper.specfile import PackageCategory
from rebasehelper.logger import logger
from rebasehelper.helpers.download_helper import DownloadHelper


class RubyGems(BaseVersioneer):

    CATEGORIES: PackageCategories = [PackageCategory.ruby]

    BASE_URL: str = 'https://rubygems.org'
    API_URL: str = '{}/api/v1/gems'.format(BASE_URL)

    @classmethod
    def _get_version(cls, package_name):
        # special-case "ruby", as https://rubygems.org/api/v1/gems/ruby.json returns nonsense
        if package_name == 'ruby':
            return None
        r = DownloadHelper.request('{}/{}.json'.format(cls.API_URL, package_name))
        if r is None or not r.ok:
            # try to strip rubygem prefix
            package_name = re.sub(r'^rubygem-', '', package_name)
            r = DownloadHelper.request('{}/{}.json'.format(cls.API_URL, package_name))
            if r is None or not r.ok:
                return None

        data = r.json()
        return data.get('version')

    @classmethod
    def run(cls, package_name):
        version = cls._get_version(package_name)
        if version:
            return version
        logger.error("Failed to determine latest upstream version!\n"
                     "Check that the package exists on %s.", cls.BASE_URL)
        return None
