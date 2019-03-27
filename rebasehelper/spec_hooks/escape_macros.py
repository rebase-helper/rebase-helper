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

from rebasehelper.specfile import BaseSpecHook


class EscapeMacrosHook(BaseSpecHook):
    """Spec hook escaping RPM macros in comments."""

    @staticmethod
    def _escape_macros_in_comment(line):
        """Escapes RPM macros in comment.

        Args:
            line (str): String to escape macros in.

        Returns:
            str: String with escaped macros.

        """
        comment = re.search(r"#.*", line)
        if not comment:
            return line

        start, end = comment.span()
        new_comment = re.sub(r'(?<!%)(%(?P<brace>{\??)?\w+(?(brace)}))', r'%\1', line[start:end])
        return line[:start] + new_comment

    @classmethod
    def run(cls, spec_file, rebase_spec_file, **kwargs):
        for _, section in rebase_spec_file.spec_content.sections:
            for index, line in enumerate(section):
                section[index] = cls._escape_macros_in_comment(line)
