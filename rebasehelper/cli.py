# -*- coding: utf-8 -*-

import argparse
import sys
import logging

from rebasehelper.constants import *
from rebasehelper.logger import logger


class CLI(object):
    """ Class for processing data from commandline """

    def __init__(self):
        """ parse arguments """
        self.parser = argparse.ArgumentParser(description=PROGRAM_DESCRIPTION)

        #self.parser.usage = "%%prog [-v] <sources>"

        self.add_args()
        self.args = self.parser.parse_args()
        logger.info(self.args)

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
            "--patchtool",
            default='patch',
            help="Select the patch tool [patch|git]"
        )
        self.parser.add_argument(
            "--buildtool",
            default="mock",
            help="Select the build tool [mock|rpmbuild]"
        )
        self.parser.add_argument(
            "--difftool",
            default="meld",
            help="Select the tool for comparing two sources [meld]"
        )
        self.parser.add_argument(
            "sources",
            metavar='SOURCES',
            help="Specify new upstream sources"
        )

    def __getattr__(self, name):
        try:
            return getattr(self.args, name)
        except AttributeError:
            return object.__getattribute__(self, name)

if __name__ == '__main__':
    x = CLI()
