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


@pytest.mark.public_api
class TestSpecContent:
    def test_section(self, spec_object):
        assert isinstance(spec_object.spec_content.section('%install'), list)
        assert spec_object.spec_content.section(name='%nonexistent') is None

    def test_sections(self, spec_object):
        assert isinstance(spec_object.spec_content.sections, list)
        for section in spec_object.spec_content.sections:
            assert isinstance(section, tuple)
            assert isinstance(section[1], list)

    def test_replace_section(self, spec_object):
        section = '%install'
        replacement = ['test', '']
        assert spec_object.spec_content.replace_section(section, replacement) is True
        assert spec_object.spec_content.replace_section(name=section, content=replacement) is True
        assert spec_object.spec_content.replace_section(name='%notasection', content=[]) is False
