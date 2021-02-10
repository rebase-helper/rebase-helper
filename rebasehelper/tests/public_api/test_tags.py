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

import collections.abc

import pytest  # type: ignore

from rebasehelper.spec_content import SpecContent
from rebasehelper.tags import Tags, Tag


@pytest.mark.public_api
class TestTags:
    def test_contructor(self):
        spec = SpecContent('')
        tags = Tags(spec, spec)
        assert isinstance(tags, Tags)

    def test_filter(self, spec_object):
        result = spec_object.tags.filter()
        assert isinstance(result, collections.abc.Iterator)
        assert isinstance(next(result), Tag)
        result = spec_object.tags.filter(section_index=0, section_name='%package', name='Source*', valid=True)
        assert isinstance(result, collections.abc.Iterator)
        assert isinstance(next(result), Tag)
