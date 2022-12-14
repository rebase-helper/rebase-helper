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

import pytest  # type: ignore
from specfile.macros import Macro, MacroLevel

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
        assert (
            '- This is chnagelog entry with some indentional typos'
            in mocked_spec_object.spec.sections().content.changelog # pylint: disable=no-member
        )
        TypoFix.run(mocked_spec_object, mocked_spec_object)
        assert (
            '- This is changelog entry with some intentional typos'
            in mocked_spec_object.spec.sections().content.changelog # pylint: disable=no-member
        )

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
            'macros':
                [
                    Macro('_bindir', None, '/usr/bin', MacroLevel.MACROFILES, False),
                    Macro('_libdir', None, '/usr/lib', MacroLevel.MACROFILES, False),
                    Macro('_datadir', None, '/usr/share', MacroLevel.MACROFILES, False),
                    Macro('_mandir', None, '%{_datadir}/man', MacroLevel.MACROFILES, False),
                    Macro('_sysconfdir', None, '/etc', MacroLevel.MACROFILES, False),
                ]
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
        sections = mocked_spec_object.spec.sections().content # pylint: disable=no-member
        assert files == list(sections.files)
        assert files_devel == list(getattr(sections, 'files devel'))

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
        assert (
            mocked_spec_object.spec.sections().content.build[0] # pylint: disable=no-member
            == "autoreconf -vi # Unescaped macros %%name %%{name}"
        )
        # Test that the string after `#` wasn't recognized as a comment.
        assert (
            mocked_spec_object.spec.tags().content.source9.value # pylint: disable=no-member
            == "https://test.com/#/1.0/%{name}-hardcoded-version-1.0.2.tar.gz"
        )

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
                Release: 0.1.b1
                Source9: https://test.com/#/1.0/%{name}-hardcoded-version-1.0.2b1.tar.gz
                Recommends: test > 1.0.2

                %changelog
                * Wed Apr 26 2017 Nikola Forró <nforro@redhat.com> - 1.0.2-34
                - Update to 1.0.2
                """)
        }
    ])
    def test_replace_old_version_spec_hook(self, mocked_spec_object, mocked_spec_object_copy, replace_with_macro):
        mocked_spec_object_copy.spec.version = '1.1.0'
        mocked_spec_object_copy.spec.release = '1'
        ReplaceOldVersion.run(mocked_spec_object, mocked_spec_object_copy,
                              replace_old_version_with_macro=replace_with_macro)

        # Check if the version has been updated
        test_source = mocked_spec_object_copy.spec.sources().content[0].location # pylint: disable=no-member
        if replace_with_macro:
            assert test_source == 'https://test.com/#/1.1/%{name}-hardcoded-version-%{version}.tar.gz'
        else:
            assert test_source == 'https://test.com/#/1.1/%{name}-hardcoded-version-1.1.0.tar.gz'

        # Check if dependency and Version tags are ignored
        tags = mocked_spec_object_copy.spec.tags().content # pylint: disable=no-member
        assert tags.recommends.value == 'test > 1.0.2'
        assert tags.version.value == '1.1.0'

        # Check if version in changelog hasn't been changed
        assert '1.0.2' in mocked_spec_object_copy.spec.sections().content.changelog[0] # pylint: disable=no-member

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
        tags = mocked_spec_object.spec.tags().content # pylint: disable=no-member
        for tag, value in expected.items():
            assert value == getattr(tags, tag).value
