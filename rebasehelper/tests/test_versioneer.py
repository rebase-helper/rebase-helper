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

import pytest

from pkg_resources import parse_version

from rebasehelper.versioneer import versioneers_runner
from rebasehelper.versioneers.anitya_versioneer import AnityaVersioneer
from rebasehelper.versioneers.pypi_versioneer import PyPIVersioneer
from rebasehelper.versioneers.npmjs_versioneer import NPMJSVersioneer
from rebasehelper.versioneers.cpan_versioneer import CPANVersioneer
from rebasehelper.versioneers.hackage_versioneer import HackageVersioneer


class TestVersioneer(object):

    @pytest.mark.parametrize('package, min_version', [
        ('vim-go', 'v1.13'),
        ('libtiff', '4.0.8'),
    ], ids=[
        'vim-go>=v1.13',
        'libtiff>=4.0.8',
    ])
    @pytest.mark.integration
    def test_anitya_versioneer(self, package, min_version):
        assert AnityaVersioneer.name in versioneers_runner.versioneers
        AnityaVersioneer.API_URL = 'https://integration:4430/versioneers'
        version = versioneers_runner.run(AnityaVersioneer.name, package, None)
        assert parse_version(version) >= parse_version(min_version)

    @pytest.mark.parametrize('package, min_version', [
        ('python-m2r', '0.1.7'),
        ('pyodbc', '4.0.17'),
    ], ids=[
        'python-m2r>=0.1.7',
        'pyodbc>=4.0.17',
    ])
    @pytest.mark.integration
    def test_pypi_versioneer(self, package, min_version):
        assert PyPIVersioneer.name in versioneers_runner.versioneers
        PyPIVersioneer.API_URL = 'https://integration:4430/versioneers'
        version = versioneers_runner.run(PyPIVersioneer.name, package, None)
        assert parse_version(version) >= parse_version(min_version)

    @pytest.mark.parametrize('package, min_version', [
        ('nodejs-read-pkg', '1.1.0'),
        ('uglify-js', '1.2.1')
    ], ids=[
        'nodejs-read-pkg>=1.1.0',
        'uglify-js>=1.2.1'
    ])
    @pytest.mark.integration
    def test_npmjs_versioneer(self, package, min_version):
        assert NPMJSVersioneer.name in versioneers_runner.versioneers
        NPMJSVersioneer.API_URL = 'https://integration:4430/versioneers'
        version = versioneers_runner.run(NPMJSVersioneer.name, package, None)
        assert parse_version(version) >= parse_version(min_version)

    @pytest.mark.parametrize('package, min_version', [
        ('perl-Task-Kensho-Toolchain', '0.39'),
        ('perl-Data-GUID', '0.049')
    ], ids=[
        'perl-Task-Kensho-Toolchain>=0.39',
        'perl-Data-GUID>=0.049'
    ])
    @pytest.mark.integration
    def test_cpan_versioneer(self, package, min_version):
        assert CPANVersioneer.name in versioneers_runner.versioneers
        CPANVersioneer.API_URL = 'https://integration:4430/versioneers'
        version = versioneers_runner.run(CPANVersioneer.name, package, None)
        assert parse_version(version) >= parse_version(min_version)

    @pytest.mark.parametrize('package, min_version', [
        ('ghc-clock', '0.2.0.0'),
        ('cab', '0.2.17')
    ], ids=[
        'ghc-clock>=0.2.0.0',
        'cab>=0.2.17'
    ])
    @pytest.mark.integration
    def test_hackage_versioneer(self, package, min_version):
        assert HackageVersioneer.name in versioneers_runner.versioneers
        HackageVersioneer.API_URL = 'https://integration:4430/versioneers'
        version = versioneers_runner.run(HackageVersioneer.name, package, None)
        assert parse_version(version) >= parse_version(min_version)
