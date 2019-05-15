# -*- coding: utf-8 -*-
#
# This tool helps you rebase your package to the latest version
# Copyright (C) 2013-2019 Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
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
#
# Authors: Petr Hráček <phracek@redhat.com>
#          Tomáš Hozza <thozza@redhat.com>
#          Nikola Forró <nforro@redhat.com>
#          František Nečas <fifinecas@seznam.cz>

import logging

from typing import Dict, Optional

from rebasehelper.helpers.console_helper import ConsoleHelper


class CustomLogger(logging.Logger):

    TRACE: int = logging.DEBUG + 1
    VERBOSE: int = logging.DEBUG + 2
    SUCCESS: int = logging.INFO + 5
    HEADING: int = logging.INFO + 6
    IMPORTANT: int = logging.INFO + 7

    _nameToLevel: Dict[str, int] = {
        'TRACE': TRACE,
        'VERBOSE': VERBOSE,
        'SUCCESS': SUCCESS,
        'HEADING': HEADING,
        'IMPORTANT': IMPORTANT,
    }

    def __init__(self, name, level=logging.NOTSET):
        super(CustomLogger, self).__init__(name, level)

        for lev, severity in self._nameToLevel.items():
            logging.addLevelName(severity, lev)

    def __getattr__(self, level):
        severity = self._nameToLevel.get(level.upper())

        def log(message, *args, **kwargs):
            if self.isEnabledFor(severity):
                self._log(severity, message, args, **kwargs)

        if severity:
            return log

        raise AttributeError


class LoggerHelper:
    """
    Helper class for setting up a logger
    """

    @staticmethod
    def get_basic_logger(logger_name, level=logging.DEBUG):
        """Sets up a basic logger without any handler.

        Args:
            logger_name (str): Logger name.
            level (int): Severity threshold.

        Returns:
            logging.Logger: Created logger instance.

        """
        basic_logger = logging.getLogger(logger_name)
        basic_logger.setLevel(level)
        return basic_logger

    @staticmethod
    def add_stream_handler(logger_object, level=None, formatter_object=None):
        """Adds stream handler to the given logger.

        Args:
            logger_object (logging.Logger): Logger object to add the handler to.
            level (int): Severity threshold.
            formatter_object (logging.Formatter): Formatter object used to format logged messages.

        Returns:
            logging.StreamHandler: Created stream handler instance.

        """
        console_handler = ColorizingStreamHandler()
        if level:
            console_handler.setLevel(level)
        if formatter_object:
            console_handler.setFormatter(formatter_object)
        logger_object.addHandler(console_handler)
        return console_handler

    @staticmethod
    def add_file_handler(logger_object, path, formatter_object=None, level=None):
        """Adds file handler to the given logger.

        Args:
            logger_object (logging.Logger): Logger object to add the handler to.
            path (str): Path to a log file.
            formatter_object (logging.Formatter): Formatter object used to format logged messages.
            level (int): Severity threshold.

        Returns:
            logging.FileHandler: Created file handler instance.

        """
        try:
            file_handler = logging.FileHandler(path, 'w')
            if level:
                file_handler.setLevel(level)
            if formatter_object:
                file_handler.setFormatter(formatter_object)
            logger_object.addHandler(file_handler)
            return file_handler
        except (IOError, OSError):
            logger_object.warning('Can not create log in %s', path)


class ColorizingStreamHandler(logging.StreamHandler):
    colors: Dict[str, Dict[int, Dict[str, Optional[str]]]] = {
        'dark': {
            logging.DEBUG: {'fg': 'brightblack', 'bg': 'default', 'style': None},
            CustomLogger.TRACE: {'fg': 'red', 'bg': 'default', 'style': None},
            CustomLogger.VERBOSE: {'fg': 'brightblack', 'bg': 'default', 'style': None},
            logging.INFO: {'fg': 'default', 'bg': 'default', 'style': None},
            CustomLogger.SUCCESS: {'fg': 'green', 'bg': 'default', 'style': None},
            CustomLogger.HEADING: {'fg': 'yellow', 'bg': 'default', 'style': None},
            CustomLogger.IMPORTANT: {'fg': 'red', 'bg': 'default', 'style': None},
            logging.WARNING: {'fg': 'yellow', 'bg': 'default', 'style': None},
            logging.ERROR: {'fg': 'red', 'bg': 'default', 'style': 'bold'},
            logging.CRITICAL: {'fg': 'white', 'bg': 'red', 'style': 'bold'},
        },
        'light': {
            logging.DEBUG: {'fg': 'brightblack', 'bg': 'default', 'style': None},
            CustomLogger.TRACE: {'fg': 'red', 'bg': 'default', 'style': None},
            CustomLogger.VERBOSE: {'fg': 'brightblack', 'bg': 'default', 'style': None},
            logging.INFO: {'fg': 'default', 'bg': 'default', 'style': None},
            CustomLogger.SUCCESS: {'fg': 'green', 'bg': 'default', 'style': None},
            CustomLogger.HEADING: {'fg': 'blue', 'bg': 'default', 'style': None},
            CustomLogger.IMPORTANT: {'fg': 'red', 'bg': 'default', 'style': None},
            logging.WARNING: {'fg': 'blue', 'bg': 'default', 'style': None},
            logging.ERROR: {'fg': 'red', 'bg': 'default', 'style': 'bold'},
            logging.CRITICAL: {'fg': 'white', 'bg': 'red', 'style': 'bold'},
        },
    }

    terminal_background: str = 'dark'

    def set_terminal_background(self, background):
        if background == 'auto':
            self.terminal_background = ConsoleHelper.detect_background()
        else:
            self.terminal_background = background

    def emit(self, record):
        try:
            message = self.format(record)
            level_settings = self.colors[self.terminal_background].get(record.levelno, {})
            ConsoleHelper.cprint(message, **level_settings)
            self.flush()
        except Exception:  # pylint: disable=broad-except
            self.handleError(record)


logging.setLoggerClass(CustomLogger)
#  the main rebase-helper logger
logger: CustomLogger = LoggerHelper.get_basic_logger('rebase-helper')
#  logger for output tool
logger_output: CustomLogger = LoggerHelper.get_basic_logger('output-tool', logging.INFO)
logger_report: CustomLogger = LoggerHelper.get_basic_logger('rebase-helper-report', logging.INFO)
logger_traceback: CustomLogger = LoggerHelper.get_basic_logger('traceback', CustomLogger.TRACE)
logger_upstream: CustomLogger = LoggerHelper.get_basic_logger('rebase-helper-upstream')

console_formatter: logging.Formatter = logging.Formatter("%(levelname)s: %(message)s")
log_formatter: logging.Formatter = logging.Formatter("%(message)s")
debug_log_formatter: logging.Formatter = logging.Formatter(
    "%(asctime)s %(filename)s:%(lineno)s %(funcName)s: %(message)s")

main_handler: ColorizingStreamHandler = LoggerHelper.add_stream_handler(logger, logging.INFO, console_formatter)
output_tool_handler: ColorizingStreamHandler = LoggerHelper.add_stream_handler(logger_output)
