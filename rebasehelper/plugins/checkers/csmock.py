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

import io
import os

from typing import Optional

from rebasehelper.helpers.process_helper import ProcessHelper
from rebasehelper.helpers.path_helper import PathHelper
from rebasehelper.exceptions import CheckerNotFoundError
from rebasehelper.results_store import results_store
from rebasehelper.plugins.checkers import BaseChecker, CheckerCategory


class CsMock(BaseChecker):
    """csmock checker"""

    CATEGORY: Optional[CheckerCategory] = CheckerCategory.SRPM

    CMD: str = 'csmock'

    @classmethod
    def is_available(cls):
        try:
            return ProcessHelper.run_subprocess([cls.CMD, '--help'], output_file=ProcessHelper.DEV_NULL) == 0
        except (IOError, OSError):
            return False

    @classmethod
    def run_check(cls, results_dir, **kwargs):
        """Compares old and new RPMs using pkgdiff"""
        csmock_report = {}

        old_pkgs = results_store.get_old_build().get('srpm', None)
        new_pkgs = results_store.get_new_build().get('srpm', None)
        results_dir = os.path.join(results_dir, cls.CMD)
        os.makedirs(results_dir)
        arguments = ['--force', '-a', '-r', 'fedora-rawhide-x86_64', '--base-srpm']
        if old_pkgs and new_pkgs:
            cmd = [cls.CMD]
            cmd.extend(arguments)
            cmd.append(old_pkgs)
            cmd.append(new_pkgs)
            cmd.extend(['-o', results_dir])
            output = io.StringIO()
            try:
                ProcessHelper.run_subprocess(cmd, output_file=output)
            except OSError:
                raise CheckerNotFoundError("Checker '{}' was not found or installed.".format(cls.name))
        csmock_report['error'] = PathHelper.find_all_files_current_dir(results_dir, '*.err')
        csmock_report['txt'] = PathHelper.find_all_files_current_dir(results_dir, '*.txt')
        csmock_report['log'] = PathHelper.find_all_files_current_dir(results_dir, '*.log')
        csmock_report['path'] = cls.get_checker_output_dir_short()
        return csmock_report

    @classmethod
    def format(cls, data):
        """
        Formats csmock data to string
        :param data: csmock data dictionary
        :return: string formated output
        """
        output_lines = [cls.get_underlined_title("csmock")]
        output_lines.append("Details in {}:".format(data['path']))
        for key, files_list in data.items():
            if key in ['error', 'txt', 'log'] and files_list:
                for f in files_list:
                    output_lines.append(" - {}".format(os.path.basename(f)))

        return output_lines
