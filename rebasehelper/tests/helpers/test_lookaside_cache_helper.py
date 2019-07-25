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

import pytest  # type: ignore

from typing import List

from rebasehelper.helpers.lookaside_cache_helper import LookasideCacheHelper


class TestLookasideCacheHelper:

    TEST_FILES: List[str] = [
        'documentation.tar.xz',
        'archive.tar.bz2',
    ]

    @pytest.mark.parametrize('package, filename, hashtype, hsh', [
        ('vim-go', 'v1.6.tar.gz', 'md5', '847d3e3577982a9515ad0aec6d5111b2'),
        ('rebase-helper', '0.8.0.tar.gz', 'md5', '91de540caef64cb8aa7fd250f2627a93'),
        (
                'man-pages',
                'man-pages-posix-2013-a.tar.xz',
                'sha512',
                'e6ec8eb57269fadf368aeaac31b5a98b9c71723d4d5cc189f9c4642d6e865c88'
                'e44f77481dccbdb72e31526488eb531f624d455016361687a834ccfcac19fa14',
        ),
    ], ids=[
        'vim-go',
        'rebase-helper',
        'man-pages',
    ])
    @pytest.mark.integration
    def test_download(self, package, filename, hashtype, hsh):
        # pylint: disable=protected-access
        target = os.path.basename(filename)
        LookasideCacheHelper._download_source('fedpkg',
                                              'https://integration:4430/pkgs',
                                              package,
                                              filename,
                                              hashtype,
                                              hsh,
                                              target)
        assert os.path.isfile(target)
        assert LookasideCacheHelper._hash(target, hashtype) == hsh

    @pytest.mark.parametrize('filename, hashtype, hsh', [
        ('documentation.tar.xz', 'md5', '03a77b3e59deec24c1d70a495e41602b'),
        (
                'archive.tar.bz2',
                'sha512',
                '6bab9c2cc6b73fbba27be45c6b5dc57a0d763e12e6a71bcc9fbdde61611ccaed'
                'f4474a09dc6e4f65e267f12ecd6d314ab87e6a43f1e62ea7d124720903e40eb4',
        ),
    ], ids=[
        'documentation.tar.xz',
        'archive.tar.bz2',
    ])
    @pytest.mark.integration
    def test_upload(self, filename, hashtype, hsh):
        # pylint: disable=protected-access
        LookasideCacheHelper._upload_source('https://integration:4430/pkgs',
                                            'test',
                                            '',
                                            filename,
                                            hashtype,
                                            hsh,
                                            None)
