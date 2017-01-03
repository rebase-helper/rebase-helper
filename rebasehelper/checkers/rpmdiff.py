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
import six
import re
from six import StringIO

from rebasehelper.utils import ProcessHelper, RpmHelper
from rebasehelper.logger import logger
from rebasehelper.exceptions import RebaseHelperError, CheckerNotFoundError
from rebasehelper.results_store import results_store
from rebasehelper import settings
from rebasehelper.checker import BaseChecker


class RpmDiffTool(BaseChecker):
    """ RpmDiff compare tool."""
    CMD = "rpmdiff"
    DEFAULT = True

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
    def _get_rpms(cls, rpm_list):
        rpm_dict = {}
        for rpm_name in rpm_list:
            rpm_dict[RpmHelper.get_info_from_rpm(rpm_name, 'name')] = rpm_name
        return rpm_dict

    @classmethod
    def _unpack_rpm(cls, rpm_name):
        pass

    @classmethod
    def _analyze_logs(cls, output, results_dict):
        removed_things = ['.build-id', '.dwz', 'PROVIDE', 'REQUIRES']
        for line in output:
            if [x for x in removed_things if x in line]:
                continue

            fields = line.strip().split()
            logger.debug(fields)
            if 'removed' in line:
                results_dict['removed'].append(fields[1])
                continue
            if 'added' in line:
                results_dict['added'].append(fields[1])
                continue
            #'S.5........' for regexp
            regexp = '(S)+\.(5)+\.\.\.\.\.\.\.\.'
            match = re.search(regexp, fields[0])
            if match:
                results_dict['changed'].append(fields[1])
        return results_dict

    @classmethod
    def update_added_removed(cls, results_dict):
        added = []
        removed = []
        for item in results_dict['removed']:
            found = [x for x in results_dict['added'] if os.path.basename(item) in x]
            if not found:
                removed.append(item)

        for item in results_dict['added']:
            found = [x for x in results_dict['removed'] if os.path.basename(item) in x]
            if not found:
                removed.append(item)
        results_dict['added'] = added
        results_dict['removed'] = removed
        return results_dict

    @classmethod
    def run_check(cls, results_dir):
        """Compares old and new RPMs using rpmdiff"""
        results_dict = {}

        for tag in settings.CHECKER_TAGS:
            results_dict[tag] = []
        cls.results_dir = results_dir

        # Only S (size), M(mode) and 5 (checksum) are now important
        not_catched_flags = ['T', 'F', 'G', 'U', 'V', 'L', 'D', 'N']
        old_pkgs = cls._get_rpms(results_store.get_old_build().get('rpm', None))
        new_pkgs = cls._get_rpms(results_store.get_new_build().get('rpm', None))
        for key, value in six.iteritems(old_pkgs):
            cmd = [cls.CMD]
            # TODO modify to online command
            for x in not_catched_flags:
                cmd.extend(['-i', x])
            cmd.append(value)
            # We would like to build correct old package against correct new packages
            cmd.append(new_pkgs[key])
            output = StringIO()
            try:
                ProcessHelper.run_subprocess(cmd, output=output)
            except OSError:
                raise CheckerNotFoundError("Checker '%s' was not found or installed." % cls.CMD)
            results_dict = cls._analyze_logs(output, results_dict)

        results_dict = cls.update_added_removed(results_dict)
        results_dict = dict((k, v) for k, v in six.iteritems(results_dict) if v)
        lines = []
        for key, val in six.iteritems(results_dict):
            if val:
                if lines:
                    lines.append('')
                lines.append('Following files were %s:' % key)
                lines.extend(val)

        rpmdiff_report = os.path.join(cls.results_dir, 'report-' + cls.CMD + '.log')
        try:
            with open(rpmdiff_report, "w") as f:
                f.write('\n'.join(lines))
        except IOError:
            raise RebaseHelperError("Unable to write result from %s to '%s'" % (cls.CMD, rpmdiff_report))

        return {rpmdiff_report: None}
