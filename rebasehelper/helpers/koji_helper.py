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
import random
import string
import sys
import time

from rebasehelper.exceptions import RebaseHelperError
from rebasehelper.logger import logger
from rebasehelper.helpers.console_helper import ConsoleHelper
from rebasehelper.helpers.rpm_helper import RpmHelper
from rebasehelper.helpers.download_helper import DownloadHelper

koji_helper_functional: bool
try:
    import koji  # type: ignore
    from koji_cli.lib import TaskWatcher  # type: ignore
except ImportError:
    koji_helper_functional = False
else:
    koji_helper_functional = True


class KojiHelper:

    functional: bool = koji_helper_functional

    @classmethod
    def create_session(cls, login=False, profile='koji'):
        """Creates new Koji session and immediately logs in to a Koji hub.

        Args:
            login (bool): Whether to perform a login.
            profile (str): Koji profile to use.

        Returns:
            koji.ClientSession: Newly created session instance.

        Raises:
            RebaseHelperError: If login failed.

        """
        config = koji.read_config(profile)
        session = koji.ClientSession(config['server'], opts=config)
        if not login:
            return session
        try:
            session.gssapi_login()
        except Exception:  # pylint: disable=broad-except
            pass
        else:
            return session
        # fall back to kerberos login (doesn't work with python3)
        exc = (koji.AuthError, koji.krbV.Krb5Error) if koji.krbV else koji.AuthError
        try:
            session.krb_login()
        except exc as e:
            raise RebaseHelperError('Login failed: {}'.format(str(e)))
        else:
            return session

    @classmethod
    def upload_srpm(cls, session, srpm):
        """Uploads SRPM to a Koji hub.

        Args:
            session (koji.ClientSession): Active Koji session instance.
            srpm (str): Valid path to SRPM.

        Returns:
            str: Remote path to the uploaded SRPM.

        Raises:
            RebaseHelperError: If upload failed.

        """
        def progress(uploaded, total, chunksize, t1, t2):  # pylint: disable=unused-argument
            DownloadHelper.progress(total, uploaded, upload_start)
        suffix = ''.join(random.choice(string.ascii_letters) for _ in range(8))
        path = os.path.join('cli-build', str(time.time()), suffix)
        logger.info('Uploading SRPM')
        try:
            try:
                upload_start = time.time()
                session.uploadWrapper(srpm, path, callback=progress)
            except koji.GenericError as e:
                raise RebaseHelperError('Upload failed: {}'.format(str(e)))
        finally:
            sys.stdout.write('\n')
            sys.stdout.flush()
        return os.path.join(path, os.path.basename(srpm))

    @classmethod
    def get_task_url(cls, session, task_id):
        return '/'.join([session.opts['weburl'], 'taskinfo?taskID={}'.format(task_id)])

    @classmethod
    def display_task_results(cls, tasks):
        """Prints states of Koji tasks.

        Args:
            tasks (list): List of koji.TaskWatcher instances.

        """
        for task in [t for t in tasks if t.level == 0]:
            state = task.info['state']
            task_label = task.str()
            logger.info('State %s (%s)', state, task_label)
            if state == koji.TASK_STATES['CLOSED']:
                logger.info('%s completed successfully', task_label)
            elif state == koji.TASK_STATES['FAILED']:
                logger.info('%s failed', task_label)
            elif state == koji.TASK_STATES['CANCELED']:
                logger.info('%s was canceled', task_label)
            else:
                # shouldn't happen
                logger.info('%s has not completed', task_label)

    @classmethod
    def watch_koji_tasks(cls, session, tasklist):
        """Waits for Koji tasks to finish and prints their states.

        Args:
            session (koji.ClientSession): Active Koji session instance.
            tasklist (list): List of task IDs.

        Returns:
            dict: Dictionary mapping task IDs to their states or None if interrupted.

        """
        if not tasklist:
            return None
        sys.stdout.flush()
        rh_tasks = {}
        try:
            tasks = {}
            for task_id in tasklist:
                task_id = int(task_id)
                tasks[task_id] = TaskWatcher(task_id, session, quiet=False)
            while True:
                all_done = True
                for task_id, task in list(tasks.items()):
                    with ConsoleHelper.Capturer(stdout=True) as capturer:
                        changed = task.update()
                    for line in capturer.stdout.split('\n'):
                        if line:
                            logger.info(line)
                    info = session.getTaskInfo(task_id)
                    state = task.info['state']
                    if state == koji.TASK_STATES['FAILED']:
                        return {info['id']: state}
                    else:
                        # FIXME: multiple arches
                        if info['arch'] == 'x86_64' or info['arch'] == 'noarch':
                            rh_tasks[info['id']] = state
                    if not task.is_done():
                        all_done = False
                    else:
                        if changed:
                            # task is done and state just changed
                            cls.display_task_results(list(tasks.values()))
                        if not task.is_success():
                            rh_tasks = None
                    for child in session.getTaskChildren(task_id):
                        child_id = child['id']
                        if child_id not in list(tasks.keys()):
                            tasks[child_id] = TaskWatcher(child_id, session, task.level + 1, quiet=False)
                            with ConsoleHelper.Capturer(stdout=True) as capturer:
                                tasks[child_id].update()
                            for line in capturer.stdout.split('\n'):
                                if line:
                                    logger.info(line)
                            info = session.getTaskInfo(child_id)
                            state = task.info['state']
                            if state == koji.TASK_STATES['FAILED']:
                                return {info['id']: state}
                            else:
                                # FIXME: multiple arches
                                if info['arch'] == 'x86_64' or info['arch'] == 'noarch':
                                    rh_tasks[info['id']] = state
                            # If we found new children, go through the list again,
                            # in case they have children also
                            all_done = False
                if all_done:
                    cls.display_task_results(list(tasks.values()))
                    break
                sys.stdout.flush()
                time.sleep(1)
        except KeyboardInterrupt:
            rh_tasks = None
        return rh_tasks

    @classmethod
    def download_task_results(cls, session, tasklist, destination):
        """Downloads packages and logs of finished Koji tasks.

        Args:
            session (koji.ClientSession): Active Koji session instance.
            tasklist (list): List of task IDs.
            destination (str): Path where to download files to.

        Returns:
            tuple: List of downloaded RPMs and list of downloaded logs.

        Raises:
            DownloadError: If download failed.

        """
        rpms = []
        logs = []
        for task_id in tasklist:
            logger.info('Downloading packages and logs for task %s', task_id)
            task = session.getTaskInfo(task_id, request=True)
            if task['state'] in [koji.TASK_STATES['FREE'], koji.TASK_STATES['OPEN']]:
                logger.info('Task %s is still running!', task_id)
                continue
            elif task['state'] != koji.TASK_STATES['CLOSED']:
                logger.info('Task %s did not complete successfully!', task_id)
            if task['method'] == 'buildArch':
                tasks = [task]
            elif task['method'] == 'build':
                opts = dict(parent=task_id, method='buildArch', decode=True,
                            state=[koji.TASK_STATES['CLOSED'], koji.TASK_STATES['FAILED']])
                tasks = session.listTasks(opts=opts)
            else:
                logger.info('Task %s is not a build or buildArch task!', task_id)
                continue
            for task in tasks:
                base_path = koji.pathinfo.taskrelpath(task['id'])
                output = session.listTaskOutput(task['id'])
                for filename in output:
                    local_path = os.path.join(destination, filename)
                    download = False
                    fn, ext = os.path.splitext(filename)
                    if ext == '.rpm':
                        if task['state'] != koji.TASK_STATES['CLOSED']:
                            continue
                        if local_path not in rpms:
                            nevra = RpmHelper.split_nevra(fn)
                            # FIXME: multiple arches
                            download = nevra['arch'] in ['noarch', 'x86_64']
                            if download:
                                rpms.append(local_path)
                    else:
                        if local_path not in logs:
                            download = True
                            logs.append(local_path)
                    if download:
                        logger.info('Downloading file %s', filename)
                        url = '/'.join([session.opts['topurl'], 'work', base_path, filename])
                        DownloadHelper.download_file(url, local_path)
        return rpms, logs

    @classmethod
    def get_latest_build(cls, session, package):
        """Looks up latest Koji build of a package.

        Args:
            session (koji.ClientSession): Active Koji session instance.
            package (str): Package name.

        Returns:
            tuple: Found latest package version and Koji build ID.

        """
        builds = session.getLatestBuilds('rawhide', package=package)
        if builds:
            build = builds.pop()
            return build['version'], build['id']
        return None, None

    @classmethod
    def get_build(cls, session, package, version):
        """Looks up Koji build of a specific version of a package.

        Args:
            session (koji.ClientSession): Active Koji session instance.
            package (str): Package name.
            version (str): Package version.

        Returns:
            tuple: Found latest package version and Koji build ID.

        """
        builds = session.listTagged('rawhide', inherit=True, package=package)
        if builds:
            for build in builds:
                if build['version'] == version:
                    return build['version'], build['id']
        return None, None

    @classmethod
    def download_build(cls, session, build_id, destination, arches):
        """Downloads RPMs and logs of a Koji build.

        Args:
            session (koji.ClientSession): Active Koji session instance.
            build_id (str): Koji build ID.
            destination (str): Path where to download files to.
            arches (list): List of architectures to be downloaded.

        Returns:
            tuple: List of downloaded RPMs and list of downloaded logs.

        Raises:
            DownloadError: If download failed.

        """
        build = session.getBuild(build_id)
        pathinfo = koji.PathInfo(topdir=session.opts['topurl'])
        rpms = []
        logs = []
        os.makedirs(destination, exist_ok=True)
        for pkg in session.listBuildRPMs(build_id):
            if pkg['arch'] not in arches:
                continue
            rpmpath = pathinfo.rpm(pkg)
            local_path = os.path.join(destination, os.path.basename(rpmpath))
            if local_path not in rpms:
                url = pathinfo.build(build) + '/' + rpmpath
                DownloadHelper.download_file(url, local_path)
                rpms.append(local_path)
        for logfile in session.getBuildLogs(build_id):
            if logfile['dir'] not in arches:
                continue
            local_path = os.path.join(destination, logfile['name'])
            if local_path not in logs:
                url = pathinfo.topdir + '/' + logfile['path']
                DownloadHelper.download_file(url, local_path)
                logs.append(local_path)
        return rpms, logs

    @classmethod
    def get_old_build_info(cls, package_name, package_version):
        """Gets old build info from Koji.

        Args:
            package_name (str): Package name from specfile.
            package_version (str): Package version from specfile.

        Returns:
            tuple: Koji build id, package version.

        """
        if cls.functional:
            session = KojiHelper.create_session()
            koji_version, koji_build_id = KojiHelper.get_build(session, package_name, package_version)
            if koji_version:
                return koji_build_id, koji_version
            else:
                logger.warning('Unable to find old version Koji build!')
                return None, None
        else:
            logger.warning('Unable to get old version Koji build!')
            return None, None
