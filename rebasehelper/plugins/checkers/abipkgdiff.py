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

import logging
import os
import re
from typing import Dict, Optional, cast

from rebasehelper.constants import ENCODING
from rebasehelper.exceptions import RebaseHelperError, CheckerNotFoundError
from rebasehelper.logger import CustomLogger
from rebasehelper.results_store import results_store
from rebasehelper.plugins.checkers import BaseChecker, CheckerCategory
from rebasehelper.helpers.process_helper import ProcessHelper
from rebasehelper.helpers.rpm_helper import RpmHelper


logger: CustomLogger = cast(CustomLogger, logging.getLogger(__name__))

AbiChange = Dict[str, Dict[str, Dict[str, str]]]


class AbiPkgDiff(BaseChecker):
    """abipkgdiff compare tool."""

    DEFAULT: bool = True
    CATEGORY: Optional[CheckerCategory] = CheckerCategory.RPM
    results_dir: Optional[str] = ''

    CMD: str = 'abipkgdiff'
    ABIDIFF_ERROR: int = 1 << 0
    ABIDIFF_USAGE_ERROR: int = 1 << 1
    ABIDIFF_ABI_CHANGE: int = 1 << 2
    ABIDIFF_ABI_INCOMPATIBLE_CHANGE: int = 1 << 3

    @classmethod
    def is_available(cls):
        try:
            return ProcessHelper.run_subprocess([cls.CMD, '--help'], output_file=ProcessHelper.DEV_NULL) == 3
        except (IOError, OSError):
            return False

    # Example
    # abipkgdiff --d1 dbus-glib-debuginfo-0.80-3.fc12.x86_64.rpm \
    # --d2 dbus-glib-debuginfo-0.104-3.fc23.x86_64.rpm \
    # dbus-glib-0.80-3.fc12.x86_64.rpm dbus-glib-0.104-3.fc23.x86_64.rpm
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
        srpm = RpmHelper.get_header_from_rpm(pkg).sourcerpm
        debuginfo = '{}-debuginfo'.format(RpmHelper.split_nevra(srpm)['name'])
        find = [x for x in debug if RpmHelper.split_nevra(os.path.basename(x))['name'] == debuginfo]
        if find:
            return find[0]
        return None

    @classmethod
    def run_check(cls, results_dir, **kwargs):
        """Compares old and new RPMs using abipkgdiff"""
        # Check if ABI changes occured
        cls.results_dir = os.path.join(results_dir, cls.name)
        cls.prepare_results_dir()
        debug_old, rest_pkgs_old = cls._get_packages_for_abipkgdiff(results_store.get_build('old'))
        debug_new, rest_pkgs_new = cls._get_packages_for_abipkgdiff(results_store.get_build('new'))
        ret_codes = {}
        for pkg in rest_pkgs_old:
            command = [cls.CMD]
            command_fallback = [cls.CMD]
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
            command.extend([pkg, new_pkg])
            command_fallback.extend([pkg, new_pkg])
            logger.verbose('Package name for ABI comparison %s', old_name)
            output = os.path.join(cls.results_dir, old_name + '.txt')
            for cmd in [command, command_fallback]:
                try:
                    ret_code = ProcessHelper.run_subprocess(cmd, output_file=output)
                except OSError as e:
                    raise CheckerNotFoundError("Checker '{}' was not found or installed.".format(cls.name)) from e
                if int(ret_code) & cls.ABIDIFF_ERROR and int(ret_code) & cls.ABIDIFF_USAGE_ERROR:
                    raise RebaseHelperError(
                        'Execution of {} failed.\nCommand line is: {}'.format(cls.CMD, ' '.join(cmd)))
                if int(ret_code) & cls.ABIDIFF_ERROR:
                    # abipkgdiff might not be able to read the debuginfo, try again without it
                    continue
                break
            ret_codes[old_name] = int(ret_code)
        return dict(packages=cls.parse_abi_logs(ret_codes),
                    abi_changes=any(x & cls.ABIDIFF_ABI_CHANGE for x in ret_codes.values()),
                    abi_incompatible_changes=any(x & cls.ABIDIFF_ABI_INCOMPATIBLE_CHANGE for x in ret_codes.values()),
                    path=cls.get_checker_output_dir_short(),
                    ret_codes=ret_codes)

    @classmethod
    def parse_abi_logs(cls, ret_codes):
        """Parses summary information from abipkgdiff logs.

        Args:
            ret_codes(dict): Dictionary mapping package names to abipkgdiff return codes.

        Returns:
            dict: Dictionary mapping package names to a dict of summary information for each shared object.

            For example:

            {
                'libtiff':
                {
                   'libtiff.so.5.2.5':{
                        'Functions changes summary': {
                            'Added': {
                                'count': '8',
                                'what': 'Added',
                                'filtered_out': None,
                            },
                        },
                        'Variables changes summary': {},
                    },
                },
            }
        """
        def parse_changes(lines):
            title_re = re.compile(r"^\s*=+\s*changes\s+of\s+'(?P<filename>.+)'.*$")
            summary_re = re.compile(r'''^
            \s+(?P<kind>[\w\s]+changes\s+summary):\s+
            (?P<changes>.+)
            $
            ''', re.VERBOSE)
            changes_re = re.compile(r'''
            (?P<count>\d+)\s+
            (?P<what>Added|Changed|Removed)(\s+functions|variables)?
            (\s+\((?P<filtered_out>\d+)\s+filtered\s+out\))?
            ''', re.VERBOSE)
            result_dict: Dict[str, AbiChange] = {}
            filename = 'Undetected filename'
            for line in lines:
                mt = title_re.match(line)
                if mt:
                    filename = mt.group('filename')
                    if filename not in result_dict:
                        result_dict[filename] = {}
                ms = summary_re.match(line)
                if ms:
                    result: AbiChange = {}
                    ds = ms.groupdict()
                    result[ds['kind']] = {}
                    for mc in changes_re.finditer(ds['changes']):
                        dc = mc.groupdict()
                        dc['count'] = int(dc['count'])
                        if int(dc['count']) or dc['filtered_out']:
                            result[ds['kind']][dc['what']] = dc

                    result_dict[filename].update(result)
            return result_dict

        pkgs = {}
        for pkg, ret_code in ret_codes.items():
            if ret_code & cls.ABIDIFF_ABI_CHANGE:
                with open(os.path.join(cls.results_dir, pkg + '.txt'), 'r', encoding=ENCODING) as f:
                    pkgs[pkg] = parse_changes(f.readlines())
        return pkgs

    @classmethod
    def format(cls, data):
        output_lines = [cls.get_underlined_title('abipkgdiff')]
        if not cls.get_important_changes(data):
            output_lines.append('No ABI changes occured.')
            return output_lines
        for pkg_name, pkg_changes in sorted(data['packages'].items()):
            if not pkg_changes:
                continue
            output_lines.append("ABI changes in {}:".format(pkg_name))
            for filename, file_changes in pkg_changes.items():
                output_lines.append(" - {}:".format(filename))
                for sum_title, changes_list in sorted(file_changes.items()):
                    if not changes_list:
                        continue
                    output_lines.append("   - {}:".format(sum_title))

                    for change_name, change_info in sorted(changes_list.items()):
                        if change_info['filtered_out']:
                            output_lines.append("     - {} {} (filtered out {})".format(change_name,
                                                                                        change_info['count'],
                                                                                        change_info['filtered_out']))
                        else:
                            output_lines.append("     - {} {}".format(change_name, change_info['count']))
        output_lines.append("Details in {}:".format(data['path']))
        for pkg_name, pkg_changes in sorted(data['packages'].items()):
            output_lines.append(" - {}.txt".format(pkg_name))

        return output_lines

    @classmethod
    def get_important_changes(cls, checker_output):
        if checker_output['abi_incompatible_changes']:
            return ['Incompatible ABI changes occurred. Check abipkgdiff output.']
        if checker_output['abi_changes']:
            return ['ABI changes occurred. Check abipkgdiff output.']
        return []
