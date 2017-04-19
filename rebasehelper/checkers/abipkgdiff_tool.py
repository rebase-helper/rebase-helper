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
import re

from rebasehelper.utils import ProcessHelper
from rebasehelper.logger import logger
from rebasehelper.exceptions import RebaseHelperError, CheckerNotFoundError
from rebasehelper.results_store import results_store
from rebasehelper import settings
from rebasehelper.checker import BaseChecker


class AbiCheckerTool(BaseChecker):
    """ Pkgdiff compare tool. """

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
    def run_check(cls, result_dir):
        """Compares old and new RPMs using pkgdiff"""
        debug_old, rest_pkgs_old = cls._get_packages_for_abipkgdiff(results_store.get_build('old'))
        debug_new, rest_pkgs_new = cls._get_packages_for_abipkgdiff(results_store.get_build('new'))
        cmd = [cls.CMD]
        if debug_old is None:
            logger.warning("Package doesn't contain any debug package")
            return None
        try:
            cmd.append('--d1')
            cmd.append(debug_old[0])
        except IndexError:
            logger.error('Debuginfo package not found for old package.')
            return None
        try:
            cmd.append('--d2')
            cmd.append(debug_new[0])
        except IndexError:
            logger.error('Debuginfo package not found for new package.')
            return None
        reports = {}
        for pkg in rest_pkgs_old:
            command = list(cmd)
            # Package can be <letters><numbers>-<letters>-<and_whatever>
            regexp = r'^(\w*)(-\D+)?.*$'
            reg = re.compile(regexp)
            matched = reg.search(os.path.basename(pkg))
            if matched:
                file_name = matched.group(1)
                command.append(pkg)
                find = [x for x in rest_pkgs_new if os.path.basename(x).startswith(file_name)]
                command.append(find[0])
                package_name = os.path.basename(os.path.basename(pkg))
                logger.debug('Package name for ABI comparision %s', package_name)
                regexp_name = r'(\w-)*(\D+)*'
                reg_name = re.compile(regexp_name)
                matched = reg_name.search(os.path.basename(pkg))
                logger.debug('Found matches %s', matched.groups())
                if matched:
                    package_name = matched.group(0) + cls.log_name
                else:
                    package_name = package_name + '-' + cls.log_name
                output = os.path.join(cls.results_dir, result_dir, package_name)
                try:
                    ret_code = ProcessHelper.run_subprocess(command, output=output)
                except OSError:
                    raise CheckerNotFoundError("Checker '%s' was not found or installed." % cls.CMD)

                if int(ret_code) & settings.ABIDIFF_ERROR and int(ret_code) & settings.ABIDIFF_USAGE_ERROR:
                    raise RebaseHelperError('Execution of %s failed.\nCommand line is: %s' % (cls.CMD, cmd))
                if int(ret_code) == 0:
                    text = 'ABI of the compared binaries in package %s are equal.' % package_name
                else:
                    text = 'ABI of the compared binaries in package %s are not equal.' % package_name
                reports[output] = text
            else:
                logger.debug("Rebase-helper did not find a package name in '%s'", package_name)
        return reports
