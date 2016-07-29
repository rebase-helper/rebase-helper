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


class ArgumentParser(argparse.ArgumentParser):

    def error(self, message):
        self.print_usage(sys.stderr)
        raise RebaseHelperError(message)


class CLI(object):
    """ Class for processing data from commandline """

    def __init__(self, args=None):
        """parse arguments"""
        self.parser = ArgumentParser(description=PROGRAM_DESCRIPTION)
        self.add_args()
        if "--builder-options" in sys.argv[1:]:
            raise RebaseHelperError("Wrong format of --builder-options. It must be in following form"
                                    " --builder-options=\"--desired-builder-option\". \n")
        self.args = self.parser.parse_args(args)

    def add_args(self):
        self.parser.add_argument(
            "-v",
            "--verbose",
            default=False,
            action="store_true",
            help="Output is more verbose (recommended)"
        )
        self.parser.add_argument(
            "-p",
            "--patch-only",
            default=False,
            action="store_true",
            help="Only apply patches"
        )
        self.parser.add_argument(
            "-b",
            "--build-only",
            default=False,
            action="store_true",
            help="Only build SRPM and RPMs"
        )
        self.parser.add_argument(
            "--buildtool",
            default="mock",
            help="Select the build tool [mock(default)|rpmbuild|fedpkg|copr]"
        )
        self.parser.add_argument(
            "--pkgcomparetool",
            default=False,
            help="Select the tool for comparing two packages [pkgdiff, rpmdiff, abipkgdiff, csmock]"
        )
        self.parser.add_argument(
            "--outputtool",
            default="text",
            help="Select the tool for showing information from rebase-helper process [text, json]"
        )
        self.parser.add_argument(
            "-w",
            "--keep-workspace",
            default=False,
            action="store_true",
            help="Use if you want rebase-helper to keep the workspace directory after finishing"
        )
        self.parser.add_argument(
            "--not-download-sources",
            default=False,
            action="store_true",
            help="Suppress to download sources from web"
        )
        self.parser.add_argument(
            "-c",
            "--continue",
            default=False,
            action="store_true",
            dest='cont',
            help="Use if you want to continue with rebase previously interrupted"
        )
        self.parser.add_argument(
            "sources",
            metavar='SOURCES',
            help="Specify new upstream sources"
        )
        self.parser.add_argument(
            "--non-interactive",
            default=False,
            action="store_true",
            dest='non_interactive',
            help="Use if you do not want a user interaction"
        )
        self.parser.add_argument(
            "--comparepkgs-only",
            default=False,
            dest="comparepkgs",
            help="Specify dir with old and new RPM packages. Dir structure has to be like <dir_name>/{old,new}/RPM"
        )
        self.parser.add_argument(
            "--builds-nowait",
            default=False,
            action="store_true",
            help="It starts koji or copr builds and does not care how they finish. "
                 "Useful for fedpkg and copr build tools."
        )
        # deprecated argument, kept for backward compatibility
        self.parser.add_argument(
            "--fedpkg-build-tasks",
            dest="fedpkg_build_tasks",
            help=argparse.SUPPRESS
        )
        self.parser.add_argument(
            "--build-tasks",
            dest="build_tasks",
            help="Specify comma-separated task ids, old task first."
        )
        self.parser.add_argument(
            "--results-dir",
            help="Specify results dir where you would like to stored rebase-helper stuff."
        )
        self.parser.add_argument(
            "--build-retries",
            default=2,
            help="Specify number of retries in case build fails.",
            type=int
        )
        self.parser.add_argument(
            "--builder-options",
            default=None,
            help="Enable arbitrary local builder option. The option MUST be in "
                 "--builder-options=\"--some-builder-option\" format. If you want to add more option stay with the "
                 "given format but divide builder options by whitespaces."
        )

    def __getattr__(self, name):
        try:
            return getattr(self.args, name)
        except AttributeError:
            return object.__getattribute__(self, name)


class CliHelper(object):

    @staticmethod
    def run():
        debug_log_file = None
        # be verbose until debug_log_file is created
        handler = LoggerHelper.add_stream_handler(logger, logging.DEBUG)
        try:
            cli = CLI()
            execution_dir, debug_log_file, report_log_file = Application.setup(cli)
            if not cli.verbose:
                handler.setLevel(logging.INFO)
            app = Application(cli, execution_dir, debug_log_file, report_log_file)
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
