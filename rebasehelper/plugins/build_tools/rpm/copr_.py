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

from typing import List, Optional

from rebasehelper.helpers.copr_helper import CoprHelper
from rebasehelper.logger import logger
from rebasehelper.exceptions import RebaseHelperError
from rebasehelper.plugins.build_tools.rpm import BuildToolBase
from rebasehelper.exceptions import BinaryPackageBuildError


class Copr(BuildToolBase):
    """
    Class representing Copr build tool.
    """

    CREATES_TASKS: bool = True

    CMD: str = 'copr'
    logs: List[str] = []
    copr_helper: Optional[CoprHelper] = None

    prefix: str = 'rebase-helper-'
    chroot: str = 'fedora-rawhide-x86_64'
    description: str = 'Repository containing rebase-helper builds.'
    instructions: str = '''You can use this repository to test functionality
                         of rebased packages.'''

    @classmethod
    def _build_rpms(cls, srpm, name, **kwargs):
        project = cls.prefix + name
        client = cls.copr_helper.get_client()
        cls.copr_helper.create_project(client, project, cls.chroot,
                                       cls.description, cls.instructions)
        build_id = cls.copr_helper.build(client, project, srpm)
        if kwargs['builds_nowait']:
            return None, None, build_id
        build_url = cls.copr_helper.get_build_url(client, build_id)
        logger.info('Copr build is here: %s\n', build_url)
        failed = not cls.copr_helper.watch_build(client, build_id)
        destination = os.path.dirname(srpm).replace('SRPM', 'RPM')
        rpms, logs = cls.copr_helper.download_build(client,
                                                    build_id,
                                                    destination)
        if failed:
            logger.info('Copr build failed %s', build_url)
            logs.append(build_url)
            cls.logs.append(build_url)
            raise BinaryPackageBuildError
        logs.append(build_url)
        return rpms, logs, build_id

    @classmethod
    def build(cls, spec, results_dir, srpm, **kwargs):
        """
        Builds the RPMs using copr

        :param spec: SpecFile object
        :param results_dir: absolute path to DIR where results should be stored
        :param srpm: absolute path to SRPM
        :return: dict with:
                 'rpm' -> list with absolute paths to RPMs
                 'logs' -> list with absolute paths to build_logs
                 'copr_build_id' -> ID of copr build
        """
        cls.logs = []
        rpm_results_dir = os.path.join(results_dir, "RPM")
        os.makedirs(rpm_results_dir)
        if not cls.copr_helper:
            cls.copr_helper = CoprHelper()
        rpms, rpm_logs, build_id = cls._build_rpms(srpm, **kwargs)
        if rpm_logs:
            cls.logs.extend(rpm_logs)
        return dict(rpm=rpms, logs=cls.logs, copr_build_id=build_id)

    @classmethod
    def get_task_info(cls, build_dict):
        if not cls.copr_helper:
            cls.copr_helper = CoprHelper()
        client = cls.copr_helper.get_client()
        build_url = cls.copr_helper.get_build_url(client, build_dict['copr_build_id'])
        message = "Copr build for '%s' version is: %s"
        return message % (build_dict['version'], build_url)

    @classmethod
    def get_detached_task(cls, task_id, results_dir):
        if not cls.copr_helper:
            cls.copr_helper = CoprHelper()
        client = cls.copr_helper.get_client()
        build_id = int(task_id)
        status = cls.copr_helper.get_build_status(client, build_id)
        if status in ['importing', 'pending', 'starting', 'running']:
            raise RebaseHelperError('Copr build is not finished yet. Try again later')
        else:
            rpm, logs = cls.copr_helper.download_build(client, build_id, results_dir)
            if status not in ['succeeded', 'skipped']:
                logger.info('Copr build %d did not complete successfully', build_id)
                raise BinaryPackageBuildError
            return rpm, logs
