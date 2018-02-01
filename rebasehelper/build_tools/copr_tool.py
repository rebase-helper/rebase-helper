# -*- coding: utf-8 -*-
#
# This tool helps you to rebase package to the latest version
# Copyright (C) 2013-2014 Red Hat, Inc.
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
#
# Authors: Petr Hracek <phracek@redhat.com>
#          Tomas Hozza <thozza@redhat.com>

import os

from rebasehelper.utils import CoprHelper
from rebasehelper.logger import logger
from rebasehelper.build_helper import BuildToolBase
from rebasehelper.build_helper import BinaryPackageBuildError


class CoprBuildTool(BuildToolBase):
    """
    Class representing Copr build tool.
    """

    CMD = "copr"
    LOCAL = False
    logs = []
    copr_helper = None

    prefix = 'rebase-helper-'
    chroot = 'fedora-rawhide-x86_64'
    description = 'Repository containing rebase-helper builds.'
    instructions = '''You can use this repository to test functionality
                      of rebased packages.'''

    @classmethod
    def match(cls, cmd=None):
        if cmd == cls.CMD:
            return True
        else:
            return False

    @classmethod
    def get_build_tool_name(cls):
        return cls.CMD

    @classmethod
    def is_default(cls):
        return cls.DEFAULT

    @classmethod
    def accepts_options(cls):
        return False

    @classmethod
    def creates_tasks(cls):
        return True

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
    def build(cls, spec, sources, patches, results_dir, **kwargs):
        """
        Builds the SRPM using rpmbuild
        Builds the RPMs using copr

        :param spec: absolute path to the SPEC file.
        :param sources: list with absolute paths to SOURCES
        :param patches: list with absolute paths to PATCHES
        :param results_dir: absolute path to DIR where results should be stored
        :return: dict with:
                 'srpm' -> absolute path to SRPM
                 'rpm' -> list with absolute paths to RPMs
                 'logs' -> list with absolute paths to build_logs
        """
        # build SRPM
        srpm, cls.logs = cls._build_srpm(spec, sources, patches, results_dir, **kwargs)
        # build RPMs
        rpm_results_dir = os.path.join(results_dir, "RPM")
        os.makedirs(rpm_results_dir)
        if not cls.copr_helper:
            cls.copr_helper = CoprHelper()
        rpms, rpm_logs, build_id = cls._build_rpms(srpm, **kwargs)
        if rpm_logs:
            cls.logs.extend(rpm_logs)
        return {'srpm': srpm,
                'rpm': rpms,
                'logs': cls.logs,
                'copr_build_id': build_id}

    @classmethod
    def get_logs(cls):
        return {'logs': cls.logs}

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
            logger.info('Copr build is not finished yet. Try again later')
            return None, None
        else:
            rpm, logs = cls.copr_helper.download_build(client, build_id, results_dir)
            if status not in ['succeeded', 'skipped']:
                logger.info('Copr build %d did not complete successfully', build_id)
                return None, None
            return rpm, logs
