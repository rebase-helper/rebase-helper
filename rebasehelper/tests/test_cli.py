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
            'version': False,
            'build_only': False,
            'patch_only': False,
            'compare_pkgs_only': True,
            'sources': 'test-1.0.3.tar.gz',
            'verbose': True,
            'buildtool': 'rpmbuild',
            'difftool': 'vimdiff',
            'pkgcomparetool': ['rpmdiff'],
            'outputtool': 'json',
            'versioneer': None,
            'keep_workspace': True,
            'not_download_sources': True,
            'cont': True,
            'non_interactive': True,
            'disable_inapplicable_patches': False,
            'comparepkgs': 'test_dir',
            'build_tasks': ['123456', '654321'],
            'builds_nowait': True,
            'results_dir': '/tmp/rebase-helper',
            'builder_options': '\"-v\"',
            'get_old_build_from_koji': False,
            'color': 'auto',
            'changelog_entry': 'Update to %{version}',
            'srpm_builder_options': '\"-r fedora-26-x86_64\"',
            'srpm_buildtool': 'mock',
        }
        arguments = [
            'test-1.0.3.tar.gz', '--verbose',
            '--buildtool', 'rpmbuild', '--pkgcomparetool',
            'rpmdiff', '--outputtool', 'json', '--keep-workspace', '--not-download-sources', '--continue',
            '--non-interactive', '--comparepkgs-only', 'test_dir',
            '--builds-nowait', '--build-tasks', '123456,654321',
            '--results-dir', '/tmp/rebase-helper',
            '--builder-options=\"-v\"',
            '--changelog-entry', 'Update to %{version}',
            '--srpm-builder-options=\"-r fedora-26-x86_64\"',
            '--srpm-buildtool', 'mock',
        ]
        cli = CLI(arguments)
        for key, value in cli.args.__dict__.items():
            assert value == conf[key]
