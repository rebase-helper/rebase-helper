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

import os
import json

from typing import Any, Dict, Tuple

from rebasehelper.constants import ENCODING
from rebasehelper.exceptions import CheckerNotFoundError, RebaseHelperError
from rebasehelper.helpers.rpm_helper import RpmHelper
from rebasehelper.helpers.process_helper import ProcessHelper
from rebasehelper.plugins.checkers import BaseChecker


class Rpminspect(BaseChecker):  # pylint: disable=abstract-method
    """An abstract class representing rpminspect checker (either RPM or SRPM).

    For both types of checkers the data stored in results_store
    looks as follows:

    {
        'checks': {
            'package1': {
                'BAD': 5,
                'VERIFY': 3,
                'OK': 1,
                'INFO': 1
            },
            'package2': {
                'BAD': 1,
                'VERIFY': 3,
                'OK': 5,
                'INFO': 1
            }
        },
        'path': rebase-helper-results/checkers/rpminspect,
        'files': [
            'package1.json',
            'package2.json'
        ]
    }
    """
    DEFAULT: bool = True

    CMD: str = 'rpminspect-fedora'

    BAD_CHECK: str = 'BAD'
    VERIFY_CHECK: str = 'VERIFY'
    OK_CHECK: str = 'OK'
    INFO_CHECK: str = 'INFO'
    POSSIBLE_CHECK_RESULTS = (BAD_CHECK, VERIFY_CHECK, OK_CHECK, INFO_CHECK)

    @classmethod
    def is_available(cls):
        try:
            return ProcessHelper.run_subprocess([cls.CMD, '--help'], output_file=ProcessHelper.DEV_NULL) == 0
        except (IOError, OSError):
            return False

    @classmethod
    def format(cls, data):
        output_lines = [cls.get_underlined_title(cls.name)]

        for package, package_data in data['checks'].items():
            output_lines.append(' - {}:'.format(package))
            for check in cls.POSSIBLE_CHECK_RESULTS:
                output_lines.append('\t- {} {} checks'.format(package_data[check], check))

        output_lines.append('Details in {}:'.format(data['path']))
        for file in data['files']:
            output_lines.append(' - {}'.format(file))
        return output_lines

    @classmethod
    def get_important_changes(cls, checker_output):
        if any(data[cls.BAD_CHECK] > 0 for data in checker_output['checks'].values()):
            return ['{} checks found in {} output. Check rpminspect output.'.format(cls.BAD_CHECK, cls.name)]
        return []

    @classmethod
    def process_data(cls, data: Dict[str, Any]) -> Dict[str, int]:
        result = {check: 0 for check in cls.POSSIBLE_CHECK_RESULTS}
        for check_data in data.values():
            for check_dict in check_data:
                status = check_dict['result']
                result[status] += 1
        return result

    @classmethod
    def run_rpminspect(cls, checker_dir: str, old_pkg: str, new_pkg: str) -> Tuple[str, Dict[str, int]]:
        """Runs rpminspect on the given package.

        Args:
            checker_dir: Path to the results directory of the checker
            old_pkg: Path to the old package.
            new_pkg: Path to the new package.

        Returns:
            Tuple of (path, data), where path is the path to rpminspect output
            and data is the dict of count of OK/BAD/VERIFY checks.

        """
        cmd = [cls.CMD, '-F', 'json']
        pkg_name = RpmHelper.split_nevra(os.path.basename(new_pkg))['name']
        cmd.append(old_pkg)
        cmd.append(new_pkg)

        outfile = os.path.join(checker_dir, '{}.json'.format(pkg_name))
        try:
            ret = ProcessHelper.run_subprocess(cmd, output_file=outfile, ignore_stderr=True)
        except OSError as e:
            raise CheckerNotFoundError('Checker \'{}\' was not found or installed.'.format(cls.name)) from e

        # Exit code 1 is used when bad check is found, 0 when everything is OK. Others on error
        if ret not in (0, 1):
            raise RebaseHelperError('An error occurred when running checker \'{}\''.format(cls.name))

        with open(outfile, 'r', encoding=ENCODING) as json_file:
            data = json.load(json_file)

        return outfile, cls.process_data(data)
