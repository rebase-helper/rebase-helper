# -*- coding: utf-8 -*-

import argparse
import sys
import logging

from rebasehelper.constants import *
from rebasehelper import logger


class CLI(object):
    """ Class for processing data from commandline """

    def __init__(self):
        """ parse arguments """
        self.parser = argparse.ArgumentParser(description=PROGRAM_DESCRIPTION)

        #self.parser.usage = "%%prog [-v] <content_file>"

        self.register_console_logging_handler(logger.logger)
        self.add_args()
        self.args = self.parser.parse_args()

    def register_console_logging_handler(cls, logger):
        """Registers console logging handler to given logger."""
        console_handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter("%(asctime)s - %(name)s - %(message)s")
        console_handler.setFormatter(formatter)
        console_handler.setLevel(logging.INFO)
        logger.addHandler(console_handler)

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
        self.parser.add_argument(
            "--specfile",
            help="Specify spec file for testing"
        )

    def __getattr__(self, name):
        try:
            return getattr(self.args, name)
        except AttributeError:
            return object.__getattribute__(self, name)

if __name__ == '__main__':
    x = CLI()
