# -*- coding: utf-8 -*-

import argparse
import os
import sys

from rebasehelper.constants import *


class CLI(object):
    """ Class for processing data from commandline """

    def __init__(self):
        """ parse arguments """
        self.parser = argparse.ArgumentParser(description=PROGRAM_DESCRIPTION)

        #self.parser.usage = "%%prog [-v] <content_file>"

        self.add_args()
        self.args = self.parser.parse_args()

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
            "--source",
            help="Tarball or zip source package"
        )

    def __getattr__(self, name):
        try:
            return getattr(self.args, name)
        except AttributeError:
            return object.__getattribute__(self, name)

if __name__ == '__main__':
    x = CLI()
