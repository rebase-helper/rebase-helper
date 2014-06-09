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
            "--patches",
            default=False,
            action="store_true",
            help="Select a patch tool [patch|git]"
        )
        self.parser.add_argument(
            "-b",
            "--build",
            default="mock",
            help="Only build package. It can be done by mock or rpmbuild."
        )
        self.parser.add_argument(
            "--difftool",
            default="meld",
            help="Tool for comparing two sources."
        )
        self.parser.add_argument(
            "sources",
            metavar='SOURCES',
            help="Specify new upstream sources"
        )
        self.parser.add_argument(
            "--patches-only",
            default=False,
            action="store_true",
            help="Apply only patches"
        )
        self.parser.add_argument(
            "--build-only",
            default=False,
            action="store_true",
            help="Apply only patches"
        )

    def __getattr__(self, name):
        try:
            return getattr(self.args, name)
        except AttributeError:
            return object.__getattribute__(self, name)

if __name__ == '__main__':
    x = CLI()
