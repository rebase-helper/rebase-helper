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

from rebasehelper.constants import PROGRAM_DESCRIPTION, NEW_ISSUE_LINK
from rebasehelper.application import Application
from rebasehelper.logger import logger, LoggerHelper
from rebasehelper.exceptions import RebaseHelperError
from rebasehelper.build_helper import Builder
from rebasehelper.checker import checkers_runner
from rebasehelper.output_tool import OutputTool


class CustomHelpFormatter(argparse.HelpFormatter):

    def _format_actions_usage(self, actions, groups):
        text = super(CustomHelpFormatter, self)._format_actions_usage(actions, groups)
        return text.replace(' BUILDER_OPTIONS', '=BUILDER_OPTIONS')

    def _format_action_invocation(self, action):
        text = super(CustomHelpFormatter, self)._format_action_invocation(action)
        return text.replace(' BUILDER_OPTIONS', '=BUILDER_OPTIONS')

    def _expand_help(self, action):
        if isinstance(action.default, list):
            default_str = ','.join([str(c) for c in action.default])
            action.default = default_str
        return super(CustomHelpFormatter, self)._expand_help(action)


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
        parser.add_argument(
            "-v",
            "--verbose",
            default=False,
            action="store_true",
            help="be more verbose (recommended)"
        )
        parser.add_argument(
            "-p",
            "--patch-only",
            default=False,
            action="store_true",
            help="only apply patches"
        )
        parser.add_argument(
            "-b",
            "--build-only",
            default=False,
            action="store_true",
            help="only build SRPM and RPMs"
        )
        parser.add_argument(
            "--buildtool",
            choices=Builder.get_supported_tools(),
            default=Builder.get_default_tool(),
            help="build tool to use, defaults to %(default)s"
        )
        parser.add_argument(
            "--pkgcomparetool",
            choices=checkers_runner.get_supported_tools(),
            default=checkers_runner.get_default_tools(),
            type=lambda s: s.split(','),
            help="set of tools to use for package comparison, defaults to %(default)s"
        )
        parser.add_argument(
            "--outputtool",
            choices=OutputTool.get_supported_tools(),
            default=OutputTool.get_default_tool(),
            help="tool to use for formatting rebase output, defaults to %(default)s"
        )
        parser.add_argument(
            "-w",
            "--keep-workspace",
            default=False,
            action="store_true",
            help="do not remove workspace directory after finishing"
        )
        parser.add_argument(
            "--not-download-sources",
            default=False,
            action="store_true",
            help="do not download sources"
        )
        parser.add_argument(
            "-c",
            "--continue",
            default=False,
            action="store_true",
            dest='cont',
            help="continue previously interrupted rebase"
        )
        parser.add_argument(
            "sources",
            metavar='SOURCES',
            help="new upstream sources"
        )
        parser.add_argument(
            "--non-interactive",
            default=False,
            action="store_true",
            dest='non_interactive',
            help="do not interact with user"
        )
        parser.add_argument(
            "--comparepkgs-only",
            default=False,
            dest="comparepkgs",
            metavar="COMPAREPKGS_DIR",
            help="compare already built packages, %(metavar)s must be a directory "
                 "with the following structure: <dir_name>/{old,new}/RPM"
        )
        parser.add_argument(
            "--builds-nowait",
            default=False,
            action="store_true",
            help="do not wait for koji or copr builds to finish"
        )
        # deprecated argument, kept for backward compatibility
        parser.add_argument(
            "--fedpkg-build-tasks",
            dest="fedpkg_build_tasks",
            type=lambda s: s.split(','),
            help=argparse.SUPPRESS
        )
        parser.add_argument(
            "--build-tasks",
            dest="build_tasks",
            metavar="OLD_TASK,NEW_TASK",
            type=lambda s: s.split(','),
            help="comma-separated koji or copr task ids"
        )
        parser.add_argument(
            "--results-dir",
            help="directory where rebase-helper output will be stored"
        )
        parser.add_argument(
            "--build-retries",
            default=2,
            help="number of retries of a failed build, defaults to %(default)d",
            type=int
        )
        parser.add_argument(
            "--builder-options",
            default=None,
            metavar="BUILDER_OPTIONS",
            help="enable arbitrary local builder option(s), enclose %(metavar)s in quotes "
                 "and note that = before it is mandatory"
        )
        return parser

    def __init__(self, args=None):
        """parse arguments"""
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
            handler = LoggerHelper.add_stream_handler(logger, logging.DEBUG)
            if "--builder-options" in sys.argv[1:]:
                raise RebaseHelperError('Wrong format of --builder-options. It must be in the following form:'
                                        ' --builder-options="--desired-builder-option".')
            cli = CLI()
            execution_dir, results_dir, debug_log_file, report_log_file = Application.setup(cli)
            if not cli.verbose:
                handler.setLevel(logging.INFO)
            app = Application(cli, execution_dir, results_dir, debug_log_file, report_log_file)
            app.run()
        except KeyboardInterrupt:
            logger.info('\nInterrupted by user')
        except RebaseHelperError as e:
            if e.args:
                logger.error('\n%s', e.args[0] % e.args[1:])
            else:
                logger.error('\n%s', six.text_type(e))
            sys.exit(1)
        except SystemExit as e:
            sys.exit(e.code)
        except BaseException:
            if debug_log_file:
                logger.error('\nrebase-helper failed due to an unexpected error. Please report this problem'
                             '\nusing the following link: %s'
                             '\nand include the content of'
                             '\n\'%s\''
                             '\nfile in the report.'
                             '\nThank you!',
                             NEW_ISSUE_LINK, debug_log_file)
            else:
                logger.error('\nrebase-helper failed due to an unexpected error. Please report this problem'
                             '\nusing the following link: %s'
                             '\nand include the traceback following this message in the report.'
                             '\nThank you!',
                             NEW_ISSUE_LINK)
            logger.debug('\n', exc_info=1)
            sys.exit(1)

        sys.exit(0)

if __name__ == '__main__':
    x = CLI()
