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

import os
import re
import tempfile

import rpm  # type: ignore

from typing import List

from rebasehelper.constants import SYSTEM_ENCODING
from rebasehelper.exceptions import RebaseHelperError
from rebasehelper.logger import logger
from rebasehelper.helpers.macro_helper import MacroHelper
from rebasehelper.helpers.process_helper import ProcessHelper
from rebasehelper.helpers.console_helper import ConsoleHelper


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
            rpm.hdr: Header object obtained from the package.

        :return:
        """
        ts = rpm.TransactionSet()
        # disable signature checking
        ts.setVSFlags(rpm._RPMVSF_NOSIGNATURES)  # pylint: disable=protected-access
        with open(rpm_name, "r") as f:
            return ts.hdrFromFdno(f)

    @classmethod
    def get_info_from_rpm(cls, rpm_name, info):
        """Gets package name from an RPM file.

        Args:
            rpm_name (str): Path to the file.
            info (bool): Which part of the RPM header to return.

        Returns:
            str: Package name obtained from the RPM file.

        :return:
        """
        h = cls.get_header_from_rpm(rpm_name)
        return cls.decode(h[info])

    @staticmethod
    def get_arches():
        """Gets list of all known architectures"""
        arches = ['aarch64', 'noarch', 'ppc', 'riscv64', 's390', 's390x', 'src', 'x86_64']
        macros = MacroHelper.dump()
        macros = [m for m in macros if m['name'] in ('ix86', 'arm', 'mips', 'sparc', 'alpha', 'power64')]
        for m in macros:
            arches.extend(MacroHelper.expand(m['value'], '').split())
        return arches

    @classmethod
    def split_nevra(cls, s):
        """Splits string into name, epoch, version, release and arch components"""
        regexps = [
            ('NEVRA', re.compile(r'^([^:]+)-(([0-9]+):)?([^-:]+)-(.+)\.([^.]+)$')),
            ('NEVR', re.compile(r'^([^:]+)-(([0-9]+):)?([^-:]+)-(.+)()$')),
            ('NA', re.compile(r'^([^:]+)()()()()\.([^.]+)$')),
            ('N', re.compile(r'^([^:]+)()()()()()$')),
        ]
        if not cls.ARCHES:
            cls.ARCHES = cls.get_arches()
        for pattern, regexp in regexps:
            match = regexp.match(s)
            if not match:
                continue
            name = match.group(1) or None
            epoch = match.group(3) or None
            if epoch:
                epoch = int(epoch)
            version = match.group(4) or None
            release = match.group(5) or None
            arch = match.group(6) or None
            if pattern == 'NEVRA' and arch not in cls.ARCHES:
                # unknown arch, let's assume it's actually dist
                continue
            return dict(name=name, epoch=epoch, version=version, release=release, arch=arch)
        raise RebaseHelperError('Unable to split string into NEVRA.')

    @classmethod
    def parse_spec(cls, path, flags=None):
        with open(path, 'rb') as orig:
            with tempfile.NamedTemporaryFile() as tmp:
                # remove BuildArch to workaround rpm bug
                tmp.write(b''.join(l for l in orig.readlines() if not l.startswith(b'BuildArch')))
                tmp.flush()
                capturer = None
                try:
                    with ConsoleHelper.Capturer(stderr=True) as capturer:
                        result = rpm.spec(tmp.name, flags) if flags is not None else rpm.spec(tmp.name)
                except ValueError:
                    output = capturer.stderr.strip().split('\n') if capturer else []
                    if len(output) == 1:
                        output = output[0]
                    raise RebaseHelperError('Failed to parse SPEC file{0}'.format(': ' + str(output) if output else ''))
                return result

    @classmethod
    def get_rpm_spec(cls, path) -> rpm.spec:
        try:
            spec = cls.parse_spec(path, flags=rpm.RPMSPEC_ANYARCH)
        except RebaseHelperError:
            # try again with RPMSPEC_FORCE flag (the default)
            spec = cls.parse_spec(path)
        return spec

    @classmethod
    def decode(cls, data):
        if isinstance(data, bytes):
            return data.decode(SYSTEM_ENCODING)
        return data
