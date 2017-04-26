# -*- coding: utf-8 -*-
#
# This tool helps you to rebase package to the latest version
# Copyright (C) 2013-2014 Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# he Free Software Foundation; either version 2 of the License, or
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
# Authors: Petr Hracek <phracek@redhat.com>
#          Tomas Hozza <thozza@redhat.com>

import re

from rebasehelper.specfile import BaseSpecHook


class TypoFixHook(BaseSpecHook):
    """Sample spec hook that fixes typos in spec file"""

    NAME = 'Typo fix'
    REPLACEMENTS = [
        ('chnagelog', 'changelog'),
        ('indentional', 'intentional'),
    ]

    @classmethod
    def get_name(cls):
        return cls.NAME

    @classmethod
    def run(cls, spec_file, rebase_spec_file):
        for index, line in enumerate(rebase_spec_file.spec_content):
            for replacement in cls.REPLACEMENTS:
                line = re.sub(replacement[0], replacement[1], line)
            rebase_spec_file.spec_content[index] = line
        rebase_spec_file.save()
