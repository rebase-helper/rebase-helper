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
from typing import Optional, cast

import rpm  # type: ignore

from rebasehelper.logger import CustomLogger
from rebasehelper.results_store import results_store
from rebasehelper.plugins.checkers import BaseChecker, CheckerCategory
from rebasehelper.helpers.rpm_helper import RpmHelper


logger: CustomLogger = cast(CustomLogger, logging.getLogger(__name__))


class SonameCheck(BaseChecker):

    DEFAULT: bool = True
    CATEGORY: Optional[CheckerCategory] = CheckerCategory.RPM
    results_dir: Optional[str] = ''

    @classmethod
    def is_available(cls):
        return True

    @classmethod
    def _get_soname(cls, header: rpm.hdr) -> Optional[str]:
        soname_re = re.compile(r'(?P<soname>[^()]+\.so[^()]+)\(.*\)(\(64bit\))?')
        for provides in header.provides:
            match = soname_re.match(RpmHelper.decode(provides))
            if match:
                return match.group('soname')
        return None

    @classmethod
    def run_check(cls, results_dir, **kwargs):
        cls.results_dir = os.path.join(results_dir, cls.name)
        os.makedirs(cls.results_dir)

        old_headers = [RpmHelper.get_header_from_rpm(x) for x in results_store.get_old_build().get('rpm', [])]
        new_headers = [RpmHelper.get_header_from_rpm(x) for x in results_store.get_new_build().get('rpm', [])]
        soname_changes = {}
        for old in old_headers:
            name = RpmHelper.decode(old.name)
            new = [x for x in new_headers if RpmHelper.decode(x.name) == name]
            if not new:
                logger.warning('New version of package %s was not found!', name)
                continue
            old_soname = cls._get_soname(old)
            new_soname = cls._get_soname(new[0])
            if not old_soname:
                continue
            if old_soname == new_soname:
                msg = 'No SONAME changes detected'
            else:
                msg = 'SONAME changed from {} to {}'.format(old_soname, new_soname)
                soname_changes[name] = {'from': old_soname, 'to': new_soname}
            with open(os.path.join(cls.results_dir, name + '.txt'), 'w') as outfile:
                outfile.write(msg)

        return dict(soname_changes=soname_changes,
                    path=cls.get_checker_output_dir_short())

    @classmethod
    def format(cls, data):
        output_lines = [cls.get_underlined_title('sonamecheck')]
        if not data['soname_changes']:
            output_lines.append('No SONAME changes occurred.')
            return output_lines
        for pkg, changes in data['soname_changes'].items():
            output_lines.append('{}: SONAME changed from {} to {}'.format(pkg, changes['from'], changes['to']))
        return output_lines

    @classmethod
    def get_important_changes(cls, checker_output):
        if checker_output['soname_changes']:
            return ['SONAME changes occurred. Check sonamecheck output.']
