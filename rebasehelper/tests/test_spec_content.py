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

import pytest  # type: ignore

from rebasehelper.spec_content import SpecContent
from rebasehelper.tests.conftest import SPEC_FILE


class TestSpecContent:
    TEST_FILES = [
        SPEC_FILE
    ]

    @pytest.fixture
    def spec_content(self):
        with open(SPEC_FILE, 'r') as infile:
            return SpecContent(infile.read())

    def test_string_representation(self, spec_content):
        with open(SPEC_FILE, 'r') as infile:
            assert str(spec_content) == infile.read()

    @pytest.mark.parametrize('line, section, expected', [
        ('#test comment', '%package', (0, 13)),
        ('make install', '%install', (12, 12)),
        ('make install # install', '%install', (12, 22)),
        ('Name: test #invalid comment', '%package', (27, 27)),
    ], ids=[
        'whole_line',
        'no_comment',
        'inline_allowed',
        'inline_prohibited',
    ])
    def test_get_comment_span(self, line, section, expected):
        assert SpecContent.get_comment_span(line, section) == expected

    @pytest.mark.parametrize('section, expected', [
        ('%install', ['make DESTDIR=$RPM_BUILD_ROOT install', '']),
        ('%package test', None),

    ], ids=[
        'existent',
        'nonexistent',
    ])
    def test_section(self, spec_content, section, expected):
        assert spec_content.section(section) == expected

    def test_replace_section(self, spec_content):
        spec_content.replace_section('%install', ['#removed'])
        assert spec_content.section('%install') == ['#removed']
