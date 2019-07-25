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


import pytest  # type: ignore

from rebasehelper.plugins.spec_hooks.typo_fix import TypoFix
from rebasehelper.plugins.spec_hooks.pypi_url_fix import PyPIURLFix
from rebasehelper.plugins.spec_hooks.escape_macros import EscapeMacros
from rebasehelper.plugins.spec_hooks.replace_old_version import ReplaceOldVersion
from rebasehelper.plugins.spec_hooks.paths_to_rpm_macros import PathsToRPMMacros


class TestSpecHook:
    def test_typo_fix_spec_hook(self, spec_object):
        assert '- This is chnagelog entry with some indentional typos' in spec_object.spec_content.section('%changelog')
        TypoFix.run(spec_object, spec_object)
        assert '- This is changelog entry with some intentional typos' in spec_object.spec_content.section('%changelog')

    def test_paths_to_rpm_macros_spec_hook(self, spec_object):
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
            '',
        ]
        PathsToRPMMacros.run(spec_object, spec_object)
        assert files == spec_object.spec_content.section('%files')
        assert files_devel == spec_object.spec_content.section('%files devel')

    def test_escape_macros_spec_hook(self, spec_object):
        EscapeMacros.run(spec_object, spec_object)
        assert spec_object.spec_content.section('%build')[0] == "autoreconf -vi # Unescaped macros %%name %%{name}"
        # Test that the string after `#` wasn't recognized as a comment.
        source9 = [line for line in spec_object.spec_content.section('%package') if line.startswith('Source9')][0]
        assert source9 == "Source9: https://test.com/#/1.0/%{name}-hardcoded-version-1.0.2.tar.gz"

    @pytest.mark.parametrize('replace_with_macro', [
        True,
        False,
    ], ids=[
        'new-version',
        'macro',
    ])
    def test_replace_old_version_spec_hook(self, spec_object, replace_with_macro):
        new_spec = spec_object.copy('new.spec')
        new_spec.set_version('1.1.0')
        ReplaceOldVersion.run(spec_object, new_spec, replace_old_version_with_macro=replace_with_macro)
        # Check if the version has been updated
        test_source = [line for line in new_spec.spec_content.section('%package') if line.startswith('Source9')]
        assert test_source
        if replace_with_macro:
            expected_result = 'https://test.com/#/1.1/%{name}-hardcoded-version-%{version}.tar.gz'
        else:
            expected_result = 'https://test.com/#/1.1/%{name}-hardcoded-version-1.1.0.tar.gz'
        assert test_source[0].split()[1] == expected_result

        # Check if version in changelog hasn't been changed
        changelog = new_spec.spec_content.section('%changelog')
        assert '1.0.2' in changelog[0]

    def test_pypi_to_python_hosted_url_trans(self, spec_object):
        # pylint: disable=protected-access
        assert 'https://pypi.python.org/' in spec_object._get_raw_source_string(7)
        PyPIURLFix.run(spec_object, spec_object)
        assert 'https://files.pythonhosted.org/' in spec_object._get_raw_source_string(7)
