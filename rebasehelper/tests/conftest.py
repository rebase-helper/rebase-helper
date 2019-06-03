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
import shutil

import pytest  # type: ignore

from rebasehelper.specfile import SpecFile


TESTS_DIR: str = os.path.dirname(__file__)
TEST_FILES_DIR: str = os.path.join(TESTS_DIR, 'testing_files')
SPEC_FILE: str = 'test.spec'


@pytest.yield_fixture(autouse=True)
def workdir(request, tmpdir_factory):
    with tmpdir_factory.mktemp('workdir').as_cwd():
        wd = os.getcwd()
        # copy testing files into workdir
        for file_name in getattr(request.cls, 'TEST_FILES', []):
            shutil.copy(os.path.join(TEST_FILES_DIR, file_name), wd)
        yield wd


@pytest.fixture
def spec_object(workdir):  # pylint: disable=redefined-outer-name
    shutil.copy(os.path.join(TEST_FILES_DIR, SPEC_FILE), workdir)
    return SpecFile(SPEC_FILE, workdir)


def pytest_collection_modifyitems(items):
    for item in items:
        # item is an instance of Function class.
        # https://github.com/pytest-dev/pytest/blob/master/_pytest/python.py
        if 'functional' in item.fspath.strpath:
            item.add_marker(pytest.mark.functional)
        else:
            item.add_marker(pytest.mark.standard)
