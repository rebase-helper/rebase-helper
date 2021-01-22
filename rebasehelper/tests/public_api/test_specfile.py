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
from rebasehelper.tags import Tag
from rebasehelper.tests.conftest import SPEC_FILE, TEST_FILES_DIR


@pytest.mark.public_api
class TestSpecFile:
    def test_constructor(self, workdir):
        shutil.copy(os.path.join(TEST_FILES_DIR, SPEC_FILE), workdir)
        # check that no mandatory argument was added
        spec = SpecFile(SPEC_FILE)
        assert isinstance(spec, SpecFile)
        # check that arguments were not renamed or removed
        spec = SpecFile(path=SPEC_FILE, sources_location=workdir, predefined_macros=None,
                        lookaside_cache_preset='fedpkg', keep_comments=False)
        assert isinstance(spec, SpecFile)

    def test_update_changelog(self, spec_object):
        assert spec_object.update_changelog('test2') is None
        assert spec_object.update_changelog(changelog_entry='test') is None

    def test_set_version(self, spec_object):
        assert spec_object.set_version('1.2.3.4') is None
        assert spec_object.set_version(version='1.2.3') is None

    def test_get_version(self, spec_object):
        assert isinstance(spec_object.get_version(), str)

    def test_set_release_number(self, spec_object):
        assert spec_object.set_release_number('2') is None
        assert spec_object.set_release_number(release='1') is None

    def test_set_release(self, spec_object):
        assert spec_object.set_release('2') is None
        assert spec_object.set_release(release='1') is None

    def test_get_sources(self, spec_object):
        assert isinstance(spec_object.get_sources(), list)

    def test_tag(self, spec_object):
        assert isinstance(spec_object.tag(name='Source*', section='%package'), Tag)
        assert spec_object.tag(name='NotATag') is None

    def test_set_tag(self, spec_object):
        assert spec_object.set_tag('Version', '1.3.5') is None
        assert spec_object.set_tag(tag='Version', value='1.3.5', preserve_macros=True) is None

    def test_save(self, spec_object):
        assert spec_object.save() is None

    def test_udpate(self, spec_object):
        assert spec_object.update() is None

    def test_process_patch_macros(self, spec_object):
        assert spec_object.process_patch_macros() is None
        assert spec_object.process_patch_macros(comment_out=[0], remove=[1], annotate=[2], note='test') is None
