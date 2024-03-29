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

from typing import Optional, cast

from specfile.utils import NEVR

from rebasehelper.logger import CustomLogger
from rebasehelper.results_store import results_store
from rebasehelper.plugins.checkers import CheckerCategory
from rebasehelper.plugins.checkers.rpminspect import Rpminspect


logger: CustomLogger = cast(CustomLogger, logging.getLogger(__name__))


class RpminspectSrpm(Rpminspect):
    """SRPM rpminspect checker."""

    CATEGORY: Optional[CheckerCategory] = CheckerCategory.SRPM

    @classmethod
    def run_check(cls, results_dir, **kwargs):
        cls.results_dir = os.path.join(results_dir, 'rpminspect-srpm')
        cls.prepare_results_dir()

        result = {'path': cls.get_checker_output_dir_short(), 'files': [], 'checks': {}}
        old_pkg = results_store.get_old_build()['srpm']
        new_pkg = results_store.get_new_build()['srpm']
        name = NEVR.from_string(os.path.basename(old_pkg)).name
        outfile, pkg_data = cls.run_rpminspect(cls.results_dir, old_pkg, new_pkg)
        result['files'].append(os.path.basename(outfile))
        result['checks'][name] = pkg_data

        return result
