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

from typing import Dict, Optional

from rebasehelper.helpers.process_helper import ProcessHelper
from rebasehelper.plugins.checkers import BaseChecker, CheckerCategory


class LicenseCheck(BaseChecker):
    """license compare tool

    Attributes:
        license_changes(bool): Boolean value to inform whether any license change occured.
        license_files_changes(dict): Dictionary of {license: change_type + file_name} pairs.
    """

    DEFAULT: bool = True
    CATEGORY: Optional[CheckerCategory] = CheckerCategory.SOURCE

    CMD: str = 'licensecheck'
    license_changes: bool = False
    license_files_changes: Dict[str, str] = {}

    @classmethod
    def is_available(cls):
        try:
            return ProcessHelper.run_subprocess([cls.CMD, '--help'], output_file=ProcessHelper.DEV_NULL) == 0
        except (IOError, OSError):
            return False

    @classmethod
    def get_license_changes(cls, old_dir, new_dir):
        """
        Finds differences in licenses between old and new source files.

        Args:
            old_dir(str): Path to the old sources directory.
            new_dir(str): Path to the new sources directory.

        Returns:
            tuple: Changes dictionary, new_licenses set, disappeared_licenses set.
        """
        diffs = []
        possible_license_names = r'COPYING|LICENSE|LICENCE|LICENSING|BSD|(L)?GPL(v[23][+]?)?'
        for source_dir in [old_dir, new_dir]:
            out = io.StringIO()
            ProcessHelper.run_subprocess(["/usr/bin/licensecheck", source_dir, "--machine", "--recursive"],
                                         output_file=out, ignore_stderr=True)
            diff = {}
            for l in out:
                # licensecheck output format: 'Filepath\tlicense'
                file_path, dlicense = l.split('\t')
                if 'GENERATED FILE' in dlicense:
                    continue
                file_path = os.path.relpath(file_path, source_dir)
                diff[file_path] = dlicense.strip()
            diffs.append(diff)

        old_lics, new_lics = set(), set()
        changes = {'appeared': {}, 'transitioned': {}, 'disappeared': {}}
        # Get changed licenses in existing files
        for new_file, new_license in diffs[1].items():
            new_lics.add(new_license)
            for old_file, old_license in diffs[0].items():
                old_lics.add(old_license)

                if (new_file == old_file and
                   (new_license != old_license)):
                    new_key = '{} => {}'.format(old_license, new_license)
                    if new_license == 'UNKNOWN':
                        # Conversion `known license` => `None/Unknown`
                        if re.search(possible_license_names, new_file, re.IGNORECASE):
                            cls.license_files_changes.update({old_license: 'disappeared in {}'.format(new_file)})
                        if old_license not in changes['disappeared']:
                            changes['disappeared'][old_license] = []
                        changes['disappeared'][old_license].append(new_file)
                    elif old_license == 'UNKNOWN':
                        # Conversion `None/Unknown` => `known license`
                        if re.search(possible_license_names, new_file, re.IGNORECASE):
                            cls.license_files_changes.update({new_license: 'appeared in {}'.format(new_file)})
                        if new_license not in changes['appeared']:
                            changes['appeared'][new_license] = []
                        changes['appeared'][new_license].append(new_file)
                    else:
                        # Conversion `known license` => `known license`
                        if re.search(possible_license_names, new_file, re.IGNORECASE):
                            cls.license_files_changes.update({new_key: 'in {}'.format(new_file)})
                        if new_key not in changes['transitioned']:
                            changes['transitioned'][new_key] = []
                        if new_file not in changes['transitioned'][new_key]:
                            changes['transitioned'][new_key].append(new_file)

        # Get newly appeared files
        for new_file, new_license in diffs[1].items():
            if new_file not in diffs[0]:
                if new_license == 'UNKNOWN':
                    continue
                if re.search(possible_license_names, new_file, re.IGNORECASE):
                    cls.license_files_changes.update({new_license: 'appeared in {}'.format(new_file)})
                if new_license not in changes['appeared']:
                    changes['appeared'][new_license] = []
                changes['appeared'][new_license].append(new_file)

        # Get removed files
        for old_file, old_license in diffs[0].items():
            if old_file not in diffs[1]:
                if old_license == 'UNKNOWN':
                    continue
                if re.search(possible_license_names, old_file, re.IGNORECASE):
                    cls.license_files_changes.update({old_license: 'disappeared in {}'.format(old_file)})
                if old_license not in changes['disappeared']:
                    changes['disappeared'][old_license] = []
                changes['disappeared'][old_license].append(old_file)

        new_licenses = new_lics - old_lics
        disappeared_licenses = old_lics - new_lics
        if new_licenses or disappeared_licenses:
            cls.license_changes = True

        return changes, list(new_licenses), list(disappeared_licenses)

    @classmethod
    def run_check(cls, results_dir, **kwargs):
        cls.license_changes = False
        cls.license_files_changes = dict()
        cls.results_dir = os.path.join(results_dir, 'licensecheck')
        os.makedirs(cls.results_dir)
        changes, new_licenses, disappeared_licenses = cls.get_license_changes(kwargs['old_dir'], kwargs['new_dir'])
        cls.output_to_report_file(changes, os.path.join(cls.results_dir, 'report.txt'))

        return {'path': cls.get_checker_output_dir_short(), 'changes': changes,
                'license_changes': cls.license_changes, 'new_licenses': new_licenses,
                'disappeared_licenses': disappeared_licenses, 'license_files_changes': cls.license_files_changes}

    @classmethod
    def output_to_report_file(cls, changes, report_file_path):
        """
        Prints the licensecheck output to a report file.

        Args:
            changes(dict): Changes dictionary produced by licensecheck_tool.
            report_file_path(str): Path for the report file.
        """
        output_string = [cls.get_underlined_title("licensecheck").lstrip()]
        if cls.license_changes:
            output_string.append('License changes occured!')
            for change_name, change_info in sorted(changes.items()):
                if not change_info:
                    continue
                output_string.append(cls.get_underlined_title('The following license(s) {}'.format(change_name)))
                for license_name, files in sorted(change_info.items()):
                    output_string.append('* {}'.format(license_name))
                    for f in sorted(files):
                        output_string.append(' - {}'.format(f))
        else:
            output_string.append('No license changes detected.')

        with open(report_file_path, 'w') as f:
            f.write('\n'.join(output_string))

    @classmethod
    def format(cls, data):
        output_string = [cls.get_underlined_title("licensecheck")]

        if data['license_changes']:
            if data['license_files_changes']:
                output_string.append('Major license changes:')
                for license_change, change_type in cls.license_files_changes.items():
                    output_string.append(' - {} {}'.format(license_change, change_type))
                    # Remove already mentioned transition to avoid duplicity in the report
                    if license_change in data['new_licenses']:
                        data['new_licenses'].remove(license_change)
                    if license_change in data['disappeared_licenses']:
                        data['disappeared_licenses'].remove(license_change)

            output_string.append('Other license changes:')
            for l in sorted(data['new_licenses']):
                output_string.append(' - {} appeared'.format(l))
            for l in sorted(data['disappeared_licenses']):
                output_string.append(' - {} disappeared'.format(l))

            output_string.append('Details in {}:'.format(data['path']))
            output_string.append(' - {}'.format('report.txt'))
        else:
            output_string.append('No license changes detected.')

        return output_string

    @classmethod
    def get_important_changes(cls, checker_output):
        if LicenseCheck.license_changes:
            return ['License changes occured. Check licensecheck output.']
        return []
