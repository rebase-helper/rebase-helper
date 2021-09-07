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

import pytest  # type: ignore

from rebasehelper.constants import RESULTS_DIR, DEBUG_LOG, CHANGES_PATCH, REPORT, ENCODING


def make_artifacts_report():
    artifacts = [
        DEBUG_LOG,
        CHANGES_PATCH,
        REPORT + '.json',
        'old-build/SRPM/build.log',
        'old-build/RPM/build.log',
        'old-build/RPM/root.log',
        'old-build/RPM/mock_output.log',
        'new-build/SRPM/build.log',
        'new-build/RPM/build.log',
        'new-build/RPM/root.log',
        'new-build/RPM/mock_output.log',
    ]
    report = []
    for artifact in artifacts:
        try:
            with open(os.path.join(RESULTS_DIR, artifact), encoding=ENCODING) as f:
                content = f.read()
                report.append(' {} '.format(artifact).center(80, '_'))
                report.append(content)
        except IOError:
            continue
    return '\n'.join(report)


@pytest.mark.hookwrapper
def pytest_runtest_makereport():
    outcome = yield
    report = outcome.get_result()
    report.sections.append(('Artifacts', make_artifacts_report()))
