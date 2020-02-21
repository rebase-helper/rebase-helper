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

from textwrap import dedent
from types import SimpleNamespace

import pytest  # type: ignore

from rebasehelper.tags import Tags
from rebasehelper.plugins.spec_hooks.typo_fix import TypoFix
from rebasehelper.plugins.spec_hooks.pypi_url_fix import PyPIURLFix
from rebasehelper.plugins.spec_hooks.escape_macros import EscapeMacros
from rebasehelper.plugins.spec_hooks.replace_old_version import ReplaceOldVersion
from rebasehelper.plugins.spec_hooks.paths_to_rpm_macros import PathsToRPMMacros


class TestSpecHook:

    @pytest.mark.parametrize('spec_attributes', [
        {
            'spec_content': '%changelog\n- This is chnagelog entry with some indentional typos'
        }
    ])
    def test_typo_fix_spec_hook(self, mocked_spec_object):
        assert '- This is chnagelog entry with some indentional typos' in \
               mocked_spec_object.spec_content.section('%changelog')
        TypoFix.run(mocked_spec_object, mocked_spec_object)
        assert '- This is changelog entry with some intentional typos' in \
               mocked_spec_object.spec_content.section('%changelog')

    @pytest.mark.parametrize('spec_attributes', [
        {
            'spec_content': dedent("""\
                %files
                /usr/share/man/man1/*
                /usr/bin/%{name}
                %config(noreplace) /etc/test/test.conf

                %files devel
                %{_bindir}/test_example
                %{_libdir}/my_test.so
                /usr/share/test1.txt
                /no/macros/here
                """),
            'macros': {},
        }
    ])
    def test_paths_to_rpm_macros_spec_hook(self, mocked_spec_object):
        files = [
            '%{_mandir}/man1/*',
            '%{_bindir}/%{name}',
            '%config(noreplace) %{_sysconfdir}/test/test.conf',
            '',
        ]
        files_devel = [
            '%{_bindir}/test_example',
            '%{_libdir}/my_test.so',
            '%{_datadir}/test1.txt',
            '/no/macros/here',
        ]
        PathsToRPMMacros.run(mocked_spec_object, mocked_spec_object)
        assert files == mocked_spec_object.spec_content.section('%files')
        assert files_devel == mocked_spec_object.spec_content.section('%files devel')

    @pytest.mark.parametrize('spec_attributes', [
        {
            'spec_content': dedent("""\
                Source9: https://test.com/#/1.0/%{name}-hardcoded-version-1.0.2.tar.gz

                %build
                autoreconf -vi # Unescaped macros %name %{name}
                """)
        }
    ])
    def test_escape_macros_spec_hook(self, mocked_spec_object):
        EscapeMacros.run(mocked_spec_object, mocked_spec_object)
        build = mocked_spec_object.spec_content.section('%build')
        assert build[0] == "autoreconf -vi # Unescaped macros %%name %%{name}"
        # Test that the string after `#` wasn't recognized as a comment.
        source9 = mocked_spec_object.get_raw_tag_value('Source9')
        assert source9 == "https://test.com/#/1.0/%{name}-hardcoded-version-1.0.2.tar.gz"

    @pytest.mark.parametrize('replace_with_macro', [
        True,
        False,
    ], ids=[
        'new-version',
        'macro',
    ])
    @pytest.mark.parametrize('spec_attributes', [
        {
            'spec_content': dedent("""\
                Version: 1.0.2
                Source9: https://test.com/#/1.0/%{name}-hardcoded-version-1.0.2b1.tar.gz
                Recommends: test > 1.0.2

                %changelog
                * Wed Apr 26 2017 Nikola Forró <nforro@redhat.com> - 1.0.2-34
                - Update to 1.0.2
                """),
            'header': SimpleNamespace(version='1.0.2', release='0.1.b1'),
        }
    ])
    def test_replace_old_version_spec_hook(self, mocked_spec_object, mocked_spec_object_copy, replace_with_macro):
        mocked_spec_object_copy.header.version = '1.1.0'
        mocked_spec_object_copy.header.release = '1'
        mocked_spec_object_copy.set_raw_tag_value('Version', '1.1.0')
        ReplaceOldVersion.run(mocked_spec_object, mocked_spec_object_copy,
                              replace_old_version_with_macro=replace_with_macro)
        # The spec is not saved due to mocking, refresh tags for the assertions
        mocked_spec_object_copy.tags = Tags(mocked_spec_object_copy.spec_content, mocked_spec_object_copy.spec_content)

        # Check if the version has been updated
        test_source = mocked_spec_object_copy.get_raw_tag_value('Source9')
        if replace_with_macro:
            assert test_source == 'https://test.com/#/1.1/%{name}-hardcoded-version-%{version}.tar.gz'
        else:
            assert test_source == 'https://test.com/#/1.1/%{name}-hardcoded-version-1.1.0.tar.gz'

        # Check if dependency and Version tags are ignored
        assert mocked_spec_object_copy.get_raw_tag_value('Recommends') == 'test > 1.0.2'
        assert mocked_spec_object_copy.get_raw_tag_value('Version') == '1.1.0'

        # Check if version in changelog hasn't been changed
        changelog = mocked_spec_object_copy.spec_content.section('%changelog')
        assert '1.0.2' in changelog[0]

    @pytest.mark.parametrize('spec_attributes', [
        {
            'spec_content': dedent("""\
                URL: https://pypi.python.org/pypi/%{name}
                Source0: https://pypi.python.org/.../%{name}.%{version}.tar.gz
                """)
        }
    ])
    def test_pypi_to_python_hosted_url_trans(self, mocked_spec_object):
        PyPIURLFix.run(mocked_spec_object, mocked_spec_object)
        expected = {
            'URL': 'https://pypi.org/project/%{name}',
            'Source0': 'https://files.pythonhosted.org/.../%{name}.%{version}.tar.gz',
        }
        for tag, value in expected.items():
            assert value == mocked_spec_object.get_raw_tag_value(tag)
