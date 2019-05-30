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

import pytest  # type: ignore

from rebasehelper.helpers.rpm_helper import RpmHelper


class TestRpmHelper:
    """ RpmHelper class tests. """

    def test_is_package_installed_existing(self):
        assert RpmHelper.is_package_installed('glibc') is True
        assert RpmHelper.is_package_installed('coreutils') is True

    def test_is_package_installed_non_existing(self):
        assert RpmHelper.is_package_installed('non-existing-package') is False
        assert RpmHelper.is_package_installed('another-non-existing-package') is False

    def test_all_packages_installed_existing(self):
        assert RpmHelper.all_packages_installed(['glibc', 'coreutils']) is True

    def test_all_packages_installed_one_non_existing(self):
        assert RpmHelper.all_packages_installed(['glibc', 'coreutils', 'non-existing-package']) is False

    @pytest.mark.parametrize('nevra, name, epoch, version, release, arch', [
        ('libtiff-static-4.0.7-5.fc26.x86_64', 'libtiff-static', None, '4.0.7', '5.fc26', 'x86_64'),
        ('libtiff-debuginfo-4.0.8-1.fc25', 'libtiff-debuginfo', None, '4.0.8', '1.fc25', None),
        ('libtiff-tools.i686', 'libtiff-tools', None, None, None, 'i686'),
        ('libtiff-devel', 'libtiff-devel', None, None, None, None),
        ('libpng-devel-debuginfo-2:1.6.31-1.fc27.aarch64', 'libpng-devel-debuginfo', 2, '1.6.31', '1.fc27', 'aarch64'),
        (
                'python-genmsg-0.3.10-14.20130617git95ca00d.fc28',
                'python-genmsg',
                None,
                '0.3.10',
                '14.20130617git95ca00d.fc28',
                None,
        ),
        (
                'golang-github-MakeNowJust-heredoc-devel-0-0.9.gitbb23615.fc28.noarch',
                'golang-github-MakeNowJust-heredoc-devel',
                None,
                '0',
                '0.9.gitbb23615.fc28',
                'noarch',
        ),
    ], ids=[
        'libtiff-static-4.0.7-5.fc26.x86_64',
        'libtiff-debuginfo-4.0.8-1.fc25',
        'libtiff-tools.i686',
        'libtiff-devel',
        'libpng-devel-debuginfo-2:1.6.31-1.fc27.aarch64',
        'python-genmsg-0.3.10-14.20130617git95ca00d.fc28',
        'golang-github-MakeNowJust-heredoc-devel-0-0.9.gitbb23615.fc28.noarch',
    ])
    def test_split_nevra(self, nevra, name, epoch, version, release, arch):
        assert RpmHelper.split_nevra(nevra) == dict(name=name, epoch=epoch, version=version,
                                                    release=release, arch=arch)
