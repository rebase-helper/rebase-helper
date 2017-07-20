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

import re

import requests

from rebasehelper.versioneer import BaseVersioneer


class PyPIVersioneer(BaseVersioneer):

    DEFAULT = False
    NAME = 'pypi'

    API_URL = 'https://pypi.python.org/pypi'

    @classmethod
    def is_default(cls):
        return cls.DEFAULT

    @classmethod
    def get_name(cls):
        return cls.NAME

    @classmethod
    def run(cls, package_name):
        r = requests.get('{}/{}/json'.format(cls.API_URL, package_name))
        if not r.ok:
            # try to strip python prefix
            package_name = re.sub(r'^python[23]?-', '', package_name)
            r = requests.get('{}/{}/json'.format(cls.API_URL, package_name))
            if not r.ok:
                return None
        data = r.json()
        try:
            return data['info']['version']
        except KeyError:
            return None
