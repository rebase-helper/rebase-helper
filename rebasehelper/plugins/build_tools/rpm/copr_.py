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
from typing import cast

from rebasehelper.helpers.copr_helper import CoprHelper
from rebasehelper.types import Options
from rebasehelper.logger import CustomLogger
from rebasehelper.exceptions import RebaseHelperError
from rebasehelper.plugins.build_tools.rpm import BuildToolBase
from rebasehelper.exceptions import BinaryPackageBuildError


logger: CustomLogger = cast(CustomLogger, logging.getLogger(__name__))


class Copr(BuildToolBase):
    """
    Class representing Copr build tool.
    """

    OPTIONS: Options = [
        {
            'name': ['--copr-project-permanent'],
            'switch': True,
            'default': False,
            'help': 'make the created copr project permanent'
        },
        {
            'name': ['--copr-project-frontpage'],
            'switch': True,
            'default': False,
            'help': 'make the created copr project visible on the frontpage',
        },
        {
            'name': ['--copr-chroots'],
            'type': lambda s: s.split(','),
            'default': ['fedora-rawhide-x86_64'],
            'help': 'comma-separated list of chroots to create copr project with',
        },
    ]

    CREATES_TASKS: bool = True

    PREFIX: str = 'rebase-helper-'
    DESCRIPTION: str = 'Repository containing rebase-helper builds.'
    INSTRUCTIONS: str = '''You can use this repository to test functionality
                         of rebased packages.'''

    @classmethod
    def _build_rpms(cls, srpm, name, **kwargs):
        project = cls.PREFIX + name
        client = CoprHelper.get_client()
        options = kwargs.get('app_kwargs', {})
        hide = not options.get('copr_project_frontpage')
        permanent = options.get('copr_project_permanent')
        chroots = options.get('copr_chroots')

        CoprHelper.create_project(client, project, chroots, cls.DESCRIPTION, cls.INSTRUCTIONS, permanent, hide)
        build_id = CoprHelper.build(client, project, srpm)
        if kwargs['builds_nowait']:
            return None, None, build_id
        build_url = CoprHelper.get_build_url(client, build_id)
        logger.info('Copr build is here: %s', build_url)
        failed = not CoprHelper.watch_build(client, build_id)
        destination = os.path.dirname(srpm).replace('SRPM', 'RPM')
        rpms, logs = CoprHelper.download_build(client, build_id, destination)
        logs.append(build_url)
        if failed:
            logger.error('Copr build failed %s', build_url)
            raise BinaryPackageBuildError(logs=logs)
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
        rpms, logs, build_id = cls._build_rpms(srpm, **kwargs)
        return dict(rpm=rpms, logs=logs, copr_build_id=build_id)

    @classmethod
    def get_task_info(cls, build_dict):
        client = CoprHelper.get_client()
        build_url = CoprHelper.get_build_url(client, build_dict['copr_build_id'])
        message = "Copr build for '%s' version is: %s"
        return message % (build_dict['version'], build_url)

    @classmethod
    def get_detached_task(cls, task_id, results_dir):
        client = CoprHelper.get_client()
        build_id = int(task_id)
        status = CoprHelper.get_build_status(client, build_id)
        if status in ['importing', 'pending', 'starting', 'running']:
            raise RebaseHelperError('Copr build is not finished yet. Try again later')
        else:
            rpm, logs = CoprHelper.download_build(client, build_id, results_dir)
            if status not in ['succeeded', 'skipped']:
                logger.info('Copr build %d did not complete successfully', build_id)
                raise BinaryPackageBuildError(logs=logs)
            return rpm, logs

    @classmethod
    def wait_for_task(cls, build_dict, task_id, results_dir):
        client = CoprHelper.get_client()
        build_id = int(task_id)
        failed = not CoprHelper.watch_build(client, build_id)
        rpms, logs = CoprHelper.download_build(client, build_id, results_dir)
        build_url = CoprHelper.get_build_url(client, build_id)
        logs.append(build_url)
        if failed:
            logger.error('Copr build failed %s', build_url)
            raise BinaryPackageBuildError(logs=logs)
        return rpms, logs
