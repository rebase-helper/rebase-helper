# -*- coding: utf-8 -*-
#
# This tool helps you to rebase package to the latest version
# Copyright (C) 2013-2014 Red Hat, Inc.
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
# Authors: Petr Hracek <phracek@redhat.com>
#          Tomas Hozza <thozza@redhat.com>

import re

from rebasehelper.specfile import BaseSpecHook


class PyPIURLFixHook(BaseSpecHook):
    """
    SpecHook for transforming old nonfunctional python package url to
    a safe url(eg. https://pypi.* to https://files.pythonhosted.*)
    """

    NAME = 'PyPI URL Fix'
    CATEGORIES = ['python']
    SOURCES_URL_TRANSFORMATIONS = [
        ('https?://pypi.python.org/', 'https://files.pythonhosted.org/'),
    ]

    @classmethod
    def get_name(cls):
        return cls.NAME

    @classmethod
    def get_categories(cls):
        return cls.CATEGORIES

    @classmethod
    def run(cls, spec_file, rebase_spec_file, **kwargs):
        """
        Run _transform_url() for all sources to replace all pypi.* urls by
        files.pythonhosted.* urls.
        """
        for index, line in enumerate(rebase_spec_file.spec_content):
            if line.startswith("Source"):
                rebase_spec_file.spec_content[index] = cls._transform_url(line)
        rebase_spec_file.save()

    @classmethod
    def _transform_url(cls, line):
        """
        Perform predefined URL transformations
        """
        for trans in cls.SOURCES_URL_TRANSFORMATIONS:
            if re.search(r".*https?://pypi.python.org/.*", line):
                line = re.sub(trans[0], trans[1], line)
        return line
