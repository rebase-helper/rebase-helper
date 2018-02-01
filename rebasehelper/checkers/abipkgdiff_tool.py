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

import rpm

from rebasehelper.utils import ProcessHelper, RpmHelper
from rebasehelper.logger import logger
from rebasehelper.exceptions import RebaseHelperError, CheckerNotFoundError
from rebasehelper.results_store import results_store
from rebasehelper import settings
from rebasehelper.checker import BaseChecker


class AbiCheckerTool(BaseChecker):
    """abipkgdiff compare tool"""

    CMD = "abipkgdiff"
    DEFAULT = True
    results_dir = ''
    log_name = 'abipkgdiff.log'

    # Example
    # abipkgdiff --d1 dbus-glib-debuginfo-0.80-3.fc12.x86_64.rpm \
    # --d2 dbus-glib-debuginfo-0.104-3.fc23.x86_64.rpm \
    # dbus-glib-0.80-3.fc12.x86_64.rpm dbus-glib-0.104-3.fc23.x86_64.rpm
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
    def _get_packages_for_abipkgdiff(cls, input_structure=None):
        debug_package = None
        rest_packages = None
        packages = input_structure.get('rpm', [])
        if packages:
            debug_package = [x for x in packages if 'debuginfo' in os.path.basename(x)]
            rest_packages = [x for x in packages if 'debuginfo' not in os.path.basename(x)]

        return debug_package, rest_packages

    @classmethod
    def _find_debuginfo(cls, debug, pkg):
        name = RpmHelper.split_nevra(os.path.basename(pkg))['name']
        debuginfo = '{}-debuginfo'.format(name)
        find = [x for x in debug if RpmHelper.split_nevra(os.path.basename(x))['name'] == debuginfo]
        if find:
            return find[0]
        srpm = RpmHelper.get_info_from_rpm(pkg, rpm.RPMTAG_SOURCERPM)
        debuginfo = '{}-debuginfo'.format(RpmHelper.split_nevra(srpm)['name'])
        find = [x for x in debug if RpmHelper.split_nevra(os.path.basename(x))['name'] == debuginfo]
        if find:
            return find[0]
        return None

    @classmethod
    def run_check(cls, results_dir):
        """Compares old and new RPMs using abipkgdiff"""
        debug_old, rest_pkgs_old = cls._get_packages_for_abipkgdiff(results_store.get_build('old'))
        debug_new, rest_pkgs_new = cls._get_packages_for_abipkgdiff(results_store.get_build('new'))
        cmd = [cls.CMD]
        reports = {}
        for pkg in rest_pkgs_old:
            command = list(cmd)
            debug = cls._find_debuginfo(debug_old, pkg)
            if debug:
                command.append('--d1')
                command.append(debug)
            old_name = RpmHelper.split_nevra(os.path.basename(pkg))['name']
            find = [x for x in rest_pkgs_new if RpmHelper.split_nevra(os.path.basename(x))['name'] == old_name]
            if not find:
                logger.warning('New version of package %s was not found!', old_name)
                continue
            new_pkg = find[0]
            debug = cls._find_debuginfo(debug_new, new_pkg)
            if debug:
                command.append('--d2')
                command.append(debug)
            command.append(pkg)
            command.append(new_pkg)
            logger.debug('Package name for ABI comparison %s', old_name)
            output = os.path.join(cls.results_dir, results_dir, old_name + '-' + cls.log_name)
            try:
                ret_code = ProcessHelper.run_subprocess(command, output=output)
            except OSError:
                raise CheckerNotFoundError("Checker '%s' was not found or installed." % cls.CMD)

            if int(ret_code) & settings.ABIDIFF_ERROR and int(ret_code) & settings.ABIDIFF_USAGE_ERROR:
                raise RebaseHelperError('Execution of %s failed.\nCommand line is: %s' % (cls.CMD, cmd))
            if int(ret_code) == 0:
                text = 'ABI of the compared binaries in package %s are equal.' % old_name
            else:
                text = 'ABI of the compared binaries in package %s are not equal.' % old_name
            reports[output] = text
        return reports
