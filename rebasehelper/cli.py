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

import argparse
import logging
import os
import re
import sys
from typing import cast, Dict, List

from rebasehelper import VERSION
from rebasehelper.options import OPTIONS, traverse_options
from rebasehelper.constants import PROGRAM_DESCRIPTION, NEW_ISSUE_LINK, LOGS_DIR, TRACEBACK_LOG, DEBUG_LOG
from rebasehelper.application import Application
from rebasehelper.logger import CustomLogger, LoggerHelper
from rebasehelper.exceptions import RebaseHelperError
from rebasehelper.helpers.console_helper import ConsoleHelper
from rebasehelper.helpers.bugzilla_helper import BugzillaHelper
from rebasehelper.config import Config
from rebasehelper.argument_parser import CustomArgumentParser, CustomHelpFormatter, CustomAction
from rebasehelper.plugins.plugin_manager import plugin_manager


logger: CustomLogger = cast(CustomLogger, logging.getLogger(__name__))


class CLI:
    """ Class for processing data from commandline """

    @staticmethod
    def build_parser(available_choices_only=False):
        parser = CustomArgumentParser(description=PROGRAM_DESCRIPTION,
                                      formatter_class=CustomHelpFormatter)

        group = None
        current_group = 0
        for option in traverse_options(OPTIONS + plugin_manager.get_options()):
            available_choices = option.pop("available_choices", option.get("choices"))
            if available_choices_only:
                option["choices"] = available_choices

            option_kwargs = dict(option)
            for key in ("group", "default", "name"):
                if key in option_kwargs:
                    del option_kwargs[key]

            if "group" in option:
                if not group or current_group != option["group"]:
                    current_group = option["group"]
                    group = parser.add_mutually_exclusive_group()
                actions_container = group
            else:
                actions_container = parser

            # default is set to SUPPRESS to prevent arguments which were not specified on command line from being
            # added to namespace. This allows rebase-helper to determine which arguments are used with their
            # default value. This is later used for merging CLI arguments with config.
            actions_container.add_argument(*option["name"], action=CustomAction, default=argparse.SUPPRESS,
                                           actual_default=option.get("default"), **option_kwargs)

        return parser

    def __init__(self, args=None):
        """parse arguments"""
        if args is None:
            args = sys.argv[1:]
        # sanitize builder options to prevent ArgumentParser from processing them
        for opt in ['--builder-options', '--srpm-builder-options']:
            try:
                i = args.index(opt)
                args[i:i+2] = ['='.join(args[i:i+2])]
            except ValueError:
                continue
        self.parser = CLI.build_parser(available_choices_only=True)
        self.args = self.parser.parse_args(args)

    def __getattr__(self, name):
        try:
            return getattr(self.args, name)
        except AttributeError:
            return object.__getattribute__(self, name)


class CliHelper:

    @classmethod
    def convert_macros_to_dict(cls, macros_list: List[str]) -> Dict[str, str]:
        """Converts macros from CLI to a dictionary.

        Args:
            macros_list: List of macros in the format 'MACRO EXPRESSION'.

        Returns:
            The converted macros, MACRO are keys, EXPRESSION are values.

        Raises:
            RebaseHelperError if the macros don't follow the correct format.

        """
        macros = {}
        for macro in macros_list:
            match = re.match(r"\s*%?(?P<macro>\S+)\s+(?P<expr>\S.*)\s*", macro)
            if not match:
                raise RebaseHelperError('Wrong macro format used ({}). Use \'MACRO EXPR\' instead'.format(macro))

            macros[match.group('macro')] = match.group('expr')

        return macros

    @classmethod
    def run(cls):
        results_dir = None
        start_dir = os.getcwd()
        try:
            LoggerHelper.setup_memory_handler()
            main_handler, output_tool_handler = LoggerHelper.create_stream_handlers()
            cli = CLI()
            if hasattr(cli, 'version'):
                print(VERSION)
                sys.exit(0)

            logger.info('rebase-helper version %s', VERSION)

            config = Config(getattr(cli, 'config-file', None))
            config.merge(cli)
            for handler in [main_handler, output_tool_handler]:
                handler.set_terminal_background(config.background)
            if config.verbose == 0:
                main_handler.setLevel(logging.INFO)
            elif config.verbose == 1:
                main_handler.setLevel(CustomLogger.VERBOSE)
            else:
                main_handler.setLevel(logging.DEBUG)
            ConsoleHelper.use_colors = ConsoleHelper.should_use_colors(config)
            if config.bugzilla_id:
                repo_path, config.config['sources'] = BugzillaHelper.prepare_rebase_repository(config.bugzilla_id)
                try:
                    os.chdir(repo_path)
                except OSError as e:
                    raise RebaseHelperError('Could not change directory to the cloned repository') from e
                # update relative paths in config
                for option in ('results_dir', 'workspace_dir'):
                    path = getattr(config, option)
                    if path and not os.path.isabs(path):
                        config.config[option] = os.path.join(os.path.relpath(start_dir, os.getcwd()), path)

            if config.config['rpmmacros']:
                macros = ' -D ' + ' -D '.join('"{}"'.format(s) for s in config.config['rpmmacros'])
                for option in ('builder_options', 'srpm_builder_options'):
                    if config.config[option]:
                        config.config[option] += macros
                    else:
                        config.config[option] = macros

            config.config['rpmmacros'] = cls.convert_macros_to_dict(config.rpmmacros)
            execution_dir, results_dir = Application.setup(config)
            app = Application(config, start_dir, execution_dir, results_dir)
            app.run()
        except KeyboardInterrupt:
            logger.info('Interrupted by user')
        except RebaseHelperError as e:
            if e.msg:
                logger.error('%s', e.msg)
            else:
                logger.error('%s', str(e))
            sys.exit(1)
        except SystemExit as e:
            sys.exit(e.code)
        except BaseException:
            logger_traceback: CustomLogger = cast(CustomLogger, logging.getLogger('rebasehelper.traceback'))
            logger_traceback.propagate = False
            logger_traceback.setLevel(CustomLogger.TRACE)
            if results_dir:
                debug_log = os.path.join(results_dir, LOGS_DIR, DEBUG_LOG)
                traceback_log = os.path.join(results_dir, LOGS_DIR, TRACEBACK_LOG)
                logger.error('rebase-helper failed due to an unexpected error. Please report this problem'
                             '\nusing the following link: %s'
                             '\nand include the content of'
                             '\n\'%s\' and'
                             '\n\'%s\''
                             '\nin the report.'
                             '\nThank you!',
                             NEW_ISSUE_LINK, debug_log, traceback_log)
                LoggerHelper.add_file_handler(logger_traceback, traceback_log)
            else:
                logger.error('rebase-helper failed due to an unexpected error. Please report this problem'
                             '\nusing the following link: %s'
                             '\nand include the following traceback in the report.'
                             '\nThank you!',
                             NEW_ISSUE_LINK)

                LoggerHelper.add_stream_handler(logger_traceback, CustomLogger.TRACE)
            logger_traceback.trace('', exc_info=1)
            sys.exit(1)

        sys.exit(0)


if __name__ == '__main__':
    x = CLI()
