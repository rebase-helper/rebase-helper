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
import sys

import six

from rebasehelper.constants import PROGRAM_DESCRIPTION
from rebasehelper.application import Application
from rebasehelper.logger import logger
from rebasehelper.exceptions import RebaseHelperError


class CLI(object):
    """ Class for processing data from commandline """

    def __init__(self, args=None):
        """parse arguments"""
        self.parser = argparse.ArgumentParser(description=PROGRAM_DESCRIPTION)
        self.add_args()
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
            help="Select the build tool [mock(default)|rpmbuild|fedpkg]"
        )
        self.parser.add_argument(
            "--pkgcomparetool",
            default=False,
            help="Select the tool for comparing two packages [pkgdiff, rpmdiff, abipkgdiff]"
        )
        self.parser.add_argument(
            "--outputtool",
            default="text",
            help="Select the tool for showing information from rebase-helper process [text]"
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
            help="It starts a koji builds and does not care how they finish. Useful for fedpkg build tool."
        )
        # deprecated argument, kept for backward compatibility
        self.parser.add_argument(
            "--fedpkg-build-tasks",
            dest="build_tasks",
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

    def __getattr__(self, name):
        try:
            return getattr(self.args, name)
        except AttributeError:
            return object.__getattribute__(self, name)


class CliHelper(object):

    @staticmethod
    def run():
        try:
            cli = CLI(sys.argv[1:])
            app = Application(cli)
            app.run()
        except KeyboardInterrupt:
            logger.info('\nInterrupted by user')
        except RebaseHelperError as e:
            logger.error('\n%s', six.text_type(e))
            sys.exit(1)

        sys.exit(0)

if __name__ == '__main__':
    x = CLI()
