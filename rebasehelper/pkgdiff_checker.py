# -*- coding: utf-8 -*-

# This tool helps you to rebase package to the latest version
# Copyright (C) 2013 Petr Hracek
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

import os

from rebasehelper.base_checker import BaseChecker, register_check_tool
from rebasehelper.utils import ProcessHelper
from rebasehelper.logger import logger
from rebasehelper.utils import write_to_file
from rebasehelper import settings


@register_check_tool
class PkgDiffTool(BaseChecker):
    """ Pkgdiff compare tool. """
    CMD = "pkgdiff"
    pkg_diff_result_path = os.path.join(settings.REBASE_HELPER_PREFIX+settings.REBASE_RESULTS_DIR,
                                        "pkgdiff_reports")

    @classmethod
    def match(cls, cmd=None):
        if cmd == cls.CMD:
            return True
        else:
            return False

    @classmethod
    def _create_xml(cls, name, input_structure={}):
        file_name = name + ".xml"
        tags = {'version': input_structure.get('version', ""),
                'group': input_structure.get('name', ''),
                'packages': input_structure.get('rpm', [])}
        lines = []
        for key, value in tags.items():
            new_value = value if isinstance(value, str) else '\n'.join(value)
            lines.append('<{0}>\n{1}\n</{0}>\n'.format(key, new_value))
        write_to_file(file_name, "w", lines)
        return file_name

    @classmethod
    def run_check(cls, *args, **kwargs):
        """ Compares  old and new RPMs using pkgdiff """
        versions = ['old', 'new']
        cmd = [cls.CMD]
        for version in versions:
            old = kwargs.get(version, None)
            if old:
                file_name = cls._create_xml(version, input_structure=old)
                cmd.append(file_name)
        cmd.append('-report-path')
        cmd.append(cls.pkg_diff_result_path)
        # TODO Should we return a value??
        ProcessHelper.run_subprocess(cmd)
        pkginfo = {}
        pkginfo['pkgcompareinfo'] = cls.pkg_diff_result_path
        kwargs.update(pkginfo)

