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
from rebasehelper.logger import logger

from rebasehelper.specfile import BaseSpecHook


class PypiUrlFixHook(BaseSpecHook):
    """SpecHook for transforming old nonfunctional python package url to
    a safe url(eg. https://pypi.* to https://files.pythonhosted.*)"""

    NAME = 'Pypi Url Fix'
    SOURCES_URL_TRANSFORMATIONS = [
        ('^https?://pypi.python.org/', 'https://files.pythonhosted.org/'),
    ]

    @classmethod
    def get_name(cls):
        return cls.NAME

    @classmethod
    def run(cls, spec_file, rebase_spec_file):
        """
        Run _transform_url() for all sources to replace all pypi.* urls by
        files.pythonhosted.* urls.
        """

        sources = rebase_spec_file.sources
        old_sources = list(rebase_spec_file.sources)

	# find and transform the appropriate sources
        for index, source in enumerate(sources):
            sources[index] = cls._transform_url(source)

	# save changes to the new spec_file
        for index, line in enumerate(rebase_spec_file.spec_content):
            for srcind, new_sources in enumerate(rebase_spec_file.sources):
                line = re.sub(old_sources[srcind], new_sources, line)
            rebase_spec_file.spec_content[index] = line
        rebase_spec_file.save()

    @classmethod
    def _transform_url(cls, url):
        """
        Perform predefined URL transformations
        """
        for trans in cls.SOURCES_URL_TRANSFORMATIONS:
            url = re.sub(trans[0], trans[1], url)
        return url
