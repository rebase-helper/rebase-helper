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
import six
import koji  # pylint: disable=import-error

from rebasehelper.utils import KojiHelper
from rebasehelper.logger import logger
from rebasehelper.build_helper import BuildToolBase
from rebasehelper.build_helper import BinaryPackageBuildError


class KojiBuildTool(BuildToolBase):
    """
    Class representing Koji build tool.
    """

    CMD = "koji"
    LOCAL = False
    logs = []
    koji_helper = None

    # Taken from https://github.com/fedora-infra/the-new-hotness/blob/develop/fedmsg.d/hotness-example.py
    koji_web = "koji.fedoraproject.org"
    server = "https://%s/kojihub" % koji_web
    weburl = "http://%s/koji" % koji_web
    git_url = 'http://pkgs.fedoraproject.org/cgit/{package}.git'
    opts = {'scratch': True}
    target_tag = 'rawhide'
    priority = 30

    # Taken from  https://github.com/fedora-infra/the-new-hotness/blob/develop/hotness/buildsys.py#L78-L123

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
    def _scratch_build(cls, source, **kwargs):
        session = cls.koji_helper.session_maker()
        remote = cls.koji_helper.upload_srpm(session, source)
        task_id = session.build(remote, cls.target_tag, cls.opts, priority=cls.priority)
        if kwargs['builds_nowait']:
            return None, None, task_id
        weburl = cls.weburl + '/taskinfo?taskID=%i' % task_id
        logger.info('Koji task_id is here:\n' + weburl)
        session.logout()
        task_dict = cls.koji_helper.watch_koji_tasks(session, [task_id])
        task_list = []
        package_failed = False
        for key in six.iterkeys(task_dict):
            if task_dict[key] == koji.TASK_STATES['FAILED']:
                package_failed = True
            task_list.append(key)
        rpms, logs = cls.koji_helper.download_scratch_build(session,
                                                            task_list,
                                                            os.path.dirname(source).replace('SRPM', 'RPM'))
        if package_failed:
            weburl = '%s/taskinfo?taskID=%i' % (cls.weburl, task_list[0])
            logger.info('RPM build failed %s', weburl)
            logs.append(weburl)
            cls.logs.append(weburl)
            raise BinaryPackageBuildError
        logs.append(weburl)
        return rpms, logs, task_id

    @classmethod
    def get_logs(cls):
        return {'logs': cls.logs}

    @classmethod
    def wait_for_task(cls, build_dict, results_dir):
        if not cls.koji_helper:
            cls.koji_helper = KojiHelper()
        task_id = build_dict.get('koji_task_id')
        if not task_id:
            return None, None
        rpm, logs = build_dict.get('rpm'), build_dict.get('logs')
        while not rpm:
            rpm, logs = cls.koji_helper.get_koji_tasks(task_id, results_dir)
        return rpm, logs

    @classmethod
    def get_task_info(cls, build_dict):
        message = "Scratch build for '%s' version is: http://koji.fedoraproject.org/koji/taskinfo?taskID=%s"
        return message % (build_dict['version'], build_dict['koji_task_id'])

    @classmethod
    def get_detached_task(cls, task_id, results_dir):
        if not cls.koji_helper:
            cls.koji_helper = KojiHelper()
        try:
            return cls.koji_helper.get_koji_tasks(task_id, results_dir)
        except TypeError:
            logger.info('Koji tasks are not finished yet. Try again later')
            return None, None

    @classmethod
    def build(cls, spec, sources, patches, results_dir, **kwargs):
        """
        Builds the SRPM using rpmbuild
        Builds the RPMs using koji

        :param spec: absolute path to the SPEC file.
        :param sources: list with absolute paths to SOURCES
        :param patches: list with absolute paths to PATCHES
        :param results_dir: absolute path to DIR where results should be stored
        :param upstream_monitoring: specify if build is handled by upstream monitoring
        :return: dict with:
                 'srpm' -> absolute path to SRPM
                 'rpm' -> list with absolute paths to RPMs
                 'logs' -> list with absolute paths to build_logs
        """
        # build SRPM
        srpm, cls.logs = cls._build_srpm(spec, sources, patches, results_dir)
        # build RPMs
        rpm_results_dir = os.path.join(results_dir, "RPM")
        os.makedirs(rpm_results_dir)
        if not cls.koji_helper:
            cls.koji_helper = KojiHelper()
        rpms, rpm_logs, koji_task_id = cls._scratch_build(srpm, **kwargs)
        if rpm_logs:
            cls.logs.extend(rpm_logs)
        return {'srpm': srpm,
                'rpm': rpms,
                'logs': cls.logs,
                'koji_task_id': koji_task_id}

