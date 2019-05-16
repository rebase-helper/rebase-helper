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

import argparse
import sys

from rebasehelper.exceptions import RebaseHelperError, ParseError


class SilentArgumentParser(argparse.ArgumentParser):

    def error(self, message):
        raise ParseError(message)


class CustomHelpFormatter(argparse.HelpFormatter):

    def _expand_help(self, action):
        action.default = getattr(action, 'actual_default', None)
        if isinstance(action.default, list):
            default_str = ','.join(str(c) for c in action.default)
            action.default = default_str
        return super(CustomHelpFormatter, self)._expand_help(action)


class CustomAction(argparse.Action):
    def __init__(self, option_strings,
                 switch=False,
                 counter=False,
                 actual_default=None,
                 dest=None,
                 default=None,
                 nargs=None,
                 required=False,
                 type=None,  # pylint: disable=redefined-builtin
                 metavar=None,
                 help=None,  # pylint: disable=redefined-builtin
                 choices=None):

        super(CustomAction, self).__init__(
            option_strings=option_strings,
            dest=dest,
            default=default,
            required=required,
            metavar=metavar,
            type=type,
            help=help,
            choices=choices)

        self.switch = switch
        self.counter = counter
        self.nargs = 0 if self.switch or self.counter else nargs
        self.actual_default = actual_default

    def __call__(self, parser, namespace, values, option_string=None):
        if self.counter:
            value = getattr(namespace, self.dest, 0) + 1
        elif self.switch:
            value = True
        else:
            value = values
        setattr(namespace, self.dest, value)


class CustomArgumentParser(argparse.ArgumentParser):

    def _check_value(self, action, value):
        if isinstance(value, list):
            # converted value must be subset of the choices (if specified)
            if action.choices is not None and not set(value).issubset(action.choices):
                invalid = set(value).difference(action.choices)
                if len(invalid) == 1:
                    tup = repr(invalid.pop()), ', '.join(map(repr, action.choices))
                    msg = 'invalid choice: %s (choose from %s)' % tup
                else:
                    tup = ', '.join(map(repr, invalid)), ', '.join(map(repr, action.choices))
                    msg = 'invalid choices: %s (choose from %s)' % tup
                raise argparse.ArgumentError(action, msg)
        else:
            super(CustomArgumentParser, self)._check_value(action, value)

    def error(self, message):
        self.print_usage(sys.stderr)
        raise RebaseHelperError(message)
