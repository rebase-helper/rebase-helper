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

from pkg_resources import parse_version

from rebasehelper.versioneer import BaseVersioneer
from rebasehelper.logger import logger


class NPMJSVersioneer(BaseVersioneer):

    NAME = 'npmjs'
    CATEGORIES = 'nodejs'

    BASE_URL = 'http://registry.npmjs.org'
    API_URL = '{}'.format(BASE_URL)

    @classmethod
    def get_name(cls):
        return cls.NAME

    @classmethod
    def get_categories(cls):
        return cls.CATEGORIES

    @classmethod
    def _get_version(cls, package_name):
        # get the package name format that is used in the npm registry
        package_name = package_name.split('-', 1)[1]

        r = requests.get('{}/{}'.format(cls.API_URL, package_name))
        if not r.ok:
            return None
        data = r.json()
        return data.get('dist-tags')['latest']

    @classmethod
    def run(cls, package_name):
        version = cls._get_version(package_name)
        if version:
            return version
        logger.error("Failed to determine latest upstream version!\n"
                     "Check that the package exists on %s.", cls.BASE_URL)
        return None
