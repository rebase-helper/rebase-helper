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

from rebasehelper.logger import logger


class TestLoggingHandler(logging.Handler):
    def __init__(self):
        logging.Handler.__init__(self)
        self.msgs = []

    def emit(self, record):
        self.msgs.append((record.levelname, record.getMessage()))

    @classmethod
    def create_fresh_handler(cls):
        tlh = cls()
        logger.addHandler(tlh)
        return tlh
