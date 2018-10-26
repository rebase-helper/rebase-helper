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
    def run(cls, spec_file, rebase_spec_file, **kwargs):
        macros = [m for m in rebase_spec_file.macros if m['name'] in cls.MACROS_WHITELIST]
        macros = MacroHelper.expand_macros(macros)
        # ensure maximal greediness
        macros.sort(key=lambda k: len(k['value']), reverse=True)

        for sec_name, sec_content in six.iteritems(rebase_spec_file.spec_content.sections):
            if sec_name.startswith('%files'):
                for index, line in enumerate(sec_content):
                    new_path = MacroHelper.substitute_path_with_macros(line, macros)
                    rebase_spec_file.spec_content.sections[sec_name][index] = new_path
        rebase_spec_file.save()
