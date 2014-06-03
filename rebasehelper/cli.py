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

        #self.parser.usage = "%%prog [-v] <content_file>"

        self.add_args()
        self.args = self.parser.parse_args()
        print self.args

    def add_args(self):
        self.parser.add_argument(
            "-d",
            "--devel",
            default="False",
            action="store_true",
            help="Check only header files and soname bump"
        )
        self.parser.add_argument(
            "-v",
            "--verbose",
            default=False,
            action="store_true",
            help="Output is more verbose (recommended)"
        )
        self.parser.add_argument(
            "-s",
            "--sources",
            help="Tarball or zip source package"
        )
        self.parser.add_argument(
            "--specfile",
            help="Specify spec file for testing"
        )
        self.parser.add_argument(
            "-p",
            "--patches",
            default=False,
            action="store_true",
            help="Apply only patches"
        )
        self.parser.add_argument(
            "-b",
            "--build",
            default="rpmbuild",
            help="Only build package. It can be done by mock or rpmbuild."
        )
        self.parser.add_argument(
            "--difftool",
            default="vimdiff",
            help="Tool for comparing two sources."
        )

    def __getattr__(self, name):
        try:
            return getattr(self.args, name)
        except AttributeError:
            return object.__getattribute__(self, name)

if __name__ == '__main__':
    x = CLI()
