# -*- coding: utf-8 -*-
#
# This tool helps you to rebase package to the latest version
# Copyright (C) 2013-2014 Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# he Free Software Foundation; either version 2 of the License, or
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

import argparse
import logging
import sys

import six

from rebasehelper.options import OPTIONS, traverse_options
from rebasehelper.constants import PROGRAM_DESCRIPTION, NEW_ISSUE_LINK
from rebasehelper.version import VERSION
from rebasehelper.application import Application
from rebasehelper.logger import logger, main_handler, output_tool_handler
from rebasehelper.exceptions import RebaseHelperError
from rebasehelper.utils import ConsoleHelper
from rebasehelper.config import Config


class CustomHelpFormatter(argparse.HelpFormatter):

    def _expand_help(self, action):
        action.default = getattr(action, 'actual_default', None)
        if isinstance(action.default, list):
            default_str = ','.join([str(c) for c in action.default])
            action.default = default_str
        return super(CustomHelpFormatter, self)._expand_help(action)


class CustomAction(argparse.Action):
    def __init__(self, option_strings,
                 switch=False,
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
        self.nargs = 0 if self.switch else nargs
        self.actual_default = actual_default

    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, True if self.switch else values)


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


class CLI(object):
    """ Class for processing data from commandline """

    @staticmethod
    def build_parser():
        parser = CustomArgumentParser(description=PROGRAM_DESCRIPTION,
                                      formatter_class=CustomHelpFormatter)

        group = parser.add_mutually_exclusive_group()
        current_group = 0
        for option in traverse_options(OPTIONS):
            option_kwargs = dict(option)
            for key in ("group", "default", "name"):
                if key in option_kwargs:
                    del option_kwargs[key]

            if "group" in option:
                if current_group != option["group"]:
                    current_group = option["group"]
                    group = parser.add_mutually_exclusive_group()
                actions_container = group
            else:
                actions_container = parser

            # default is set to SUPPRESS to prevent arguments which were not specified on command line from being
            # added to namespace. This allows rebase-helper to determine which arguments are used with their
            # default value. This is later used for merging CLI arguments with config.
            actions_container.add_argument(*option["name"], action=CustomAction, default=argparse.SUPPRESS,
                                           actual_default=option.get("default"), **option_kwargs)

        return parser

    def __init__(self, args=None):
        """parse arguments"""
        if args is None:
            args = sys.argv[1:]
        # sanitize builder options to prevent ArgumentParser from processing them
        for opt in ['--builder-options', '--srpm-builder-options']:
            try:
                i = args.index(opt)
                args[i:i+2] = ['='.join(args[i:i+2])]
            except ValueError:
                continue
        self.parser = CLI.build_parser()
        self.args = self.parser.parse_args(args)

    def __getattr__(self, name):
        try:
            return getattr(self.args, name)
        except AttributeError:
            return object.__getattribute__(self, name)


class CliHelper(object):

    @staticmethod
    def run():
        debug_log_file = None
        try:
            # be verbose until debug_log_file is created
            cli = CLI()
            if hasattr(cli, 'version'):
                logger.info(VERSION)
                sys.exit(0)

            config = Config(getattr(cli, 'config-file', None))
            config.merge(cli)
            for handler in [main_handler, output_tool_handler]:
                handler.set_terminal_background()

            ConsoleHelper.use_colors = ConsoleHelper.should_use_colors(config)
            execution_dir, results_dir, debug_log_file = Application.setup(config)
            if not config.verbose:
                main_handler.setLevel(logging.INFO)
            app = Application(config, execution_dir, results_dir, debug_log_file)
            app.run()
        except KeyboardInterrupt:
            logger.info('Interrupted by user')
        except RebaseHelperError as e:
            if e.msg:
                logger.error('%s', e.msg)
            else:
                logger.error('%s', six.text_type(e))
            sys.exit(1)
        except SystemExit as e:
            sys.exit(e.code)
        except BaseException:
            if debug_log_file:
                logger.error('rebase-helper failed due to an unexpected error. Please report this problem'
                             '\nusing the following link: %s'
                             '\nand include the content of'
                             '\n\'%s\''
                             '\nfile in the report.'
                             '\nThank you!',
                             NEW_ISSUE_LINK, debug_log_file)
            else:
                logger.error('rebase-helper failed due to an unexpected error. Please report this problem'
                             '\nusing the following link: %s'
                             '\nand include the traceback following this message in the report.'
                             '\nThank you!',
                             NEW_ISSUE_LINK)
            logger.trace('', exc_info=1)
            sys.exit(1)

        sys.exit(0)


if __name__ == '__main__':
    x = CLI()
