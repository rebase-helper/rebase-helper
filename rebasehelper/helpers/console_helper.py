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

import datetime
import fcntl
import io
import os
import re
import sys
import tempfile
import termios
import tty

import colors  # type: ignore

from rebasehelper.constants import SYSTEM_ENCODING


class ConsoleHelper:

    """Class for interacting with the command line."""

    use_colors: bool = False

    @classmethod
    def should_use_colors(cls, conf):
        """Determines whether ANSI colors should be used for CLI output.

        Args:
            conf (rebasehelper.config.Config): Configuration object with arguments from the command line.

        Returns:
            bool: Whether colors should be used.

        """
        if os.environ.get('PY_COLORS') == '1':
            return True
        if os.environ.get('PY_COLORS') == '0':
            return False
        if conf.color == 'auto':
            if (not os.isatty(sys.stdout.fileno()) or
                    os.environ.get('TERM') == 'dumb'):
                return False
        elif conf.color == 'never':
            return False
        return True

    @classmethod
    def cprint(cls, message, fg=None, bg=None, style=None):
        """Prints colored output if possible.

        Args:
            message (str): String to be printed out.
            fg (str): Foreground color.
            bg (str): Background color.
            style (str): Style to be applied to the printed message.
                Possible styles: bold, faint, italic, underline, blink, blink2, negative, concealed, crossed.
                Some styles may not be supported by every terminal, e.g. 'blink'.
                Multiple styles should be connected with a '+', e.g. 'bold+italic'.

        """
        if cls.use_colors:
            try:
                print(colors.color(message, fg=fg, bg=bg, style=style))
            except ValueError:
                print(message)
        else:
            print(message)

    @staticmethod
    def parse_rgb_device_specification(specification):
        """Parses RGB device specification.

        Args:
            specification(str): RGB device specification.

        Returns:
            tuple: If the specification follows correct format, the first element is RGB tuple and the second is
            bit width of the RGB. Otherwise, both elements are None.

        """
        match = re.match(r'^rgb:([A-Fa-f0-9]{1,4})/([A-Fa-f0-9]{1,4})/([A-Fa-f0-9]{1,4})$', str(specification))
        if match:
            rgb = match.groups()
            bit_width = max(len(str(x)) for x in rgb) * 4
            return tuple(int(x, 16) for x in rgb), bit_width
        return None, None

    @staticmethod
    def color_is_light(rgb, bit_width):
        """Determines whether a color is light or dark.

        Args:
            rgb(tuple): RGB tuple.
            bit_width: Number of bits defining the RGB.

        Returns:
            bool: Whether a color is light or dark.

        """
        brightness = 1 - (0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]) / (1 << bit_width - 1)
        return brightness < 0.5

    @staticmethod
    def detect_background():
        """Detects terminal background color and decides whether it is light or dark.

        Returns:
            str: Whether to use dark or light color scheme.

        """
        background_color = ConsoleHelper.exchange_control_sequence('\x1b]11;?\x07')

        rgb_tuple, bit_width = ConsoleHelper.parse_rgb_device_specification(background_color)

        if rgb_tuple and ConsoleHelper.color_is_light(rgb_tuple, bit_width):
            return 'light'
        else:
            return 'dark'

    @staticmethod
    def exchange_control_sequence(query, timeout=0.05):
        """Captures a response of a control sequence from STDIN.

        Args:
            query (str): Control sequence.
            timeout (int, float): Time given to the terminal to react.

        Returns:
            str: Response of the terminal.

        """
        prefix, suffix = query.split('?', 1)
        attrs_obtained = False
        try:
            attrs = termios.tcgetattr(sys.stdin)
            attrs_obtained = True
            flags = fcntl.fcntl(sys.stdin.fileno(), fcntl.F_GETFL)

            # disable STDIN line buffering
            tty.setcbreak(sys.stdin.fileno(), termios.TCSANOW)
            # set STDIN to non-blocking mode
            fcntl.fcntl(sys.stdin.fileno(), fcntl.F_SETFL, flags | os.O_NONBLOCK)

            sys.stdout.write(query)
            sys.stdout.flush()

            # read the response
            buf = ''
            start = datetime.datetime.now()
            while (datetime.datetime.now() - start).total_seconds() < timeout:
                try:
                    buf += sys.stdin.read(1)
                except IOError:
                    continue
                if buf.endswith(suffix):
                    return buf.replace(prefix, '').replace(suffix, '')
            return None
        except termios.error:
            return None
        finally:
            # set terminal settings to the starting point
            if attrs_obtained:
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, attrs)
                fcntl.fcntl(sys.stdin.fileno(), fcntl.F_SETFL, flags)

    class Capturer:
        """ContextManager for capturing stdout/stderr"""

        def __init__(self, stdout=False, stderr=False):
            self.capture_stdout = stdout
            self.capture_stderr = stderr
            self.stdout = None
            self.stderr = None
            self._stdout_fileno = None
            self._stderr_fileno = None
            self._stdout_tmp = None
            self._stderr_tmp = None
            self._stdout_copy = None
            self._stderr_copy = None

        def __enter__(self):
            self._stdout_fileno = sys.__stdout__.fileno()  # pylint: disable=no-member
            self._stderr_fileno = sys.__stderr__.fileno()  # pylint: disable=no-member

            self._stdout_tmp = tempfile.TemporaryFile(mode='w+b') if self.capture_stdout else None
            self._stderr_tmp = tempfile.TemporaryFile(mode='w+b') if self.capture_stderr else None
            self._stdout_copy = os.fdopen(os.dup(self._stdout_fileno), 'wb') if self.capture_stdout else None
            self._stderr_copy = os.fdopen(os.dup(self._stderr_fileno), 'wb') if self.capture_stderr else None

            if self._stdout_tmp:
                sys.stdout.flush()
                os.dup2(self._stdout_tmp.fileno(), self._stdout_fileno)
            if self._stderr_tmp:
                sys.stderr.flush()
                os.dup2(self._stderr_tmp.fileno(), self._stderr_fileno)

            return self

        def __exit__(self, *args):
            if self._stdout_copy:
                sys.stdout.flush()
                os.dup2(self._stdout_copy.fileno(), self._stdout_fileno)
            if self._stderr_copy:
                sys.stderr.flush()
                os.dup2(self._stderr_copy.fileno(), self._stderr_fileno)

            if self._stdout_tmp:
                self._stdout_tmp.flush()
                self._stdout_tmp.seek(0, io.SEEK_SET)
                self.stdout = self._stdout_tmp.read().decode(SYSTEM_ENCODING)
            if self._stderr_tmp:
                self._stderr_tmp.flush()
                self._stderr_tmp.seek(0, io.SEEK_SET)
                self.stderr = self._stderr_tmp.read().decode(SYSTEM_ENCODING)

            if self._stdout_tmp:
                self._stdout_tmp.close()
            if self._stderr_tmp:
                self._stderr_tmp.close()
            if self._stdout_copy:
                self._stdout_copy.close()
            if self._stderr_copy:
                self._stderr_copy.close()
