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
