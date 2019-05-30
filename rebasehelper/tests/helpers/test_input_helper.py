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

import io

import pytest  # type: ignore

from rebasehelper.helpers.input_helper import InputHelper


class TestInputHelper:

    @pytest.mark.parametrize('suffix, answer, kwargs, expected_input', [
        (' [Y/n]? ', 'yes', None, True),
        (' [Y/n]? ', 'no', None, False),
        (' [y/N]? ', 'yes', dict(default_yes=False), True),
        (' [Y/n]? ', '\n', None, True),
        (' [y/N]? ', '\n', dict(default_yes=False), False),
        (' ', 'random input\ndsfdf', dict(any_input=True), True),
        (' ', 'random input\n', dict(default_yes=False, any_input=True), False),
    ], ids=[
        'yes',
        'no',
        'yes-default_no',
        'no_input-default_yes',
        'no_input-default_no',
        'any_input-default_yes',
        'any_input-default_no',
    ])
    def test_get_message(self, monkeypatch, capsys, suffix, answer, kwargs, expected_input):
        question = 'bla bla'
        monkeypatch.setattr('sys.stdin', io.StringIO(answer))
        inp = InputHelper.get_message(question, **(kwargs or {}))
        assert capsys.readouterr()[0] == question + suffix
        assert inp is expected_input
