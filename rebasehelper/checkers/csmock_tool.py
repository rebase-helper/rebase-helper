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

from __future__ import print_function
import os
from six import StringIO

from rebasehelper.utils import ProcessHelper
from rebasehelper.utils import PathHelper
from rebasehelper.exceptions import CheckerNotFoundError
from rebasehelper.results_store import results_store
from rebasehelper.checker import BaseChecker


class CsmockTool(BaseChecker):
    """ Csmock compare tool."""

    CMD = "csmock"
    category = "SRPM"

    @classmethod
    def match(cls, cmd=None):
        if cmd == cls.CMD:
            return True
        else:
            return False

    @classmethod
    def get_checker_name(cls):
        return cls.CMD

    @classmethod
    def is_default(cls):
        return cls.DEFAULT

    @classmethod
    def run_check(cls, results_dir, **kwargs):
        """Compares old and new RPMs using pkgdiff"""
        csmock_report = {}

        old_pkgs = results_store.get_old_build().get('srpm', None)
        new_pkgs = results_store.get_new_build().get('srpm', None)
        csmock_dir = os.path.join(results_dir, cls.CMD)
        os.makedirs(csmock_dir)
        arguments = ['--force', '-a', '-r', 'fedora-rawhide-x86_64', '--base-srpm']
        if old_pkgs and new_pkgs:
            cmd = [cls.CMD]
            cmd.extend(arguments)
            cmd.append(old_pkgs)
            cmd.append(new_pkgs)
            cmd.extend(['-o', csmock_dir])
            output = StringIO()
            try:
                ProcessHelper.run_subprocess(cmd, output_file=output)
            except OSError:
                raise CheckerNotFoundError("Checker '%s' was not found or installed." % cls.CMD)
        csmock_report['error'] = PathHelper.find_all_files_current_dir(csmock_dir, '*.err')
        csmock_report['txt'] = PathHelper.find_all_files_current_dir(csmock_dir, '*.txt')
        csmock_report['log'] = PathHelper.find_all_files_current_dir(csmock_dir, '*.log')
        return csmock_report
