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
import re

import pytest  # type: ignore

from typing import List

from rebasehelper.specfile import SpecFile, SpecContent
from rebasehelper.tests.conftest import SPEC_FILE


class TestSpecFile:
    NAME: str = 'test'
    VERSION: str = '1.0.2'
    OLD_ARCHIVE: str = NAME + '-' + VERSION + '.tar.xz'
    SOURCE_0: str = 'test-source.sh'
    SOURCE_1: str = 'source-tests.sh'
    SOURCE_2: str = ''
    SOURCE_4: str = 'file.txt.bz2'
    SOURCE_5: str = 'documentation.tar.xz'
    SOURCE_6: str = 'misc.zip'
    SOURCE_7: str = 'positional-1.1.0.tar.gz'
    PATCH_1: str = 'test-testing.patch'
    PATCH_2: str = 'test-testing2.patch'
    PATCH_3: str = 'test-testing3.patch'
    PATCH_4: str = 'test-testing4.patch'
    BUILD_MISSING_LOG: str = 'build_missing.log'
    BUILD_OBSOLETES_LOG: str = 'build_obsoletes.log'

    TEST_FILES: List[str] = [
        OLD_ARCHIVE,
        SOURCE_0,
        SOURCE_1,
        SOURCE_4,
        SOURCE_5,
        SOURCE_6,
        SOURCE_7,
        PATCH_1,
        PATCH_2,
        PATCH_3,
        PATCH_4,
        BUILD_MISSING_LOG,
        BUILD_OBSOLETES_LOG
    ]

    def test_get_release(self, spec_object):
        match = re.search(r'([0-9.]*[0-9]+)\w*', spec_object.get_release())
        assert match is not None
        assert match.group(1) == spec_object.get_release_number()

    def test_get_release_number(self, spec_object):
        assert spec_object.get_release_number() == '34'

    def test_set_release_number(self, spec_object):
        spec_object.set_release_number(0.1)
        assert spec_object.get_release_number() == '0.1'
        spec_object.set_release_number(22)
        assert spec_object.get_release_number() == '22'

    def test_get_version(self, spec_object):
        assert spec_object.get_version() == self.VERSION

    def test_set_version(self, spec_object):
        NEW_VERSION = '1.2.3.4.5'
        spec_object.set_version(NEW_VERSION)
        spec_object.save()
        assert spec_object.get_version() == NEW_VERSION

    def test_set_version_using_archive(self, spec_object):
        NEW_VERSION = '1.2.3.4.5'
        ARCHIVE_NAME = 'test-{0}.tar.xz'.format(NEW_VERSION)
        spec_object.set_version_using_archive(ARCHIVE_NAME)
        spec_object.save()
        assert spec_object.get_version() == NEW_VERSION

    def test_get_package_name(self, spec_object):
        assert spec_object.get_package_name() == self.NAME

    def test__write_spec_content(self, spec_object):
        # pylint: disable=protected-access
        new_content = 'testing line 1\ntesting line 2\n'
        spec_object.spec_content = SpecContent(new_content)
        spec_object._write_spec_content()
        with open(SPEC_FILE) as spec:
            assert new_content == spec.read()

    def test__get_raw_source_string(self, spec_object):
        # pylint: disable=protected-access
        assert spec_object._get_raw_source_string(0) == 'ftp://ftp.test.org/%{name}-%{version}.tar.xz'
        assert spec_object._get_raw_source_string(1) == 'source-tests.sh'
        assert spec_object._get_raw_source_string(2) == 'ftp://test.com/test-source.sh'
        assert spec_object._get_raw_source_string(3) is None

    def test_old_tarball(self, spec_object):
        assert spec_object.get_archive() == self.OLD_ARCHIVE

    def test_get_sources(self, workdir, spec_object):
        sources = [self.SOURCE_0, self.SOURCE_1, self.SOURCE_4, self.SOURCE_5,
                   self.SOURCE_6, self.SOURCE_7, self.OLD_ARCHIVE]
        sources = [os.path.join(workdir, f) for f in sources]
        assert len(set(sources).intersection(set(spec_object.get_sources()))) == 7
        # The Source0 has to be always in the beginning
        assert spec_object.get_archive() == 'test-1.0.2.tar.xz'

    def test_get_patches(self, workdir, spec_object):
        expected_patches = {0: [os.path.join(workdir, self.PATCH_1), 1],
                            1: [os.path.join(workdir, self.PATCH_2), 2],
                            2: [os.path.join(workdir, self.PATCH_3), 3],
                            3: [os.path.join(workdir, self.PATCH_4), 4]}
        patches = {}
        for index, p in enumerate(spec_object.get_patches()):
            patches[index] = [p.path, p.index]
        assert patches == expected_patches

    def test_get_requires(self, spec_object):
        expected = {'openssl-devel', 'pkgconfig', 'texinfo', 'gettext', 'autoconf'}
        req = spec_object.get_requires()
        assert len(expected.intersection(req)) == len(expected)

    def test_split_version_string(self):
        assert SpecFile.split_version_string() == (None, None, None)
        assert SpecFile.split_version_string('1.0.1') == ('1.0.1', '', '')
        assert SpecFile.split_version_string('1.0.1b1') == ('1.0.1', 'b1', '')
        assert SpecFile.split_version_string('1.0.1rc1') == ('1.0.1', 'rc1', '')
        assert SpecFile.split_version_string('1.1.3-rc6') == ('1.1.3', 'rc6', '-')
        assert SpecFile.split_version_string('1.1.3_rc6') == ('1.1.3', 'rc6', '_')
        assert SpecFile.split_version_string('.1.1.1') == ('1.1.1', '', '')

    def test_extract_version_from_archive_name(self):
        # Basic tests
        assert SpecFile.extract_version_from_archive_name('test-1.0.1.tar.gz') == ('1.0.1', '', '')
        assert SpecFile.extract_version_from_archive_name('/home/user/test-1.0.1.tar.gz') == ('1.0.1', '', '')
        assert SpecFile.extract_version_from_archive_name('test-1.0.1.tar.gz',
                                                          'ftp://ftp.test.org/test-%{version}.tar.gz') == ('1.0.1',
                                                                                                           '',
                                                                                                           '')
        assert SpecFile.extract_version_from_archive_name('/home/user/test-1.0.1.tar.gz',
                                                          'ftp://ftp.test.org/test-%{version}.tar.gz') == ('1.0.1',
                                                                                                           '',
                                                                                                           '')
        # Real world tests
        name = 'http://www.cups.org/software/%{version}/cups-%{version}-source.tar.bz2'
        assert SpecFile.extract_version_from_archive_name('cups-1.7.5-source.tar.bz2',
                                                          name) == ('1.7.5', '', '')
        # the 'rc1' can't be in the version number
        name = 'ftp://ftp.isc.org/isc/bind9/%{VERSION}/bind-%{VERSION}.tar.gz'
        assert SpecFile.extract_version_from_archive_name('bind-9.9.5rc2.tar.gz',
                                                          name) == ('9.9.5', 'rc2', '')
        name = 'http://www.thekelleys.org.uk/dnsmasq/%{?extrapath}%{name}-%{version}%{?extraversion}.tar.xz'
        assert SpecFile.extract_version_from_archive_name('dnsmasq-2.69rc1.tar.xz',
                                                          name) == ('2.69', 'rc1', '')
        name = 'http://downloads.sourceforge.net/%{name}/%{name}-%{version}%{?prever:-%{prever}}.tar.xz'
        assert SpecFile.extract_version_from_archive_name('log4cplus-1.1.3-rc3.tar.xz',
                                                          name) == ('1.1.3', 'rc3', '-')
        name = 'http://downloads.sourceforge.net/%{name}/%{name}-%{version}%{?prever:_%{prever}}.tar.xz'
        assert SpecFile.extract_version_from_archive_name('log4cplus-1.1.3_rc3.tar.xz',
                                                          name) == ('1.1.3', 'rc3', '_')
        name = 'http://download.gnome.org/sources/libsigc++/%{release_version}/libsigc++-%{version}.tar.xz'
        assert SpecFile.extract_version_from_archive_name('libsigc++-2.10.0.tar.xz',
                                                          name) == ('2.10.0', '', '')

    def test_get_main_files_section(self, spec_object):
        assert spec_object.get_main_files_section() == '%files'

    def test_is_test_suite_enabled(self, spec_object):
        found = spec_object.is_test_suite_enabled()
        assert found is True

    def test_set_extra_version_some_extra_version(self, spec_object):
        spec_object.set_extra_version('b1')
        preamble = spec_object.spec_content.section('%package')
        assert preamble[0] == '%global REBASE_EXTRA_VER b1'
        assert preamble[1] == '%global REBASE_VER %{version}%{REBASE_EXTRA_VER}'
        old_source_index = preamble.index('#Source: ftp://ftp.test.org/%{name}-%{version}.tar.xz')
        assert preamble[old_source_index + 1] == 'Source: ftp://ftp.test.org/%{name}-%{REBASE_VER}.tar.xz'
        # the release number was changed
        assert spec_object.get_release_number() == '0.1'
        # the release string now contains the extra version
        match = re.search(r'([0-9.]*[0-9]+)\.b1\w*', spec_object.get_release())
        assert match is not None
        assert match.group(1) == spec_object.get_release_number()

    def test_set_extra_version_no_extra_version(self, spec_object):
        spec_object.set_extra_version('')
        assert spec_object.spec_content.section('%package')[0] != '%global REBASE_EXTRA_VER b1'
        assert spec_object.spec_content.section('%package')[1] != '%global REBASE_VER %{version}%{REBASE_EXTRA_VER}'
        assert spec_object.get_release_number() == '1'

    def test_redefine_release_with_macro(self, spec_object):
        macro = '%{REBASE_VER}'
        spec_object.redefine_release_with_macro(macro)
        preamble = spec_object.spec_content.section('%package')
        old_release_index = preamble.index('#Release: %{release_str}')
        assert preamble[old_release_index + 1] == 'Release: 34' + '.' + macro + '%{?dist}'

    def test_revert_redefine_release_with_macro(self, spec_object):
        macro = '%{REBASE_VER}'
        spec_object.redefine_release_with_macro(macro)
        spec_object.revert_redefine_release_with_macro(macro)
        assert 'Release: %{release_str}' in spec_object.spec_content.section('%package')

    def test_get_extra_version_not_set(self, spec_object):
        assert spec_object.get_extra_version() == ''

    def test_get_extra_version_set(self, spec_object):
        spec_object.set_extra_version('rc1')
        assert spec_object.get_extra_version() == 'rc1'

    def test_update_setup_dirname(self, spec_object):
        spec_object.set_extra_version('rc1')

        prep = spec_object.spec_content.section('%prep')
        spec_object.update_setup_dirname('test-1.0.2')
        assert spec_object.spec_content.section('%prep') == prep

        spec_object.update_setup_dirname('test-1.0.2rc1')
        prep = spec_object.spec_content.section('%prep')
        setup = [l for l in prep if l.startswith('%setup')][0]
        assert '-n %{name}-%{REBASE_VER}' in setup

        spec_object.update_setup_dirname('test-1.0.2-rc1')
        prep = spec_object.spec_content.section('%prep')
        setup = [l for l in prep if l.startswith('%setup')][0]
        assert '-n %{name}-%{version}-%{REBASE_EXTRA_VER}' in setup

    def test_find_archive_target_in_prep(self, spec_object):
        target = spec_object.find_archive_target_in_prep('documentation.tar.xz')
        assert target == 'test-1.0.2'
        target = spec_object.find_archive_target_in_prep('misc.zip')
        assert target == 'test-1.0.2/misc'

    def test_update_paths_to_patches(self, spec_object):
        """
        Check updated paths to patches in the rebased directory
        :return:
        """
        line = [l for l in spec_object.spec_content.section('%package') if l.startswith('Patch5')][0]
        assert 'rebased-sources' in line

        spec_object.update_paths_to_patches()

        line = [l for l in spec_object.spec_content.section('%package') if l.startswith('Patch5')][0]
        assert 'rebased-sources' not in line

    @pytest.mark.parametrize('preserve_macros', [
        False,
        True,
    ], ids=[
        'ignoring_macros',
        'preserving_macros',
    ])
    @pytest.mark.parametrize('tag, value, lines, lines_preserve', [
        (
            'Summary',
            'A testing SPEC file',
            [
                '%{!?specfile: %global specfile spec file}',
                '%global summary %{?longsum}%{!?longsum:A testing %{specfile}}',
                'Summary: A testing SPEC file',
            ],
            [
                '%{!?specfile: %global specfile SPEC file}',
                '%global summary %{?longsum}%{!?longsum:A testing %{specfile}}',
                'Summary: %{summary}',
            ],
        ),
        (
            'Version',
            '1.1.8',
            [
                '%global version_major 1',
                '%global version_minor 0',
                '%global version_patch 2',
                '%global version_major_minor %{version_major}.%{version_minor}',
                '%global version %{version_major_minor}.%{version_patch}',
                'Version: 1.1.8',
            ],
            [
                '%global version_major 1',
                '%global version_minor 1',
                '%global version_patch 8',
                '%global version_major_minor %{version_major}.%{version_minor}',
                '%global version %{version_major_minor}.%{version_patch}',
                'Version: %{version}',
            ],
        ),
        (
            'Release',
            '42%{?dist}',
            [
                '%global release 34',
                '%global release_str %{release}%{?dist}',
                'Release: 42%{?dist}',
            ],
            [
                '%global release 42',
                '%global release_str %{release}%{?dist}',
                'Release: %{release_str}',
            ],
        ),
        (
            'Source8',
            'https://github.com/rebase-helper/rebase-helper/archive/'
            'b0ed0b235bd5ea295fc897e1e2e8e6b6637f2c2d/'
            'rebase-helper-b0ed0b235bd5ea295fc897e1e2e8e6b6637f2c2d.tar.gz',
            [
                '%global project rebase-helper',
                '%global commit d70cb5a2f523db5b6088427563531f43b7703859',
                'Source8: https://github.com/rebase-helper/rebase-helper/archive/'
                'b0ed0b235bd5ea295fc897e1e2e8e6b6637f2c2d/'
                'rebase-helper-b0ed0b235bd5ea295fc897e1e2e8e6b6637f2c2d.tar.gz',
            ],
            [
                '%global project rebase-helper',
                '%global commit b0ed0b235bd5ea295fc897e1e2e8e6b6637f2c2d',
                'Source8: https://github.com/%{project}/%{project}/archive/%{commit}/%{project}-%{commit}.tar.gz',
            ],
        ),
    ], ids=[
        'Summary=>"A testing SPEC file..."',
        'Version=>"1.1.8"',
        'Release=>"42%{?dist}"',
        'Source8=>"https://github.com/rebase-helper/rebase-helper/archive/..."',
    ])
    def test_set_tag(self, spec_object, preserve_macros, tag, value, lines, lines_preserve):
        spec_object.set_tag(tag, value, preserve_macros=preserve_macros)
        for line in lines_preserve if preserve_macros else lines:
            assert line in spec_object.spec_content.section('%package')
