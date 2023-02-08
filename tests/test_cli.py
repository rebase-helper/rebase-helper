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

from rebasehelper.cli import CLI


class TestCLI:
    def test_cli_unit(self):
        """Function tests cli class with all arguments"""
        conf = {
            'verbose': True,
            'srpm_buildtool': 'mock',
            'buildtool': 'rpmbuild',
            'outputtool': 'json',
            'keep_workspace': True,
            'not_download_sources': True,
            'non_interactive': True,
            'builds_nowait': True,
            'build_tasks': ['123456', '654321'],
            'results_dir': '/tmp/rebase-helper',
            'srpm_builder_options': '\"-r fedora-26-x86_64\"',
            'builder_options': '\"-v\"',
            'changelog_entry': 'Update to %{version}',
            'sources': 'test-1.0.3.tar.gz',
            'version': False,
            'versioneer': None,
            'disable_inapplicable_patches': False,
            'get_old_build_from_koji': False,
            'color': 'auto',
        }
        arguments = [
            '--verbose',
            '--srpm-buildtool', 'mock',
            '--buildtool', 'rpmbuild',
            '--outputtool', 'json',
            '--keep-workspace',
            '--not-download-sources',
            '--non-interactive',
            '--builds-nowait',
            '--build-tasks', '123456,654321',
            '--results-dir', '/tmp/rebase-helper',
            '--srpm-builder-options=\"-r fedora-26-x86_64\"',
            '--builder-options=\"-v\"',
            '--changelog-entry', 'Update to %{version}',
            'test-1.0.3.tar.gz',
        ]
        cli = CLI(arguments)
        for key, value in cli.args.__dict__.items():
            assert value == conf[key]
