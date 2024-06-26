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
from typing import List
from textwrap import dedent

import pytest  # type: ignore
from specfile.macros import Macro, MacroLevel

from rebasehelper.specfile import SpecFile


class TestSpecFile:
    NAME: str = 'test'
    VERSION: str = '1.0.2'
    OLD_ARCHIVE: str = NAME + '-' + VERSION + '.tar.xz'
    SOURCE_1: str = 'source-tests.sh'
    SOURCE_2: str = ''
    SOURCE_5: str = 'documentation.tar.xz'
    SOURCE_6: str = 'misc.zip'
    PATCH_1: str = 'test-testing.patch'
    PATCH_2: str = 'test-testing2.patch'
    PATCH_3: str = 'test-testing3.patch'
    PATCH_4: str = 'test-testing4.patch'

    TEST_FILES: List[str] = [
        OLD_ARCHIVE,
        SOURCE_1,
        SOURCE_5,
        SOURCE_6,
        PATCH_1,
        PATCH_2,
        PATCH_3,
        PATCH_4,
    ]

    def test_get_release(self, spec_object):
        assert spec_object.get_release() == '34'

    def test_set_release(self, spec_object):
        spec_object.set_release('0.1')
        assert spec_object.get_release() == '0.1'
        spec_object.set_release('22')
        assert spec_object.get_release() == '22'

    def test_set_version(self, spec_object):
        NEW_VERSION = '1.2.3.4.5'
        spec_object.set_version(NEW_VERSION)
        spec_object.save()
        assert spec_object.spec.expanded_version == NEW_VERSION

    @pytest.mark.parametrize('spec_attributes, sources', [
        (
            {
                'spec_content': dedent("""\
                    Source:     ftp://ftp.test.org/%{name}-%{version}.tar.xz
                    Source1:    source-tests.sh
                    Source2:    ftp://test.com/test-source.sh
                    #Source3:    source-tests.sh
                    """)
            },
            [
                'ftp://ftp.test.org/%{name}-%{version}.tar.xz',
                'source-tests.sh',
                'ftp://test.com/test-source.sh',
                None
            ]
        )
    ])
    def test__get_raw_source_string(self, mocked_spec_object, sources):
        # pylint: disable=protected-access
        for i, source in enumerate(sources):
            assert mocked_spec_object._get_raw_source_string(i) == source
        assert mocked_spec_object._get_raw_source_string(None) == None

    def test_old_tarball(self, spec_object):
        assert spec_object.get_main_source() == self.OLD_ARCHIVE

    def test_get_sources(self, workdir, spec_object):
        sources = [self.SOURCE_1, self.SOURCE_5, self.SOURCE_6, self.OLD_ARCHIVE]
        sources = [os.path.join(workdir, f) for f in sources]
        assert len(set(sources).intersection(set(spec_object.get_sources()))) == 4
        # The Source0 has to be always in the beginning
        assert spec_object.get_main_source() == 'test-1.0.2.tar.xz'

    def test_get_patches(self, workdir, spec_object):
        expected_patches = {0: [os.path.join(workdir, self.PATCH_1), 1],
                            1: [os.path.join(workdir, self.PATCH_2), 2],
                            2: [os.path.join(workdir, self.PATCH_3), 3],
                            3: [os.path.join(workdir, self.PATCH_4), 4]}
        patches = {}
        for index, p in enumerate(spec_object.get_patches()):
            patches[index] = [p.path, p.number]
        assert patches == expected_patches

    def test_split_version_string(self):
        assert SpecFile.split_version_string('1.0.1', '1.0.1') == ('1.0.1', None)
        assert SpecFile.split_version_string('1.0.1b1', '1.0.1') == ('1.0.1', 'b1')
        assert SpecFile.split_version_string('1.0.1rc1', '1.0.1') == ('1.0.1', 'rc1')
        assert SpecFile.split_version_string('1.1.3-rc6', '1.1.3') == ('1.1.3', 'rc6')
        assert SpecFile.split_version_string('1.1.3_rc6', '1.1.3') == ('1.1.3', 'rc6')
        assert SpecFile.split_version_string('1.1.3~rc6', '1.1.3') == ('1.1.3', 'rc6')
        assert SpecFile.split_version_string('1.1.1d', '1.1.1c') == ('1.1.1d', None)

    def test_extract_version_from_archive_name(self, spec_object):
        # Basic tests
        assert spec_object.extract_version_from_archive_name('test-1.0.1.tar.gz', '') == '1.0.1'
        assert spec_object.extract_version_from_archive_name('/home/user/test-1.0.1.tar.gz', '') == '1.0.1'
        assert spec_object.extract_version_from_archive_name('test-1.0.1.tar.gz',
                                                             'ftp://ftp.test.org/test-%{version}.tar.gz') == '1.0.1'
        assert spec_object.extract_version_from_archive_name('/home/user/test-1.0.1.tar.gz',
                                                             'ftp://ftp.test.org/test-%{version}.tar.gz') == '1.0.1'
        # Real world tests
        name = 'http://www.cups.org/software/%{version}/cups-%{version}-source.tar.bz2'
        assert spec_object.extract_version_from_archive_name('cups-1.7.5-source.tar.bz2',
                                                             name) == '1.7.5'
        name = 'ftp://ftp.isc.org/isc/bind9/%{VERSION}/bind-%{VERSION}.tar.gz'
        assert spec_object.extract_version_from_archive_name('bind-9.9.5rc2.tar.gz',
                                                             name) == '9.9.5rc2'
        name = 'http://www.thekelleys.org.uk/dnsmasq/%{?extrapath}%{name}-%{version}%{?extraversion}.tar.xz'
        assert spec_object.extract_version_from_archive_name('dnsmasq-2.69rc1.tar.xz',
                                                             name) == '2.69rc1'
        name = 'http://downloads.sourceforge.net/%{name}/%{name}-%{version}%{?prever:-%{prever}}.tar.xz'
        assert spec_object.extract_version_from_archive_name('log4cplus-1.1.3-rc3.tar.xz',
                                                             name) == '1.1.3-rc3'
        name = 'http://downloads.sourceforge.net/%{name}/%{name}-%{version}%{?prever:_%{prever}}.tar.xz'
        assert spec_object.extract_version_from_archive_name('log4cplus-1.1.3_rc3.tar.xz',
                                                             name) == '1.1.3_rc3'
        name = 'http://download.gnome.org/sources/libsigc++/%{release_version}/libsigc++-%{version}.tar.xz'
        assert spec_object.extract_version_from_archive_name('libsigc++-2.10.0.tar.xz',
                                                             name) == '2.10.0'

    @pytest.mark.parametrize('spec_attributes, main_files', [
        (
            {
                'spec_content': dedent("""\
                    %files
                    %files -n test
                    %files test
                    """)
            },
            'files'
        ),
        (
            {
                'spec_content': dedent("""\
                    %files -n test
                    """)
            },
            None
        ),
    ], ids=[
        'has-main-files',
        'no-main-files',
    ])
    def test_get_main_files_section(self, mocked_spec_object, main_files):
        assert mocked_spec_object.get_main_files_section() == main_files

    @pytest.mark.parametrize('spec_attributes, is_enabled', [
        (
            {
                'spec_content': dedent("""\
                    %check
                    make test
                    """)
            },
            True
        ),
        (
            {
                'spec_content': dedent("""\
                    %check
                    # disabled test
                    # make test
                    """)
            },
            False
        ),
    ], ids=[
        'is_enabled',
        'is_disabled',
    ])
    def test_is_test_suite_enabled(self, mocked_spec_object, is_enabled):
        assert mocked_spec_object.is_test_suite_enabled() is is_enabled

    def test_set_extra_version(self, spec_object):
        spec_object.set_version('1.0.3')
        spec_object.set_extra_version('beta1', True)
        assert spec_object.get_release() == '0.1.beta1'
        spec_object.set_extra_version('beta2', False)
        assert spec_object.get_release() == '0.2.beta2'
        spec_object.set_extra_version('rc', False)
        assert spec_object.get_release() == '0.3.rc'
        spec_object.set_version('1.0.4')
        spec_object.set_extra_version(None, True)
        assert spec_object.get_release() == '1'
        spec_object.set_extra_version('g1234567', False)
        assert spec_object.get_release() == '2.g1234567'

    @pytest.mark.parametrize('spec_attributes', [
        {
            'spec_content': dedent("""\
                %global release 34
                %global release_str %{release}%{?dist}

                Name:    test
                Version: 1.0.2
                Release: %{release_str}

                %prep
                %setup -q -c -a 5
                """),
            'macros':
                [
                    Macro('release', None, '34', MacroLevel.SPEC, True),
                    Macro('release_str', None, '%{release}%{?dist}', MacroLevel.SPEC, True),
                    Macro('name', None, 'test', MacroLevel.SPEC, False),
                    Macro('version', None, '1.0.2', MacroLevel.SPEC, False),
                ],
        }
    ])
    def test_update_setup_dirname(self, mocked_spec_object):
        mocked_spec_object.set_extra_version('rc1', False)

        prep = mocked_spec_object.spec.sections().content.prep # pylint: disable=no-member
        mocked_spec_object.update_setup_dirname('test-1.0.2')
        assert mocked_spec_object.spec.sections().content.prep == prep # pylint: disable=no-member

        mocked_spec_object.update_setup_dirname('test-1.0.2rc1')
        assert (
            mocked_spec_object.spec.prep().content.setup.options.n # pylint: disable=no-member
            == '%{name}-%{version}rc1'
        )

        mocked_spec_object.update_setup_dirname('test-1.0.2-rc1')
        assert (
            mocked_spec_object.spec.prep().content.setup.options.n # pylint: disable=no-member
            == '%{name}-%{version}-rc1'
        )

    def test_find_archive_target_in_prep(self, spec_object):
        target = spec_object.find_archive_target_in_prep('documentation.tar.xz')
        assert target == 'test-1.0.2'
        target = spec_object.find_archive_target_in_prep('misc.zip')
        assert target == 'test-1.0.2/misc'

    @pytest.mark.parametrize('spec_attributes, kwargs, expected_content', [
        (
            {
                'removed_patches': [],
                'spec_content': dedent("""\
                    Patch0:    0.patch
                    Patch1:    1.patch

                    %patchlist
                    2.patch
                    3.patch

                    %prep
                    %patch -P 0 -p0
                    %patch -P 1 -p1
                    %patch -P 2 -p2
                    %patch -P 3 -p3
                    """),
            },
            {
                'patches_dict':
                    {
                        'deleted': ['2.patch'],
                        'inapplicable': ['1.patch'],
                    },
                'disable_inapplicable': False,
            },
            dedent("""\
                Patch0:    0.patch
                Patch1:    1.patch

                %patchlist
                3.patch

                %prep
                %patch -P 0 -p0
                # The following patch contains conflicts
                %patch -P 1 -p1
                %patch -P 2 -p3
                """)
        ),
        (
            {
                'removed_patches': [],
                'spec_content': dedent("""\
                    Patch0:    0.patch
                    Patch1:    1.patch

                    %patchlist
                    2.patch
                    3.patch

                    %prep
                    %patch -P 0 -p0
                    %patch -P 1 -p1
                    %patch -P 2 -p2
                    %patch -P 3 -p3
                    """),
            },
            {
                'patches_dict':
                    {
                        'deleted': ['2.patch'],
                        'inapplicable': ['1.patch'],
                    },
                'disable_inapplicable': True,
            },
            dedent("""\
        Patch0:    0.patch
        #Patch1:    1.patch

        %patchlist
        3.patch

        %prep
        %patch -P 0 -p0
        # The following patch contains conflicts
        #%%patch -P 1 -p1
        %patch -P 1 -p3
        """),
        ),
        (
            {
                'removed_patches': [],
                'spec_content': dedent("""\
                    Patch0:     0.patch
                    
                    
                    # Patch comment
                    # line2
                    Patch1:     1.patch
                    
                    Patch2:     2.patch
                    """),
            },
            {
                'patches_dict':
                    {
                        'deleted': ['1.patch'],
                    },
                'disable_inapplicable': False,
            },
            dedent("""\
            Patch0:     0.patch
            
            Patch2:     2.patch
            """),
        ),
        (
            {
                'removed_patches': [],
                'spec_content': dedent("""\
                    Patch0:    0.patch
                    Patch1:    1.patch

                    %patchlist
                    2.patch
                    3.patch

                    %prep
                    %patch -P 0 -p0
                    %patch -P 1 -p1
                    %patch -P 2 -p2
                    %patch -P 3 -p3
                    """),
            },
            {
                'patches_dict':
                    {
                        'modified': ['1.patch', '2.patch'],
                    },
                'disable_inapplicable': False,
            },
            dedent("""\
                Patch0:    0.patch
                Patch1:    rebase-helper-results/rebased-sources/1.patch

                %patchlist
                rebase-helper-results/rebased-sources/2.patch
                3.patch

                %prep
                %patch -P 0 -p0
                %patch -P 1 -p1
                %patch -P 2 -p2
                %patch -P 3 -p3
                """)
        ),
    ], ids=[
        'do_not_disable_inapplicable',
        'disable_inapplicable',
        'comments_and_blank_lines',
        'modified_patches'
    ])
    def test_write_updated_patches(self, mocked_spec_object, kwargs, expected_content):
        mocked_spec_object.write_updated_patches(**kwargs)
        assert expected_content == str(mocked_spec_object.spec)

    @pytest.mark.parametrize('spec_attributes', [
        {
            'spec_content': 'Patch5: rebase-helper-results/rebased-sources/test-testing5.patch\n'
        }
    ])
    def test_update_paths_to_sources_and_patches(self, mocked_spec_object):
        assert 'rebased-sources' in mocked_spec_object.spec.patches().content[0].location # pylint: disable=no-member
        mocked_spec_object.update_paths_to_sources_and_patches()
        assert 'rebased-sources' not in mocked_spec_object.spec.patches().content[0].location # pylint: disable=no-member

    def test_tags(self, spec_object):
        tags = spec_object.spec.tags().content # pylint: disable=no-member
        # sanity check
        assert tags.name.name == 'Name'
        # no workaround
        assert 'Patch100' in tags
        assert 'Patch101' in tags
        assert 'Patch102' in tags
        spec_object.spec.macros.append(('use_workaround', '1'))
        spec_object.update()
        tags = spec_object.spec.tags().content # pylint: disable=no-member
        # workaround
        assert 'Patch100' in tags
        assert 'Patch101' in tags
        assert 'Patch102' in tags
        assert tags.patch100.expanded_value == 'workaround_base.patch'
        assert tags.patch101.expanded_value == 'workaround_1.patch'
        assert tags.patch102.expanded_value == 'workaround_2.patch'
