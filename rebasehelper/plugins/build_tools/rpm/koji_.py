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
import re

import koji  # type: ignore  # pylint: disable=import-error

# unused import needed to prevent loading koji buildtool with Koji < 1.13
import koji_cli.lib  # type: ignore  # pylint: disable=import-error,unused-import

from typing import List

from rebasehelper.types import Options
from rebasehelper.helpers.koji_helper import KojiHelper
from rebasehelper.logger import logger
from rebasehelper.exceptions import RebaseHelperError
from rebasehelper.plugins.build_tools.rpm import BuildToolBase
from rebasehelper.exceptions import BinaryPackageBuildError


class Koji(BuildToolBase):
    """
    Class representing Koji build tool.
    """

    OPTIONS: Options = [
        {
            "name": ["--get-old-build-from-koji"],
            "default": False,
            "switch": True,
            "help": "do not build old sources, download latest build from Koji instead",
        },
    ]

    CREATES_TASKS: bool = True

    CMD: str = 'koji'
    logs: List[str] = []

    target_tag: str = 'rawhide'

    @classmethod
    def _verify_tasks(cls, session, task_dict):
        """Checks if any of the tasks failed and tries to extract mock exit code from it.

        Args:
            session (koji.ClientSession): Active Koji session instance.
            task_dict (dict): Dict mapping Koji task ID to its state.

        Returns:
            int: Mock exit code or -1 if any task failed, otherwise None.

        """
        for task_id, state in task_dict.items():
            if state == koji.TASK_STATES['FAILED']:
                try:
                    session.getTaskResult(task_id)
                except koji.BuildError as e:
                    # typical error message:
                    #   BuildError: error building package (arch noarch),
                    #   mock exited with status 1; see build.log for more information
                    match = re.search(r'mock exited with status (\d+)', str(e))
                    if match:
                        return int(match.group(1))
                    else:
                        return -1
        return None

    @classmethod
    def _scratch_build(cls, srpm, **kwargs):
        session = KojiHelper.create_session(login=True)
        remote = KojiHelper.upload_srpm(session, srpm)
        task_id = session.build(remote, cls.target_tag, dict(scratch=True))
        if kwargs['builds_nowait']:
            return None, None, task_id
        url = KojiHelper.get_task_url(session, task_id)
        logger.info('Koji task is here: %s\n', url)
        session.logout()
        task_dict = KojiHelper.watch_koji_tasks(session, [task_id])
        path = os.path.dirname(srpm).replace('SRPM', 'RPM')
        rpms, logs = KojiHelper.download_task_results(session, list(task_dict), path)
        exit_code = cls._verify_tasks(session, task_dict)
        if exit_code:
            raise BinaryPackageBuildError(exit_code=exit_code)
        return rpms, logs, task_id

    @classmethod
    def wait_for_task(cls, build_dict, task_id, results_dir):
        session = KojiHelper.create_session()
        task_dict = KojiHelper.watch_koji_tasks(session, [task_id])
        rpms, logs = KojiHelper.download_task_results(session, list(task_dict), results_dir)
        exit_code = cls._verify_tasks(session, task_dict)
        if exit_code:
            raise BinaryPackageBuildError(exit_code=exit_code)
        return rpms, logs

    @classmethod
    def get_task_info(cls, build_dict):
        session = KojiHelper.create_session()
        url = KojiHelper.get_task_url(session, build_dict['koji_task_id'])
        return 'Scratch build for {} version is: {}'.format(build_dict['version'], url)

    @classmethod
    def get_detached_task(cls, task_id, results_dir):
        session = KojiHelper.create_session()
        rpms, logs = KojiHelper.download_task_results(session, [task_id], results_dir)
        task = session.getTaskInfo(task_id)
        exit_code = cls._verify_tasks(session, {task_id: task['state']})
        if exit_code:
            raise BinaryPackageBuildError(exit_code=exit_code)
        if not rpms:
            raise RebaseHelperError('Koji tasks are not finished yet. Try again later.')
        return rpms, logs

    @classmethod
    def build(cls, spec, results_dir, srpm, **kwargs):
        """
        Builds the RPMs using koji

        :param spec: SpecFile object
        :param results_dir: absolute path to DIR where results should be stored
        :param srpm: absolute path to SRPM
        :param upstream_monitoring: specify if build is handled by upstream monitoring
        :return: dict with:
                 'rpm' -> list with absolute paths to RPMs
                 'logs' -> list with absolute paths to build_logs
                 'koji_task_id' -> ID of koji task
        """
        cls.logs = []
        rpm_results_dir = os.path.join(results_dir, "RPM")
        os.makedirs(rpm_results_dir)
        rpms, rpm_logs, koji_task_id = cls._scratch_build(srpm, **kwargs)
        if rpm_logs:
            cls.logs.extend(rpm_logs)
        return dict(rpm=rpms, logs=cls.logs, koji_task_id=koji_task_id)
