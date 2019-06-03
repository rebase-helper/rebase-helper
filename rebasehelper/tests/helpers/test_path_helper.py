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

from rebasehelper.helpers.path_helper import PathHelper


class TestPathHelper:
    """ PathHelper tests """

    @pytest.fixture
    def filelist(self):
        files = [
            'file',
            'ffile',
            'ppythooon',
            'dir1/fileee',
            'dir1/faa/pythooon',
            'dir1/foo/pythooon',
            'dir1/foo/bar/file',
            'dir1/foo/baz/file',
            'dir1/baz/ffile',
            'dir1/bar/file',
            'dir1/baz/bar/ffile',
            'dir1/baz/bar/test.spec',
        ]

        for f in files:
            try:
                os.makedirs(os.path.dirname(f))
            except OSError:
                pass
            with open(f, 'w') as fd:
                fd.write(f)

        return files

    class TestFindFirstDirWithFile:
        """ PathHelper - find_first_dir_with_file() tests """
        def test_find_file(self, filelist):
            assert PathHelper.find_first_dir_with_file(
                "dir1", "file") == os.path.abspath(
                os.path.dirname(filelist[9]))
            assert PathHelper.find_first_dir_with_file(
                os.path.curdir, "file") == os.path.abspath(os.path.dirname(filelist[0]))
            assert PathHelper.find_first_dir_with_file(
                "dir1/baz", "file") is None

        def test_find_ffile(self, filelist):
            assert PathHelper.find_first_dir_with_file(
                "dir1", "*le") == os.path.abspath(
                os.path.dirname(filelist[9]))
            assert PathHelper.find_first_dir_with_file(
                "dir1", "ff*") == os.path.abspath(
                os.path.dirname(filelist[8]))
            assert PathHelper.find_first_dir_with_file(
                "dir1/foo", "ff*") is None

        def test_find_pythoon(self, filelist):
            assert PathHelper.find_first_dir_with_file(
                "dir1", "pythooon") == os.path.abspath(
                os.path.dirname(filelist[4]))
            assert PathHelper.find_first_dir_with_file(
                os.path.curdir, "py*n") == os.path.abspath(os.path.dirname(filelist[4]))
            assert PathHelper.find_first_dir_with_file(
                "dir1/bar", "pythooon") is None

    class TestFindFirstFile:
        """ PathHelper - find_first_file() tests """
        def test_find_file(self, filelist):
            assert PathHelper.find_first_file(
                "dir1", "file") == os.path.abspath(filelist[9])
            assert PathHelper.find_first_file(
                os.path.curdir, "file") == os.path.abspath(filelist[0])
            assert PathHelper.find_first_file("dir1/baz", "file") is None

        def test_find_ffile(self, filelist):
            assert PathHelper.find_first_file(
                "dir1", "*le") == os.path.abspath(filelist[9])
            assert PathHelper.find_first_file(
                "dir1", "ff*") == os.path.abspath(filelist[8])
            assert PathHelper.find_first_file("dir1/foo", "ff*") is None

        def test_find_pythoon(self, filelist):
            assert PathHelper.find_first_file(
                "dir1", "pythooon") == os.path.abspath(filelist[4])
            assert PathHelper.find_first_file(
                os.path.curdir, "py*n") == os.path.abspath(filelist[4])
            assert PathHelper.find_first_file("dir1/bar", "pythooon") is None

        def test_find_with_recursion(self, filelist):
            assert PathHelper.find_first_file(os.path.curdir, "*.spec", 0) is None
            assert PathHelper.find_first_file(os.path.curdir, "*.spec", 1) is None
            assert PathHelper.find_first_file(os.path.curdir, "*.spec", 2) is None
            assert PathHelper.find_first_file(os.path.curdir, "*.spec", 3) is None
            assert PathHelper.find_first_file(os.path.curdir, "*.spec", 4) == os.path.abspath(filelist[-1])

        def test_find_without_recursion(self, filelist):
            assert PathHelper.find_first_file(os.path.curdir, "*.spec") == os.path.abspath(filelist[-1])
