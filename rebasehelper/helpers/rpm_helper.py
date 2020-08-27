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
import re
import tempfile
from typing import Any, Dict, List, cast

import rpm  # type: ignore

from rebasehelper.constants import SYSTEM_ENCODING
from rebasehelper.exceptions import RebaseHelperError
from rebasehelper.logger import CustomLogger
from rebasehelper.helpers.macro_helper import MacroHelper
from rebasehelper.helpers.process_helper import ProcessHelper
from rebasehelper.helpers.console_helper import ConsoleHelper


logger: CustomLogger = cast(CustomLogger, logging.getLogger(__name__))


class RpmHeader:
    def __init__(self, hdr: rpm.hdr) -> None:
        self.hdr = hdr

    def __getattr__(self, item: str) -> Any:
        def decode(s):
            if isinstance(s, bytes):
                return s.decode(SYSTEM_ENCODING)
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
        with open(rpm_name, "r") as f:
            hdr = ts.hdrFromFdno(f)
        return RpmHeader(hdr)

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
                except ValueError as e:
                    output = capturer.stderr.strip().split('\n') if capturer else []
                    if len(output) == 1:
                        output = output[0]
                    raise RebaseHelperError('Failed to parse SPEC file{0}'.format(
                        ': ' + str(output) if output else '')) from e
                return result

    @classmethod
    def get_rpm_spec(cls, path: str, sourcedir: str, predefined_macros: Dict[str, str]) -> rpm.spec:
        # reset all macros and settings
        rpm.reloadConfig()
        # ensure that %{_sourcedir} macro is set to proper location
        MacroHelper.purge_macro('_sourcedir')
        rpm.addMacro('_sourcedir', sourcedir)
        # add predefined macros
        for macro, value in predefined_macros.items():
            rpm.addMacro(macro, value)
        try:
            spec = cls.parse_spec(path, flags=rpm.RPMSPEC_ANYARCH)
        except RebaseHelperError:
            # try again with RPMSPEC_FORCE flag (the default)
            spec = cls.parse_spec(path)
        return spec
