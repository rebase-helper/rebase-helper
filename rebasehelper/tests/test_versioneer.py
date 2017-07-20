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

import pytest

from pkg_resources import parse_version

from rebasehelper.versioneer import versioneers_runner
from rebasehelper.versioneers.anitya_versioneer import AnityaVersioneer


class TestVersioneer(object):

    @pytest.mark.parametrize('package, min_version', [
        ('vim-go', 'v1.13'),
        ('libtiff', '4.0.8'),
    ], ids=[
        'vim-go>=v1.13',
        'libtiff>=4.0.8',
    ])
    def test_anitya_versioneer(self, package, min_version):
        assert AnityaVersioneer.get_name() in versioneers_runner.versioneers
        version = versioneers_runner.run(AnityaVersioneer.get_name(), package)
        assert parse_version(version) >= parse_version(min_version)
