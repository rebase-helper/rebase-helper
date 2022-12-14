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

import logging
import os
from typing import Any, List, cast

import rpm  # type: ignore

from rebasehelper.constants import ENCODING
from rebasehelper.logger import CustomLogger
from rebasehelper.helpers.process_helper import ProcessHelper


logger: CustomLogger = cast(CustomLogger, logging.getLogger(__name__))


class RpmHeader:
    def __init__(self, hdr: rpm.hdr) -> None:
        self.hdr = hdr

    def __getattr__(self, item: str) -> Any:
        def decode(s):
            if isinstance(s, bytes):
                return s.decode(ENCODING)
            return s
        result = getattr(self.hdr, item)
        if isinstance(result, list):
            return [decode(x) for x in result]
        return decode(result)


class RpmHelper:

    """Class for working with RPM database and packages."""

    ARCHES: List[str] = []

    @staticmethod
    def is_package_installed(pkg_name=None):
        """Checks whether a package is installed.

        Args:
            pkg_name (str): Name of the package.

        Returns:
            bool: Whether the package is installed.

        """
        ts = rpm.TransactionSet()
        mi = ts.dbMatch('provides', pkg_name)
        return len(mi) > 0

    @staticmethod
    def all_packages_installed(pkg_names=None):
        """Checks if all specified packages are installed.

        Args:
            pkg_names (list): List of package names to check.

        Returns:
            bool: True if all packages are installed, False otherwise.

        """
        for pkg in pkg_names:
            if not RpmHelper.is_package_installed(pkg):
                return False
        return True

    @staticmethod
    def install_build_dependencies(spec_path=None, assume_yes=False):
        """Installs build dependencies of a package using dnf.

        Args:
            spec_path (str): Absolute path to the SPEC file.
            assume_yes (bool): Whether to automatically answer 'yes' to all questions.

        Returns:
            int: Exit code of the subprocess run.

        """
        cmd = ['dnf', 'builddep', spec_path]
        if os.geteuid() != 0:
            logger.warning("Authentication required to install build dependencies using '%s'", ' '.join(cmd))
            cmd = ['pkexec'] + cmd
        if assume_yes:
            cmd.append('-y')
        return ProcessHelper.run_subprocess(cmd)

    @staticmethod
    def get_header_from_rpm(rpm_name):
        """Gets an RPM header from the given RPM package.

        Args:
            rpm_name (str): Path to the package.

        Returns:
            RpmHeader: Header object obtained from the package.

        """
        ts = rpm.TransactionSet()
        # disable signature checking
        ts.setVSFlags(rpm._RPMVSF_NOSIGNATURES)  # pylint: disable=protected-access
        with open(rpm_name, "r", encoding=ENCODING) as f:
            hdr = ts.hdrFromFdno(f)
        return RpmHeader(hdr)
