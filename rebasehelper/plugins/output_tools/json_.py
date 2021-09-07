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

import json

from rebasehelper.constants import ENCODING
from rebasehelper.plugins.output_tools import BaseOutputTool
from rebasehelper.results_store import results_store


class JSON(BaseOutputTool):
    """ JSON output tool """

    EXTENSION: str = 'json'

    @classmethod
    def print_summary(cls, report_path, results):
        """Writes the report as JSON data.

        Args:
            report_path: Path to the report.
            results: Results store instance to get the data from.

        """
        with open(report_path, 'w', encoding=ENCODING) as outputfile:
            json.dump(results.get_all(), outputfile, indent=4, sort_keys=True)

    @classmethod
    def run(cls, logs, app):  # pylint: disable=unused-argument
        """Runs the output tool, writes the data to a JSON-formatted report."""
        cls.print_summary(cls.get_report_path(app), results_store)
