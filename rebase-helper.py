#!/usr/bin/python -tt
# -*- coding: utf-8 -*-

# This tool helps you to rebase package to the latest version
# Copyright (C) 2013 Petr Hracek
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

import sys
from rebasehelper.cli import CLI
from rebasehelper.application import Application
from rebasehelper.logger import logger

def main(args=None):
    try:
        cli = CLI(args)
        app = Application(cli)
        app.run()
    except KeyboardInterrupt:
        logger.info('\nExiting due to Keyboard Interrupt')
    except Exception as e:
        # TODO: maybe we should catch only specific exception to find unknown bugs
        logger.error('\n{0}'.format(e.message))
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
