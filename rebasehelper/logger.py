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
from rebasehelper.exceptions import RebaseHelperError


class LoggerHelper(object):

    @staticmethod
    def setup_logger(logger_name, level=logging.INFO):
        """
        Sets logger for rebase-helper
        :param logger_name: Logger name
        :param level: Initial level
        :return: logger for later on usage
        """
        logger_name = logging.getLogger(logger_name)
        console_handler = logging.StreamHandler()
        logger_name.setLevel(level)
        logger_name.addHandler(console_handler)

    @staticmethod
    def add_file_handler_to_logger(logger_name, log_file, formatter=True, level=logging.DEBUG):
        """
        Adds log_file to logger
        :param logger: To which logger handler is assigned
        :param log_file: log_file used for logging rebase-helper actions
        :return:
        """
        try:
            file_handler = logging.FileHandler(log_file, 'a')
            if formatter:
                log_formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
                file_handler.setFormatter(log_formatter)
            file_handler.setLevel(level)
            logger_name.addHandler(file_handler)
        except (IOError, OSError):
            raise RebaseHelperError('Adding log file {0} to logger failed.'.format(log_file))


LoggerHelper.setup_logger('rebase_helper')
logger = logging.getLogger('rebase_helper')
LoggerHelper.setup_logger('output_rebase_helper')
logger_output = logging.getLogger('output_rebase_helper')
