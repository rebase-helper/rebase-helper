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

import os
import sys

import pytest  # type: ignore

from rebasehelper.helpers.console_helper import ConsoleHelper


class TestConsoleHelper:

    def test_capture_output(self):
        def write():
            with os.fdopen(sys.__stdout__.fileno(), 'w') as f:  # pylint: disable=no-member
                f.write('test stdout')
            with os.fdopen(sys.__stderr__.fileno(), 'w') as f:  # pylint: disable=no-member
                f.write('test stderr')

        with ConsoleHelper.Capturer(stdout=True, stderr=True) as capturer:
            write()

        assert capturer.stdout == 'test stdout'
        assert capturer.stderr == 'test stderr'

    @pytest.mark.parametrize('specification, expected_rgb, expected_bit_width', [
        ('rgb:0000/0000/0000', (0x0, 0x0, 0x0), 16),
        ('rgb:ffff/ffff/ffff', (0xffff, 0xffff, 0xffff), 16),
        ('rgb:f/f/f', (0xf, 0xf, 0xf), 4),
        ('rgb:', None, None)
    ], ids=[
        '16-bit-black',
        '16-bit-white',
        '4-bit-white',
        'invalid-format',
    ])
    def test_parse_rgb_device_specification(self, specification, expected_rgb, expected_bit_width):
        rgb, bit_width = ConsoleHelper.parse_rgb_device_specification(specification)
        assert rgb == expected_rgb
        assert bit_width == expected_bit_width

    @pytest.mark.parametrize('rgb_tuple, bit_width, expected_result', [
        ((0xf, 0xf, 0xf), 4, True),
        ((0x0, 0x0, 0x0), 4, False),
        ((0x2929, 0x2929, 0x2929), 16, False),
    ], ids=[
        'white',
        'black',
        'grey',
    ])
    def test_color_is_light(self, rgb_tuple, bit_width, expected_result):
        assert ConsoleHelper.color_is_light(rgb_tuple, bit_width) == expected_result
