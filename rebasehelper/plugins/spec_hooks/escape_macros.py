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

from rebasehelper.plugins.spec_hooks import BaseSpecHook


class EscapeMacros(BaseSpecHook):
    """Spec hook escaping RPM macros in comments."""

    @classmethod
    def run(cls, spec_file, rebase_spec_file, **kwargs):
        for sec_name, section in rebase_spec_file.spec_content.sections:
            for index, line in enumerate(section):
                start, end = spec_file.spec_content.get_comment_span(line, sec_name)
                new_comment = re.sub(r'(?<!%)(%(?P<brace>{\??)?\w+(?(brace)}))', r'%\1', line[start:end])
                section[index] = line[:start] + new_comment
