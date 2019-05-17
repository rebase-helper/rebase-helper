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
import sys

from argparse import SUPPRESS
from typing import List

from rebasehelper.cli import CLI
from rebasehelper.constants import CONFIG_PATH, CONFIG_FILENAME


class SampleConfig:

    DESCRIPTION: List[str] = [
        '# sample configuration file for rebase-helper',
        '# copy this file to {} and edit it as necessary'.format(os.path.join(CONFIG_PATH, CONFIG_FILENAME)),
        '# all options specified here can be overridden on the command line',
    ]

    BLACKLIST: List[str] = [
        'help',
        'version',
        'config-file',
    ]

    @classmethod
    def generate(cls):
        result = cls.DESCRIPTION + ['']
        parser = CLI.build_parser()
        result.append('[general]')
        for action in parser._get_optional_actions():  # pylint: disable=protected-access
            if action.help is SUPPRESS:
                continue
            fmt = parser._get_formatter()  # pylint: disable=protected-access
            opts = action.option_strings
            if len(opts) > 1:
                opts.pop(0)
            name = opts[0].lstrip('-')
            if name in cls.BLACKLIST:
                continue
            value = getattr(action, 'actual_default', None)
            if isinstance(value, list):
                value = ','.join(value)
            args = fmt._format_args(action, action.dest.upper())  # pylint: disable=protected-access
            result.append('')
            result.append('# {}'.format(fmt._expand_help(action)))  # pylint: disable=protected-access
            if args:
                result.append('# synopsis: {} = {}'.format(name, args))
            result.append('{} = {}'.format(name, value if value is not None else ''))
        return '\n'.join(result)


def main():
    if len(sys.argv) != 2:
        return 1
    s = SampleConfig.generate()
    with open(sys.argv[1], 'w') as f:
        f.write(s)
    return 0


if __name__ == '__main__':
    main()
