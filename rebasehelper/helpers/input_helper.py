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
from typing import cast

from rebasehelper.logger import CustomLogger


logger: CustomLogger = cast(CustomLogger, logging.getLogger(__name__))


class InputHelper:

    """Class for command line interaction with the user."""

    @staticmethod
    def strtobool(message):
        """Converts a user message to a corresponding truth value.

        This method is a replacement for deprecated strtobool from distutils,
        its behaviour remains the same.

        Args:
            message (str): Message to evaluate.

        Returns:
            bool: True on 'y', 'yes', 't', 'true', 'on' and '1'.
                  False on 'n', 'no', 'f', 'false', 'off' and '0'.

        Raises:
            ValueError: On any other value.
        """
        message = message.lower()
        if message in ('y', 'yes', 't', 'true', 'on', '1'):
            return True
        elif message in ('n', 'no', 'f', 'false', 'off', '0'):
            return False
        raise ValueError('No conversion to truth value for "{}"'.format(message))

    @classmethod
    def get_message(cls, message, default_yes=True, any_input=False):
        """Prompts a user with yes/no message and gets the response.

        Args:
            message (str): Prompt string.
            default_yes (bool): If the default value should be YES.
            any_input (bool): Whether to return default value regardless of input.

        Returns:
            bool: True or False, based on user's input.

        """
        if default_yes:
            choice = '[Y/n]'
        else:
            choice = '[y/N]'

        if any_input:
            msg = '{0} '.format(message)
        else:
            msg = '{0} {1}? '.format(message, choice)

        while True:
            user_input = input(msg).lower()

            if not user_input or any_input:
                return True if default_yes else False

            try:
                user_input = cls.strtobool(user_input)
            except ValueError:
                logger.error('You have to type y(es) or n(o).')
                continue

            if any_input:
                return True
            else:
                return bool(user_input)
