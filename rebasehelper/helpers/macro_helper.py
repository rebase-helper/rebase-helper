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

from typing import List

from specfile.rpm import Macros, Macro
from specfile.exceptions import RPMException


class MacroHelper:

    """Class for working with RPM macros"""

    MACROS_WHITELIST: List[str] = [
        '_bindir',
        '_datadir',
        '_includedir',
        '_infodir',
        '_initdir',
        '_libdir',
        '_libexecdir',
        '_localstatedir',
        '_mandir',
        '_sbindir',
        '_sharedstatedir',
        '_sysconfdir',
        'python2_sitelib',
        'python3_sitelib',
    ]

    @staticmethod
    def expand(s, default=None):
        # FIXME: Remove this wrapper
        try:
            return Macros.expand(s)
        except RPMException:
            return default

    @classmethod
    def expand_macros(cls, macros: List[Macro]) -> List[Macro]:
        """Expands values of multiple macros in-place.

        Args:
            macros: List of macros to be expanded.

        Returns:
            List of macros with expanded values
        """
        for macro in macros:
            macro.body = cls.expand(macro.body)
        return macros

    @staticmethod
    def substitute_path_with_macros(path: str, macros: List[Macro]) -> str:
        """Substitutes parts of a path with macros.

        Args:
            path: Path to be changed.
            macros: Macros which can be used as a substitution.

        Returns:
            Path expressed using macros.

        """
        for m in macros:
            if m.body and m.body in path:
                path = path.replace(m.body, '%{{{}}}'.format(m.name))

        return path

    @staticmethod
    def filter(macros: List[Macro], **kwargs) -> List[Macro]:
        """Finds all macros satisfying certain conditions.

        Args:
            macros: Macros to be filtered.
            **kwargs: Filters to be used.

        Returns:
            list: Macros satisfying the conditions.

        """
        def _test(macro: Macro):
            return all(getattr(macro, k[4:]) >= v if k.startswith('min_') else
                       getattr(macro, k[4:]) <= v if k.startswith('max_') else
                       getattr(macro, k) == v for k, v in kwargs.items())

        return [m for m in macros if _test(m)]
