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

from rebasehelper.plugins.spec_hooks import BaseSpecHook
from rebasehelper.helpers.macro_helper import MacroHelper


class PathsToRPMMacros(BaseSpecHook):
    """SpecHook for replacing paths to files with RPM macros."""

    @classmethod
    def run(cls, spec_file, rebase_spec_file, **kwargs):
        macros = [m for m in rebase_spec_file.macros if m['name'] in MacroHelper.MACROS_WHITELIST]
        macros = MacroHelper.expand_macros(macros)
        # ensure maximal greediness
        macros.sort(key=lambda k: len(k['value']), reverse=True)

        for sec_name, sec_content in rebase_spec_file.spec_content.sections:
            if sec_name.startswith('%files'):
                for index, line in enumerate(sec_content):
                    new_path = MacroHelper.substitute_path_with_macros(line, macros)
                    sec_content[index] = new_path
        rebase_spec_file.save()
