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


class AnityaVersioneer(BaseVersioneer):

    DEFAULT = True
    NAME = 'anitya'

    API_URL = 'https://release-monitoring.org/api/projects'

    @classmethod
    def is_default(cls):
        return cls.DEFAULT

    @classmethod
    def get_name(cls):
        return cls.NAME

    @classmethod
    def run(cls, package_name):
        r = requests.get(cls.API_URL, params=dict(pattern=package_name))
        if not r.ok:
            return None
        data = r.json()
        try:
            versions = [p['version'] for p in data['projects'] if p['version']]
        except KeyError:
            return None
        # there can be multiple matching projects, just return the highest version of all of them
        if versions:
            return sorted(versions, key=parse_version, reverse=True)[0]
        else:
            return None
