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

import re

from typing import List, Tuple

from rebasehelper.plugins.spec_hooks import BaseSpecHook
from rebasehelper.types import PackageCategories


class TypoFix(BaseSpecHook):
    """Sample spec hook that fixes typos in spec file"""

    CATEGORIES: PackageCategories = [None]

    REPLACEMENTS: List[Tuple[str, str]] = [
        ('chnagelog', 'changelog'),
        ('indentional', 'intentional'),
    ]

    @classmethod
    def run(cls, spec_file, rebase_spec_file, **kwargs):
        for _, section in rebase_spec_file.spec_content.sections:
            for index, line in enumerate(section):
                for replacement in cls.REPLACEMENTS:
                    line = re.sub(replacement[0], replacement[1], line)
                section[index] = line
        rebase_spec_file.save()
