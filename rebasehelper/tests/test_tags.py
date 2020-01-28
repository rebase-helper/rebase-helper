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
import rpm  # type: ignore

from rebasehelper.tags import Tag, Tags
from rebasehelper.spec_content import SpecContent


class TestTags:

    RAW_CONTENT = '''
Name: test
Version: 0.1
Source: test.tar.xz
SOURCE1: additional-files.zip
Patch00: patch0000.diff
Patch:   patch0001.diff
Patch:   patch0002.diff
Patch03: patch0003.diff
%{?!optimize:Patch999: extras.patch}
%{?optimize:Patch999: extras-optimized.patch}

%sourcelist
   # test comment
source2.zip

%patchlist
list.patch

%Package libs
Requires: %{name}-%{version}
Requires: extradep
Source: source3.tar.gz

%sourcelist
source4.zip

%if 0%{?with_utils:1}
%package utils
Requires: %{name}-%{version}
%endif
    '''

    PARSED_CONTENT = '''
Name: test
Version: 0.1
Source: test.tar.xz
SOURCE1: additional-files.zip
Patch00: patch0000.diff
Patch:   patch0001.diff
Patch:   patch0002.diff
Patch03: patch0003.diff

Patch999: extras-optimized.patch

%sourcelist
   # test comment
source2.zip

%patchlist
list.patch

%Package libs
Requires: test-0.1
Requires: extradep
Source: source3.tar.gz

%sourcelist
source4.zip

    '''

    MACROS = [
        ('name', 'test'),
        ('version', '0.1'),
        ('optimize', '1'),
    ]

    @pytest.fixture
    def tags(self):
        rpm.reloadConfig()
        for macro in self.MACROS:
            rpm.addMacro(*macro)
        return Tags(SpecContent(self.RAW_CONTENT), SpecContent(self.PARSED_CONTENT))

    def test_tags(self, tags):
        assert len(tags) == 16
        assert tags[0] == Tag(0, '%package', 1, 'Name', (6, 10), True)
        assert tags[1] == Tag(0, '%package', 2, 'Version', (9, 12), True)
        assert tags[2] == Tag(0, '%package', 3, 'Source0', (8, 19), True, 0)
        assert tags[3] == Tag(0, '%package', 4, 'Source1', (9, 29), True, 1)
        assert tags[4] == Tag(0, '%package', 5, 'Patch0', (9, 23), True, 0)
        assert tags[5] == Tag(0, '%package', 6, 'Patch1', (9, 23), True, 1)
        assert tags[6] == Tag(0, '%package', 7, 'Patch2', (9, 23), True, 2)
        assert tags[7] == Tag(0, '%package', 8, 'Patch3', (9, 23), True, 3)
        assert tags[8] == Tag(0, '%package', 10, 'Patch999', (22, 44), True, 999)
        assert tags[9] == Tag(1, '%sourcelist', 1, 'Source2', (0, 11), True, 2)
        assert tags[10] == Tag(2, '%patchlist', 0, 'Patch1000', (0, 10), True, 1000)
        assert tags[11] == Tag(3, '%package libs', 0, 'Requires', (10, 28), True)
        assert tags[12] == Tag(3, '%package libs', 1, 'Requires', (10, 18), True)
        assert tags[13] == Tag(3, '%package libs', 2, 'Source3', (8, 22), True, 3)
        assert tags[14] == Tag(4, '%sourcelist', 0, 'Source4', (0, 11), True, 4)
        assert tags[15] == Tag(5, '%package utils', 0, 'Requires', (10, 28), False)

    def test_filter(self, tags):
        assert len(list(tags.filter(section_name='%package'))) == 9
        assert len(list(tags.filter(section_name='%package', name='Patch*'))) == 5
        assert len(list(tags.filter(section_name='%package', valid=False))) == 0
        assert len(list(tags.filter(valid=False))) == 1
        assert len(list(tags.filter(name='Requires', valid=None))) == 3
