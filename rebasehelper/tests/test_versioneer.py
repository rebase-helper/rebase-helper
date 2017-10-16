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
from rebasehelper.versioneers.pypi_versioneer import PyPIVersioneer
from rebasehelper.versioneers.npmjs_versioneer import NPMJSVersioneer
from rebasehelper.versioneers.cpan_versioneer import CPANVersioneer


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
        version = versioneers_runner.run(AnityaVersioneer.get_name(), package, None)
        assert parse_version(version) >= parse_version(min_version)

    @pytest.mark.parametrize('package, min_version', [
        ('python-m2r', '0.1.7'),
        ('pyodbc', '4.0.17'),
    ], ids=[
        'python-m2r>=0.1.7',
        'pyodbc>=4.0.17',
    ])
    def test_pypi_versioneer(self, package, min_version):
        assert PyPIVersioneer.get_name() in versioneers_runner.versioneers
        version = versioneers_runner.run(PyPIVersioneer.get_name(), package, None)
        assert parse_version(version) >= parse_version(min_version)

    @pytest.mark.parametrize('package, min_version', [
        ('nodejs-read-pkg', '1.1.0'),
        ('uglify-js', '1.2.1')
    ], ids=[
        'nodejs-read-pkg>=1.1.0',
        'uglify-js>=1.2.1'
    ])
    def test_npmjs_versioneer(self, package, min_version):
        assert NPMJSVersioneer.get_name() in versioneers_runner.versioneers
        version = versioneers_runner.run(NPMJSVersioneer.get_name(), package, None)
        assert parse_version(version) >= parse_version(min_version)

    @pytest.mark.parametrize('package, min_version', [
        ('perl-Task-Kensho-Toolchain', '0.39'),
        ('perl-Data-GUID', '0.049')
    ], ids=[
        'perl-Task-Kensho-Toolchain>=0.39',
        'perl-Data-GUID>=0.049'
    ])
    def test_cpan_versioneer(self, package, min_version):
        assert CPANVersioneer.get_name() in versioneers_runner.versioneers
        version = versioneers_runner.run(CPANVersioneer.get_name(), package, None)
        assert parse_version(version) >= parse_version(min_version)
