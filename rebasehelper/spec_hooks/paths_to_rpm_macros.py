# -*- coding: utf-8 -*-
#
# This tool helps you to rebase package to the latest version
# Copyright (C) 2013-2014 Red Hat, Inc.
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
# Authors: Petr Hracek <phracek@redhat.com>
#          Tomas Hozza <thozza@redhat.com>

import six

from rebasehelper.specfile import BaseSpecHook
from rebasehelper.helpers.macro_helper import MacroHelper


class PathsToRPMMacrosHook(BaseSpecHook):
    """SpecHook for replacing paths to files with RPM macros."""

    NAME = 'Paths To RPM Macros'
    CATEGORIES = None

    MACROS_WHITELIST = [
        '_sysconfdir',
        '_bindir',
        '_libdir',
        '_libexecdir',
        '_sbindir',
        '_sharedstatedir',
        '_datadir',
        '_includedir',
        '_infodir',
        '_mandir',
        '_localstatedir',
        '_initdir',
    ]

    @classmethod
    def get_name(cls):
        return cls.NAME

    @classmethod
    def get_categories(cls):
        return cls.CATEGORIES

    @classmethod
    def _substitute_for_macro(cls, path, macros):
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

    @classmethod
    def _expand_macros(cls, macros):
        for macro in macros:
            macro['value'] = MacroHelper.expand(macro['value'])
        return macros

    @classmethod
    def run(cls, spec_file, rebase_spec_file, **kwargs):
        macros = [m for m in rebase_spec_file.macros if m['name'] in cls.MACROS_WHITELIST]
        macros = cls._expand_macros(macros)
        # ensure maximal greediness
        macros.sort(key=lambda k: len(k['value']), reverse=True)

        for sec_name, sec_content in six.iteritems(rebase_spec_file.spec_content.sections):
            if sec_name.startswith('%files'):
                for index, line in enumerate(sec_content):
                    rebase_spec_file.spec_content.sections[sec_name][index] = cls._substitute_for_macro(line, macros)
        rebase_spec_file.save()
