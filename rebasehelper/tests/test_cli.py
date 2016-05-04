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

from rebasehelper.cli import CLI


class TestCLI(object):
    """
    The test suite is used for testing CLI class
    """
    def test_cli_unit(self):
        """Function tests cli class with all arguments"""
        conf = {'build_only': True,
                'patch_only': True,
                'sources': 'test-1.0.3.tar.gz',
                'verbose': True,
                'buildtool': 'rpmbuild',
                'difftool': 'vimdiff',
                'pkgcomparetool': 'rpmdiff',
                'outputtool': 'xml',
                'keep_workspace': True,
                'not_download_sources': True,
                'cont': True,
                'non_interactive': True,
                'comparepkgs': 'test_dir',
                'build_tasks': '123456,654321',
                'builds_nowait': True,
                'results_dir': '/tmp/rebase-helper'}
        arguments = ['--build-only', '--patch-only', 'test-1.0.3.tar.gz', '--verbose',
                     '--buildtool', 'rpmbuild', '--pkgcomparetool',
                     'rpmdiff', '--outputtool', 'xml', '--keep-workspace', '--not-download-sources', '--continue',
                     '--non-interactive', '--comparepkgs-only', 'test_dir',
                     '--builds-nowait', '--build-tasks', '123456,654321',
                     '--results-dir', '/tmp/rebase-helper']
        cli = CLI(arguments)
        for key, value in cli.args.__dict__.items():
            assert cli.args.__dict__[key] == conf[key]
