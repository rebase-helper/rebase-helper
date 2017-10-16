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

import requests

from rebasehelper.versioneer import BaseVersioneer
from rebasehelper.logger import logger


class CPANVersioneer(BaseVersioneer):
    NAME = 'cpan'
    CATEGORIES = ['perl']

    BASE_URL = 'https://metacpan.org'
    API_URL = 'https://fastapi.metacpan.org/v1'

    @classmethod
    def get_name(cls):
        return cls.NAME

    @classmethod
    def get_categories(cls):
        return cls.CATEGORIES

    @classmethod
    def _get_version(cls, package_name):
        # sets package name to format used on metacpan
        if package_name.startswith('perl-'):
            package_name = package_name.replace('perl-', '', 1)
        package_name = package_name.replace('-', '::')

        r = requests.get('{}/download_url/{}'.format(cls.API_URL, package_name))
        if not r.ok:
            return None
        data = r.json()
        if data.get('status') == 'latest':
            return data.get('version')
        return None

    @classmethod
    def run(cls, package_name):
        version = cls._get_version(package_name)
        if version:
            return version
        logger.error("Failed to determine latest upstream version!\n"
                     "Check that the package exists on %s.", cls.BASE_URL)
        return None
