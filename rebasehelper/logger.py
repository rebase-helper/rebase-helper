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
import logging.handlers
import os
from typing import Dict, List, Optional, Tuple

from rebasehelper.helpers.console_helper import ConsoleHelper
from rebasehelper import constants


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
        super().__init__(name, level)

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


class MemoryHandler(logging.handlers.BufferingHandler):
    """BufferingHandler with infinite capacity"""

    buffer: List[logging.LogRecord]  # until this is added to typeshed: https://github.com/python/typeshed/pull/3402

    def __init__(self) -> None:
        super().__init__(0)

    def shouldFlush(self, record: logging.LogRecord) -> bool:
        return False

    def replay_into(self, target: logging.Handler) -> None:
        self.acquire()
        try:
            for record in self.buffer:
                if record.levelno >= target.level:
                    target.handle(record)
        finally:
            self.release()


class LoggerHelper:
    """Helper class for setting up a logger."""

    memory_handler: Optional[MemoryHandler] = None

    @classmethod
    def setup_memory_handler(cls) -> None:
        if cls.memory_handler:
            # only one memory handler is allowed
            return
        cls.memory_handler = MemoryHandler()
        logger = logging.getLogger('rebasehelper')
        logger.addHandler(cls.memory_handler)

    @classmethod
    def remove_memory_handler(cls) -> None:
        if cls.memory_handler:
            logger = logging.getLogger('rebasehelper')
            logger.removeHandler(cls.memory_handler)
        cls.memory_handler = None

    @staticmethod
    def add_stream_handler(logger: logging.Logger, level: Optional[int] = None,
                           formatter: Optional[logging.Formatter] = None) -> ColorizingStreamHandler:
        """Adds stream handler to the given logger.

        Args:
            logger: Logger object to add the handler to.
            level: Severity threshold.
            formatter: Formatter object used to format logged messages.

        Returns:
            Created stream handler instance.

        """
        console_handler = ColorizingStreamHandler()
        if level:
            console_handler.setLevel(level)
        if formatter:
            console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        return console_handler

    @staticmethod
    def add_file_handler(logger: logging.Logger, path: str, formatter: Optional[logging.Formatter] = None,
                         level: Optional[int] = None) -> Optional[logging.FileHandler]:
        """Adds file handler to the given logger.

        Args:
            logger: Logger object to add the handler to.
            path: Path to a log file.
            formatter: Formatter object used to format logged messages.
            level: Severity threshold.

        Returns:
            Created file handler instance or None if creation failed.

        """
        try:
            file_handler = logging.FileHandler(path, 'w')
            if level:
                file_handler.setLevel(level)
            if formatter:
                file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except (IOError, OSError):
            logger.warning('Can not create log in %s', path)
            return None
        else:
            return file_handler

    @classmethod
    def create_file_handlers(cls, results_dir: str) -> List[logging.FileHandler]:
        """Creates rebase-helper file handlers.

        Args:
            results_dir: Path to rebase-helper-results directory.

        Returns:
            List of created file handler instances.

        """
        logs_dir = os.path.join(results_dir, constants.LOGS_DIR)
        # the logs directory can already exist
        os.makedirs(logs_dir, exist_ok=True)
        logger = logging.getLogger('rebasehelper')

        # first remove any existing file handlers
        logger.handlers = [h for h in logger.handlers if not isinstance(h, logging.FileHandler)]

        log_formatter = logging.Formatter('%(message)s')
        debug_log_formatter = logging.Formatter('%(asctime)s %(filename)s:%(lineno)s %(funcName)s: %(message)s')

        debug_log = os.path.join(logs_dir, constants.DEBUG_LOG)
        debug = cls.add_file_handler(logger, debug_log, debug_log_formatter, logging.DEBUG)
        verbose_log = os.path.join(logs_dir, constants.VERBOSE_LOG)
        verbose = cls.add_file_handler(logger, verbose_log, log_formatter, CustomLogger.VERBOSE)
        info_log = os.path.join(logs_dir, constants.INFO_LOG)
        info = cls.add_file_handler(logger, info_log, log_formatter, logging.INFO)

        if cls.memory_handler:
            # initialize the log files with what has been recorded in memory until now
            for handler in (debug, verbose, info):
                if handler:
                    cls.memory_handler.replay_into(handler)
            cls.remove_memory_handler()

        return [h for h in (debug, verbose, info) if h]

    @classmethod
    def create_stream_handlers(cls) -> Tuple[ColorizingStreamHandler, ColorizingStreamHandler]:
        logger = logging.getLogger('rebasehelper')
        formatter = logging.Formatter('%(levelname)s: %(message)s')
        main = cls.add_stream_handler(logger, logging.INFO, formatter)

        logger_summary = logging.getLogger('rebasehelper.summary')
        logger_summary.propagate = False
        summary = cls.add_stream_handler(logger_summary)

        logger_report = logging.getLogger('rebasehelper.report')
        logger_report.propagate = False
        return main, summary

    @classmethod
    def remove_file_handlers(cls, handlers: List[logging.FileHandler]) -> None:
        """Removes rebase-helper file handlers.

        Args:
            handlers: List of file handlers to remove.

        """
        logger = logging.getLogger('rebasehelper')
        for handler in handlers:
            logger.removeHandler(handler)
