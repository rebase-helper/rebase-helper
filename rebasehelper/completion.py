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
import sys

from rebasehelper.cli import CLI
from rebasehelper.archive import Archive


class Completion:

    @staticmethod
    def extensions():
        archives = Archive.get_supported_archives()
        return [a.lstrip('.') for a in archives]

    @staticmethod
    def options():
        def get_delimiter(parser, action):
            if action.nargs == 0:
                return None
            fmt = parser._get_formatter()  # pylint: disable=protected-access
            usage = fmt._format_actions_usage([action], [])  # pylint: disable=protected-access
            option_string = action.option_strings[0]
            idx = usage.find(option_string)
            if idx == -1:
                return None
            return usage[idx + len(option_string)]
        parser = CLI.build_parser()
        result = []
        actions = parser._get_optional_actions() + parser._get_positional_actions()  # pylint: disable=protected-access
        for action in actions:
            if not action.option_strings:
                continue
            delimiter = get_delimiter(parser, action) or ''
            result.append(dict(
                options=[o + delimiter.strip() for o in action.option_strings],
                choices=action.choices or []))
        return result

    @classmethod
    def dump(cls):
        options = cls.options()
        return {
            # pattern list of extensions
            'RH_EXTENSIONS': '@({})'.format('|'.join(cls.extensions())),
            # array of options
            'RH_OPTIONS': '({})'.format(' '.join('"{}"'.format(' '.join(o['options'])) for o in options)),
            # array of choices of respective options
            'RH_CHOICES': '({})'.format(' '.join('"{}"'.format(' '.join(o['choices'])) for o in options)),
        }


def replace_placeholders(s, **kwargs):
    placeholder_re = re.compile(r'@(\w+)@')
    matches = list(placeholder_re.finditer(s))
    result = s
    for match in reversed(matches):
        replacement = kwargs.get(match.group(1), '')
        result = result[:match.start(0)] + replacement + result[match.end(0):]
    return result


def main():
    if len(sys.argv) != 3:
        return 1
    with open(sys.argv[1]) as f:
        s = f.read()
    s = replace_placeholders(s, **Completion.dump())
    with open(sys.argv[2], 'w') as f:
        f.write(s)
    return 0


if __name__ == '__main__':
    main()
