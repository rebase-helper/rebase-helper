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

import logging
import settings
import os

logger = logging.getLogger('rebase_helper')
consoleHandler = logging.StreamHandler()
logger.setLevel(logging.INFO)
logger.addHandler(consoleHandler)


def add_log_file_handler(log_file):
    log_formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    try:
        file_handler = logging.FileHandler(log_file, 'a')
        file_handler.setFormatter(log_formatter)
        file_handler.setLevel(logging.DEBUG)
        logger.addHandler(file_handler)
    except (IOError, OSError):
        return False
    return True
