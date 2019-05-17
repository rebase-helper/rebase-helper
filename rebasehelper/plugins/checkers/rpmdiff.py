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
import re

from typing import List, Optional

from rebasehelper.logger import logger
from rebasehelper.exceptions import RebaseHelperError, CheckerNotFoundError
from rebasehelper.results_store import results_store
from rebasehelper.plugins.checkers import BaseChecker, CheckerCategory
from rebasehelper.helpers.process_helper import ProcessHelper
from rebasehelper.helpers.rpm_helper import RpmHelper


class RpmDiff(BaseChecker):
    """rpmdiff compare tool"""

    DEFAULT: bool = True
    CATEGORY: Optional[CheckerCategory] = CheckerCategory.RPM

    CMD: str = 'rpmdiff'
    CHECKER_TAGS: List[str] = ['added', 'removed', 'changed', 'moved', 'renamed']

    @classmethod
    def is_available(cls):
        try:
            return ProcessHelper.run_subprocess([cls.CMD, '--help'], output_file=ProcessHelper.DEV_NULL) == 0
        except (IOError, OSError):
            return False

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
            logger.verbose(fields)
            if line.startswith('removed'):
                results_dict['removed'].append(fields[1])
                continue
            if line.startswith('added'):
                results_dict['added'].append(fields[1])
                continue

            if re.match(r'(S..|..5)........', fields[0]):
                # size or checksum changed
                results_dict['changed'].append(fields[1])
        return results_dict

    @classmethod
    def update_added_removed(cls, results_dict):
        added = []
        removed = []
        for item in results_dict['removed']:
            found = [x for x in results_dict['added'] if os.path.basename(item) == os.path.basename(x)]
            if not found:
                removed.append(item)

        for item in results_dict['added']:
            found = [x for x in results_dict['removed'] if os.path.basename(item) == os.path.basename(x)]
            if not found:
                added.append(item)
        results_dict['added'] = added
        results_dict['removed'] = removed
        return results_dict

    @classmethod
    def run_check(cls, results_dir, **kwargs):
        """Compares old and new RPMs using rpmdiff"""
        results_dict = {}

        for tag in cls.CHECKER_TAGS:
            results_dict[tag] = []

        cls.results_dir = os.path.join(results_dir, cls.name)
        os.makedirs(cls.results_dir)

        # Only S (size), M(mode) and 5 (checksum) are now important
        not_catched_flags = ['T', 'F', 'G', 'U', 'V', 'L', 'D', 'N']
        old_pkgs = cls._get_rpms(results_store.get_old_build().get('rpm', None))
        new_pkgs = cls._get_rpms(results_store.get_new_build().get('rpm', None))
        for key, value in old_pkgs.items():
            if 'debuginfo' in key or 'debugsource' in key:
                # skip debug{info,source} packages
                continue
            cmd = [cls.CMD]
            # TODO modify to online command
            for x in not_catched_flags:
                cmd.extend(['-i', x])
            cmd.append(value)
            # We would like to build correct old package against correct new packages
            try:
                cmd.append(new_pkgs[key])
            except KeyError:
                logger.warning('New version of package %s was not found!', key)
                continue
            output = io.StringIO()
            try:
                ProcessHelper.run_subprocess(cmd, output_file=output)
            except OSError:
                raise CheckerNotFoundError("Checker '{}' was not found or installed.".format(cls.name))
            results_dict = cls._analyze_logs(output, results_dict)
        results_dict = cls.update_added_removed(results_dict)
        cls.results_dict = {k: v for k, v in results_dict.items() if v}
        lines = []
        for key, val in results_dict.items():
            if val:
                if lines:
                    lines.append('')
                lines.append('Following files were {}:'.format(key))
                lines.extend(val)

        rpmdiff_report = os.path.join(cls.results_dir, 'report.txt')

        counts = {k: len(v) for k, v in results_dict.items()}

        try:
            with open(rpmdiff_report, "w") as f:
                f.write('\n'.join(lines))
        except IOError:
            raise RebaseHelperError("Unable to write result from {} to '{}'".format(cls.name, rpmdiff_report))

        return {'path': cls.get_checker_output_dir_short(), 'files_changes': counts}

    @classmethod
    def format(cls, data):
        """
        Format rpmdiff output for outputtool
        :param data: rpmdiff output data dictionary
        :return: formated rpmdiff output list of strings
        """
        output_lines = [cls.get_underlined_title("rpmdiff")]

        output_lines.append(" - {} added files".format(data['files_changes']['added']))
        output_lines.append(" - {} changed files".format(data['files_changes']['changed']))
        output_lines.append(" - {} removed files".format(data['files_changes']['removed']))

        output_lines.append("Details in {}:".format(data['path']))
        output_lines.append(" - report.txt")

        return output_lines
