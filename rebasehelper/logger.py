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
import os


class LoggerHelper(object):
    """
    Helper class for setting up a logger
    """

    @staticmethod
    def get_basic_logger(logger_name, level=logging.DEBUG):
        """
        Sets-up a basic logger without any handler

        :param logger_name: Logger name
        :param level: severity level
        :return: created logger
        """
        logger = logging.getLogger(logger_name)
        console_handler = logging.StreamHandler()
        logger.setLevel(level)
        logger.addHandler(console_handler)
        return logger

    @staticmethod
    def add_stream_handler(logger, level=logging.DEBUG):
        """
        Adds console handler with given severity.

        :param logger: logger object to add the handler to
        :param level: severity level
        :return: None
        """
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        logger.addHandler(console_handler)

    @staticmethod
    def add_file_handler(logger, path, formatter=None, level=logging.DEBUG):
        """
        Adds FileHandler to a given logger

        :param logger: Logger object to which the file handler will be added
        :param path: Path to file where the debug log will be written
        :return: None
        """
        file_handler = logging.FileHandler(path, 'w')
        if formatter:
            file_handler.setFormatter(formatter)
        file_handler.setLevel(level)
        logger.addHandler(file_handler)


#  the main Rebase-Helper logger
logger = LoggerHelper.get_basic_logger('rebase-helper')
LoggerHelper.add_stream_handler(logger, logging.INFO)
#  logger for output tool
logger_output = LoggerHelper.get_basic_logger('rebase-helper.output')
LoggerHelper.add_stream_handler(logger_output, logging.INFO)
