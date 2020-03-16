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

import collections
import logging
import os
import re
from typing import Dict, List, Optional, Set, Union, cast

from rebasehelper.logger import CustomLogger
from rebasehelper.results_store import results_store
from rebasehelper.plugins.checkers import BaseChecker, CheckerCategory
from rebasehelper.helpers.rpm_helper import RpmHelper


logger: CustomLogger = cast(CustomLogger, logging.getLogger(__name__))

SonameChanges = Dict[str, Dict[str, List[Union[str, Dict[str, str]]]]]


class SonameCheck(BaseChecker):

    DEFAULT: bool = True
    CATEGORY: Optional[CheckerCategory] = CheckerCategory.RPM

    @classmethod
    def is_available(cls):
        return True

    @classmethod
    def _get_sonames(cls, provides: List[str]) -> Set[str]:
        soname_re = re.compile(r'(?P<soname>[^()]+\.so[^()]+)\(.*\)(\(64bit\))?')
        sonames = set()
        for p in provides:
            match = soname_re.match(p)
            if match:
                sonames.add(match.group('soname'))
        return sonames

    @classmethod
    def run_check(cls, results_dir, **kwargs):
        old_headers = [RpmHelper.get_header_from_rpm(x) for x in results_store.get_old_build().get('rpm', [])]
        new_headers = [RpmHelper.get_header_from_rpm(x) for x in results_store.get_new_build().get('rpm', [])]
        soname_changes: SonameChanges = collections.defaultdict(lambda: collections.defaultdict(list))
        for old in old_headers:
            new = [x for x in new_headers if x.name == old.name]
            if not new:
                logger.warning('New version of package %s was not found!', old.name)
                continue
            else:
                new = new[0]
            old_sonames = cls._get_sonames(old.provides)
            new_sonames = cls._get_sonames(new.provides)
            for old_soname in old_sonames:
                if old_soname in new_sonames:
                    new_sonames.remove(old_soname)
                    continue
                soname = [x for x in new_sonames if os.path.splitext(x)[0] == os.path.splitext(old_soname)[0]]
                if not soname:
                    soname_changes[old.name]['removed'].append(old_soname)
                else:
                    soname_changes[old.name]['changed'].append({'from': old_soname, 'to': soname[0]})
                    new_sonames.remove(soname[0])

            if new_sonames:
                soname_changes[old.name]['added'] = list(new_sonames)

        return dict(soname_changes=soname_changes)

    @classmethod
    def format(cls, data):
        output_lines = [cls.get_underlined_title('sonamecheck')]
        if not data['soname_changes']:
            output_lines.append('No SONAME changes occurred.')
            return output_lines
        for package, package_changes in data['soname_changes'].items():
            output_lines.append(package)
            for change_type, changes in package_changes.items():
                output_lines.append(' - {}'.format(change_type))
                for change in changes:
                    if change_type == 'changed':
                        output_lines.append('\t- from {} to {}'.format(change['from'], change['to']))
                    else:
                        output_lines.append('\t - {}'.format(change))

        return output_lines

    @classmethod
    def get_important_changes(cls, checker_output):
        if checker_output['soname_changes']:
            return ['SONAME changes occurred. Check sonamecheck output in the report.']
        return []
