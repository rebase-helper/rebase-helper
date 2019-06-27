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

import re

import rpm  # type: ignore

from typing import List

from pkg_resources import parse_version

from rebasehelper.helpers.console_helper import ConsoleHelper


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
        try:
            return rpm.expandMacro(s)
        except rpm.error:
            return default

    @classmethod
    def purge_macro(cls, macro: str) -> None:
        m = '%{{{}}}'.format(macro)
        while cls.expand(m, m) != m:
            rpm.delMacro(macro)

    @classmethod
    def expand_macros(cls, macros):
        """Expands values of multiple macros.

        Args:
            macros (list): List of macros to be expanded, macros are
                represented as dicts.

        Returns:
            list: List of macros with expanded values.

        """
        for macro in macros:
            macro['value'] = cls.expand(macro['value'])
        return macros

    @staticmethod
    def substitute_path_with_macros(path, macros):
        """Substitutes parts of a path with macros.

        Args:
            path (str): Path to be changed.
            macros (list): Macros which can be used as a substitution.

        Returns:
            str: Path expressed using macros.

        """
        for m in macros:
            if m['value'] and m['value'] in path:
                path = path.replace(m['value'], '%{{{}}}'.format(m['name']))

        return path

    @staticmethod
    def dump():
        """Gets list of all defined macros.

        Returns:
            list: All defined macros.

        """
        macro_re = re.compile(
            r'''
            ^\s*
            (?P<level>-?\d+)
            (?P<used>=|:)
            [ ]
            (?P<name>\w+)
            (?P<options>\(.+?\))?
            [\t]
            (?P<value>.*)
            $
            ''',
            re.VERBOSE)

        with ConsoleHelper.Capturer(stderr=True) as capturer:
            rpm.expandMacro('%dump')

        macros = []

        def add_macro(properties):
            macro = dict(properties)
            macro['used'] = macro['used'] == '='
            macro['level'] = int(macro['level'])
            if parse_version(rpm.__version__) < parse_version('4.13.90'):
                # in RPM < 4.13.90 level of some macros is decreased by 1
                if macro['level'] == -1:
                    # this could be macro with level -1 or level 0, we can not be sure
                    # so just duplicate the macro for both levels
                    macros.append(macro)
                    macro = dict(macro)
                    macro['level'] = 0
                    macros.append(macro)
                elif macro['level'] in (-14, -16):
                    macro['level'] += 1
                    macros.append(macro)
                else:
                    macros.append(macro)
            else:
                macros.append(macro)

        for line in capturer.stderr.split('\n'):
            match = macro_re.match(line)
            if match:
                add_macro(match.groupdict())

        return macros

    @staticmethod
    def filter(macros, **kwargs):
        """Finds all macros satisfying certain conditions.

        Args:
            macros (list): Macros to be filtered.
            **kwargs: Filters to be used.

        Returns:
            list: Macros satisfying the conditions.

        """
        def _test(macro):
            return all(macro.get(k[4:]) >= v if k.startswith('min_') else
                       macro.get(k[4:]) <= v if k.startswith('max_') else
                       macro.get(k) == v for k, v in kwargs.items())

        return [m for m in macros if _test(m)]
