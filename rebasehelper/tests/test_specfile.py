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

import os
import shutil
import six
import re

from .base_test import BaseTest
from rebasehelper.specfile import SpecFile, spec_hooks_runner
from rebasehelper.build_log_analyzer import BuildLogAnalyzer
from rebasehelper.spec_hooks.typo_fix import TypoFixHook


class TestSpecFile(BaseTest):
    """ SpecFile tests """
    NAME = 'test'
    VERSION = '1.0.2'
    OLD_ARCHIVE = NAME + '-' + VERSION + '.tar.xz'
    SPEC_FILE = 'test.spec'
    SOURCE_0 = 'test-source.sh'
    SOURCE_1 = 'source-tests.sh'
    SOURCE_2 = ''
    SOURCE_4 = 'file.txt.bz2'
    SOURCE_5 = 'documentation.tar.xz'
    SOURCE_6 = 'misc.zip'
    PATCH_1 = 'test-testing.patch'
    PATCH_2 = 'test-testing2.patch'
    PATCH_3 = 'test-testing3.patch'
    PATCH_4 = 'test-testing4.patch'
    BUILD_MISSING_LOG = 'build_missing.log'
    BUILD_OBSOLETES_LOG = 'build_obsoletes.log'

    TEST_FILES = [
        SPEC_FILE,
        PATCH_1,
        PATCH_2,
        PATCH_3,
        PATCH_4,
        BUILD_MISSING_LOG,
        BUILD_OBSOLETES_LOG
    ]

    def setup(self):
        super(TestSpecFile, self).setup()
        self.SPEC_FILE_OBJECT = SpecFile(self.SPEC_FILE, self.WORKING_DIR, download=False)

    def test_get_release(self):
        match = re.search(r'([0-9.]*[0-9]+)\w*', self.SPEC_FILE_OBJECT.get_release())
        assert match is not None
        assert match.group(1) == self.SPEC_FILE_OBJECT.get_release_number()

    def test_get_release_number(self):
        assert self.SPEC_FILE_OBJECT.get_release_number() == '34'

    def test_set_release_number(self):
        self.SPEC_FILE_OBJECT.set_release_number(0.1)
        assert self.SPEC_FILE_OBJECT.get_release_number() == '0.1'
        self.SPEC_FILE_OBJECT.set_release_number(22)
        assert self.SPEC_FILE_OBJECT.get_release_number() == '22'

    def test_get_version(self):
        assert self.SPEC_FILE_OBJECT.get_version() == self.VERSION

    def test_set_version(self):
        NEW_VERSION = '1.2.3.4.5'
        self.SPEC_FILE_OBJECT.set_version(NEW_VERSION)
        self.SPEC_FILE_OBJECT.save()
        assert self.SPEC_FILE_OBJECT.get_version() == NEW_VERSION

    def test_set_version_using_archive(self):
        NEW_VERSION = '1.2.3.4.5'
        ARCHIVE_NAME = 'test-{0}.tar.xz'.format(NEW_VERSION)
        self.SPEC_FILE_OBJECT.set_version_using_archive(ARCHIVE_NAME)
        self.SPEC_FILE_OBJECT.save()
        assert self.SPEC_FILE_OBJECT.get_version() == NEW_VERSION

    def test_get_package_name(self):
        assert self.SPEC_FILE_OBJECT.get_package_name() == self.NAME

    def test__write_spec_file_to_disc(self):
        new_content = [
            'testing line 1\n',
            'testing line 2\n'
        ]
        self.SPEC_FILE_OBJECT.spec_content = new_content
        self.SPEC_FILE_OBJECT._write_spec_file_to_disc()
        with open(self.SPEC_FILE) as spec:
            assert new_content == spec.readlines()

    def test__get_raw_source_string(self):
        assert self.SPEC_FILE_OBJECT._get_raw_source_string(0) == 'ftp://ftp.test.org/%{name}-%{version}.tar.xz'
        assert self.SPEC_FILE_OBJECT._get_raw_source_string(1) == 'source-tests.sh'
        assert self.SPEC_FILE_OBJECT._get_raw_source_string(2) == 'ftp://test.com/test-source.sh'
        assert self.SPEC_FILE_OBJECT._get_raw_source_string(3) is None

    def test_old_tarball(self):
        assert self.SPEC_FILE_OBJECT.get_archive() == self.OLD_ARCHIVE

    def test_get_sources(self):
        sources = [self.SOURCE_0, self.SOURCE_1, self.SOURCE_4, self.SOURCE_5, self.SOURCE_6, self.OLD_ARCHIVE]
        sources = [os.path.join(self.WORKING_DIR, f) for f in sources]
        assert len(set(sources).intersection(set(self.SPEC_FILE_OBJECT.get_sources()))) == 6
        # The Source0 has to be always in the beginning
        assert self.SPEC_FILE_OBJECT.get_archive() == 'test-1.0.2.tar.xz'

    def test_get_patches(self):
        expected_patches = {0: [os.path.join(self.WORKING_DIR, self.PATCH_1), 0],
                            1: [os.path.join(self.WORKING_DIR, self.PATCH_2), 1],
                            2: [os.path.join(self.WORKING_DIR, self.PATCH_3), 2],
                            3: [os.path.join(self.WORKING_DIR, self.PATCH_4), 3]}
        patches = {}
        for index, p in enumerate(self.SPEC_FILE_OBJECT.get_patches()):
            patches[index] = [p.get_path(), p.get_index()]
        assert patches == expected_patches

    def test_get_requires(self):
        expected = set(['openssl-devel', 'pkgconfig', 'texinfo', 'gettext', 'autoconf'])
        req = self.SPEC_FILE_OBJECT.get_requires()
        assert len(expected.intersection(req)) == len(expected)

    def test_get_paths_with_rpm_macros(self):
        raw_paths = ['/usr/bin/binary1',
                     '/usr/sbin/binary2',
                     '/usr/include/header.h',
                     '/usr/lib/library1.so',
                     '/usr/lib64/library2.so',
                     '/usr/libexec/script.sh',
                     '/usr/lib/systemd/system/daemond.service',
                     '/usr/share/man/man1/test.1.gz',
                     '/usr/share/info/file.info',
                     '/usr/share/doc/RFC.pdf',
                     '/usr/share/config.site',
                     '/var/lib/libvirt',
                     '/var/tmp/abrt',
                     '/var/lock']

        expected_paths = set(['%{_bindir}/binary1',
                              '%{_sbindir}/binary2',
                              '%{_includedir}/header.h',
                              '%{_libdir}/library1.so',
                              '%{_libdir}/library2.so',
                              '%{_libexecdir}/script.sh',
                              '%{_unitdir}/daemond.service',
                              '%{_mandir}/man1/test.1.gz',
                              '%{_infodir}/file.info',
                              '%{_docdir}/RFC.pdf',
                              '%{_datarootdir}/config.site',
                              '%{_sharedstatedir}/libvirt',
                              '%{_tmppath}/abrt',
                              '%{_localstatedir}/lock'])
        paths = SpecFile.get_paths_with_rpm_macros(raw_paths)
        assert len(set(paths)) == len(expected_paths)
        assert len(expected_paths.intersection(set(paths))) == len(expected_paths)

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

    def test__split_sections(self):
        expected_sections = {
            0: ['%header', ['Summary: A testing spec file\n',
                            'Name: test\n',
                            'Version: 1.0.2\n',
                            'Release: 34%{?dist}\n',
                            'License: GPL2+\n',
                            'Group: System Environment\n',
                            'URL: http://testing.org\n',
                            '\n',
                            '# Note: non-current tarballs get moved to the history/ subdirectory,\n',
                            '# so look there if you fail to retrieve the version you want\n',
                            'Source: ftp://ftp.test.org/%{name}-%{version}.tar.xz\n',
                            'Source1: source-tests.sh\n',
                            'Source2: ftp://test.com/test-source.sh\n',
                            '#Source3: source-tests.sh\n',
                            'Source4: file.txt.bz2\n',
                            'Source5: documentation.tar.xz\n',
                            'Source6: misc.zip\n',
                            'Patch1: test-testing.patch\n',
                            'Patch2: test-testing2.patch\n',
                            'Patch3: test-testing3.patch\n',
                            'Patch4: test-testing4.patch\n',
                            '\n',
                            'BuildRequires: openssl-devel, pkgconfig, texinfo, gettext, autoconf\n',
                            '\n']],
            1: ['%description', ['Testing spec file\n',
                                 '\n']],
            2: ['%package devel', ['Summary: A testing devel package\n',
                                   '\n']],
            3: ['%description devel', ['Testing devel spec file\n',
                                       '\n']],
            4: ['%prep', ['%setup -q -a 5\n',
                          '%patch1\n',
                          '%patch2 -p1\n',
                          '%patch3 -p1 -b .testing3\n',
                          '%patch4 -p0 -b .testing4\n',
                          'mkdir misc\n',
                          'tar -xf %{SOURCE6} -C misc\n',
                          '\n']],
            5: ['%build', ['autoreconf -vi\n',
                           '\n',
                           '%configure\n',
                           'make TEST\n',
                           '\n']],
            6: ['%install', ['make DESTDIR=$RPM_BUILD_ROOT install\n',
                             '\n']],
            7: ['%check', ['#to run make check use "--with check"\n',
                           '%if %{?_with_check:1}%{!?_with_check:0}\n',
                           'make check\n',
                           '%endif\n',
                           '\n']],
            8: ['%files', ['%{_bindir}/file.txt\n',
                           '\n']],
            9: ['%files devel', ['%{_bindir}/test_example\n',
                                 '%{_libdir}/my_test.so\n',
                                 '\n']],
            10: ['%changelog', ['* Wed Apr 26 2017 Nikola Forró <nforro@redhat.com> - 1.0.2-34\n',
                                '- This is chnagelog entry with some indentional typos\n',
                                '\n',
                                '* Wed Nov 12 2014 Tomas Hozza <thozza@redhat.com> 1.0.0-33\n',
                                '- Bump the release for testing purposes\n',
                                '\n',
                                '* Tue Sep 24 2013 Petr Hracek <phracek@redhat.com> 1.0.0-1\n',
                                '- Initial version\n',
                                '\n']]
        }
        sections = self.SPEC_FILE_OBJECT._split_sections()
        for key, value in six.iteritems(expected_sections):
            assert sections[key][0] == value[0]
            assert sections[key][1] == value[1]

    def test_get_spec_section(self):
        expected_section = ['%{_bindir}/file.txt\n',
                            '\n']
        section = self.SPEC_FILE_OBJECT.get_spec_section('%files')
        assert section == expected_section

    def test_spec_missing_file(self):
        files = {'missing': ['/usr/bin/test2']}
        self.SPEC_FILE_OBJECT.modify_spec_files_section(files)
        section = self.SPEC_FILE_OBJECT.get_spec_section('%files')
        expected = ['#BEGIN THIS MODIFIED BY REBASE-HELPER\n',
                    '%{_bindir}/test2\n',
                    '#END THIS MODIFIED BY REBASE-HELPER\n',
                    '%{_bindir}/file.txt\n',
                    '\n']
        assert expected == section

    def test_spec_remove_file(self):
        files = {'deleted': ['/usr/lib/test.so']}
        self.SPEC_FILE_OBJECT.modify_spec_files_section(files)
        section = self.SPEC_FILE_OBJECT.get_spec_section('%files devel')
        assert '%{_libdir}/test.so' not in section

    def test_spec_missing_and_remove_file(self):
        files = {'missing': ['/usr/bin/test2'],
                 'deleted': ['/usr/lib/my_test.so']}
        self.SPEC_FILE_OBJECT.modify_spec_files_section(files)
        section = self.SPEC_FILE_OBJECT.get_spec_section('%files')
        expected = ['#BEGIN THIS MODIFIED BY REBASE-HELPER\n',
                    '%{_bindir}/test2\n',
                    '#END THIS MODIFIED BY REBASE-HELPER\n',
                    '%{_bindir}/file.txt\n',
                    '\n']
        assert expected == section
        section_devel = self.SPEC_FILE_OBJECT.get_spec_section('%files devel')
        expected_devel = ['%{_bindir}/test_example\n',
                          '#BEGIN THIS MODIFIED BY REBASE-HELPER\n',
                          '#%{_libdir}/my_test.so\n\n',
                          '#END THIS MODIFIED BY REBASE-HELPER\n',
                          '\n']
        assert expected_devel == section_devel

    def test_spec_missing_from_logfile(self):
        shutil.move('build_missing.log', 'build.log')
        files = BuildLogAnalyzer.parse_log(self.WORKING_DIR, 'build.log')
        self.SPEC_FILE_OBJECT.modify_spec_files_section(files)
        section = self.SPEC_FILE_OBJECT.get_spec_section('%files')
        expected = ['#BEGIN THIS MODIFIED BY REBASE-HELPER\n',
                    '%{_bindir}/test2\n',
                    '#END THIS MODIFIED BY REBASE-HELPER\n',
                    '%{_bindir}/file.txt\n',
                    '\n']
        assert expected == section

    def test_spec_obsolete_from_logfile(self):
        shutil.move('build_obsoletes.log', 'build.log')
        files = BuildLogAnalyzer.parse_log(self.WORKING_DIR, 'build.log')
        self.SPEC_FILE_OBJECT.modify_spec_files_section(files)
        section = self.SPEC_FILE_OBJECT.get_spec_section('%files')
        assert '%{_libdir}/libtest.so' not in section

    def test_is_test_suite_enabled(self):
        found = self.SPEC_FILE_OBJECT.is_test_suite_enabled()
        assert found is True

    def test_set_extra_version_some_extra_version(self):
        self.SPEC_FILE_OBJECT.set_extra_version('b1')
        with open(self.SPEC_FILE_OBJECT.get_path()) as f:
            # 1st line
            assert f.readline() == '%global REBASE_EXTRA_VER b1\n'
            # 2nd line
            assert f.readline() == '%global REBASE_VER %{version}%{REBASE_EXTRA_VER}\n'
            while True:
                line = f.readline()
                if line == '#Source: ftp://ftp.test.org/%{name}-%{version}.tar.xz\n':
                    break
                assert line is not None
            # there is new Source0 after old commented out entry
            assert f.readline() == 'Source: ftp://ftp.test.org/%{name}-%{REBASE_VER}.tar.xz\n'
        # the release number was changed
        assert self.SPEC_FILE_OBJECT.get_release_number() == '0.1'
        # the release string now contains the extra version
        match = re.search(r'([0-9.]*[0-9]+)\.b1\w*', self.SPEC_FILE_OBJECT.get_release())
        assert match is not None
        assert match.group(1) == self.SPEC_FILE_OBJECT.get_release_number()

    def test_set_extra_version_no_extra_version(self):
        self.SPEC_FILE_OBJECT.set_extra_version('')
        with open(self.SPEC_FILE_OBJECT.get_path()) as f:
            # 1st line
            assert f.readline() != '%global REBASE_EXTRA_VER b1\n'
            # 2nd line
            assert f.readline() != '%global REBASE_VER %{version}%{REBASE_EXTRA_VER}\n'
        # the release number was changed
        assert self.SPEC_FILE_OBJECT.get_release_number() == '1'

    def test_redefine_release_with_macro(self):
        macro = '%{REBASE_VER}'
        self.SPEC_FILE_OBJECT.redefine_release_with_macro(macro)
        with open(self.SPEC_FILE_OBJECT.get_path()) as f:
            while f.readline() != '#Release: 34%{?dist}\n':
                pass
            assert f.readline() == 'Release: 34' + '.' + macro + '%{?dist}\n'

    def test_revert_redefine_release_with_macro(self):
        macro = '%{REBASE_VER}'
        self.SPEC_FILE_OBJECT.redefine_release_with_macro(macro)
        self.SPEC_FILE_OBJECT.revert_redefine_release_with_macro(macro)
        with open(self.SPEC_FILE_OBJECT.get_path()) as f:
            for line in f.readlines():
                if line.startswith('Release:'):
                    assert line == 'Release: 34%{?dist}\n'
                    return
        # the line has to be found, fail if not!
        assert False

    def test_get_extra_version_not_set(self):
        assert self.SPEC_FILE_OBJECT.get_extra_version() == ''

    def test_get_extra_version_set(self):
        self.SPEC_FILE_OBJECT.set_extra_version('rc1')
        assert self.SPEC_FILE_OBJECT.get_extra_version() == 'rc1'

    def test_update_changelog(self):
        changelog = []
        changelog.append('* Mon Jan 01 1970 Rebase-helper <rebase-helper@rebase-helper.com> - 1.2.3')
        changelog.append('- New upstream version 1.2.3')
        self.SPEC_FILE_OBJECT.insert_changelog(changelog)
        result = self.SPEC_FILE_OBJECT.get_spec_section('%changelog')
        assert changelog[0] == result[0]
        assert changelog[1] == result[1]

    def test_patch_macro(self):
        self.SPEC_FILE_OBJECT._correct_rebased_patches(['4'])
        self.SPEC_FILE_OBJECT._write_spec_file_to_disc()
        expected_patch = ['%patch4 -b .testing4 -p1\n']
        with open(self.SPEC_FILE) as spec:
            lines = spec.readlines()
        lines = [x for x in lines if x.startswith('%patch4')]
        assert expected_patch == lines

    def test_update_setup_dirname(self):
        prep = self.SPEC_FILE_OBJECT.get_spec_section('%prep')
        self.SPEC_FILE_OBJECT.update_setup_dirname('test-1.0.2')
        assert self.SPEC_FILE_OBJECT.get_spec_section('%prep') == prep

        self.SPEC_FILE_OBJECT.update_setup_dirname('test-1.0.2rc1')
        prep = self.SPEC_FILE_OBJECT.get_spec_section('%prep')
        assert '%setup -q -a 5 -n %{name}-%{REBASE_VER}' in prep

        self.SPEC_FILE_OBJECT.update_setup_dirname('test-1.0.2-rc1')
        prep = self.SPEC_FILE_OBJECT.get_spec_section('%prep')
        assert '%setup -q -a 5 -n %{name}-%{version}-%{REBASE_EXTRA_VER}' in prep

    def test_find_archive_target_in_prep(self):
        target = self.SPEC_FILE_OBJECT.find_archive_target_in_prep('documentation.tar.xz')
        assert target == 'test-1.0.2'
        target = self.SPEC_FILE_OBJECT.find_archive_target_in_prep('misc.zip')
        assert target == 'test-1.0.2/misc'

    def test_typo_fix_spec_hook(self):
        assert TypoFixHook.get_name() in spec_hooks_runner.spec_hooks
        assert '- This is chnagelog entry with some indentional typos\n' in self.SPEC_FILE_OBJECT.spec_content
        spec_hooks_runner.run_spec_hooks(None, self.SPEC_FILE_OBJECT)
        assert '- This is changelog entry with some intentional typos\n' in self.SPEC_FILE_OBJECT.spec_content
