# -*- coding: utf-8 -*-
#
# This tool helps you to rebase package to the latest version
# Copyright (C) 2013-2014 Red Hat, Inc.
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
# Authors: Petr Hracek <phracek@redhat.com>
#          Tomas Hozza <thozza@redhat.com>

import gzip
import hashlib
import os
import random
import re
import shutil
import string
import sys
import time

import copr
import pyquery
import requests
import six

from six.moves import urllib
from six.moves import configparser
from urllib3.fields import RequestField
from urllib3.filepost import encode_multipart_formdata

from rebasehelper.exceptions import RebaseHelperError, DownloadError, LookasideCacheError
from rebasehelper.logger import logger
from rebasehelper.helpers.download_helper import DownloadHelper
from rebasehelper.helpers.path_helper import PathHelper
from rebasehelper.helpers.console_helper import ConsoleHelper
from rebasehelper.helpers.rpm_helper import RpmHelper

try:
    from requests_gssapi import HTTPSPNEGOAuth as SPNEGOAuth
except ImportError:
    from requests_kerberos import HTTPKerberosAuth as SPNEGOAuth


try:
    import koji
    from koji_cli.lib import TaskWatcher
except ImportError:
    koji_helper_functional = False
else:
    koji_helper_functional = True


class TemporaryEnvironment(object):

    """
    Class representing a temporary environment (directory) that can be used
    as a workspace. It can be used with with statement.
    """

    TEMPDIR = 'TEMPDIR'

    def __init__(self, exit_callback=None):
        self._env = {}
        self._exit_callback = exit_callback

    def __enter__(self):
        self._env[self.TEMPDIR] = PathHelper.get_temp_dir()
        logger.debug("Created environment in '%s'", self.path())
        return self

    def __exit__(self, *args):
        # run callback before removing the environment
        try:
            self._exit_callback(**self.env())
        except TypeError:
            pass
        else:
            logger.debug("Exit callback executed successfully")

        shutil.rmtree(self.path(), onerror=lambda func, path, excinfo: shutil.rmtree(path))
        logger.debug("Destroyed environment in '%s'", self.path())

    def __str__(self):
        return "<TemporaryEnvironment path='%s'>", self.path()

    def path(self):
        """
        Returns path to the temporary environment.

        :return: abs path to the environment
        """
        return self._env.get(self.TEMPDIR, '')

    def env(self):
        """
        Returns copy of _env dictionary.

        :return: copy of _env dictionary
        """
        return self._env.copy()


class KojiHelper(object):

    functional = koji_helper_functional

    @classmethod
    def create_session(cls, profile='koji'):
        """Creates new Koji session and immediately logs in to a Koji hub.

        Args:
            profile (str): Koji profile to use.

        Returns:
            koji.ClientSession: Newly created session instance.

        Raises:
            RebaseHelperError: If login failed.

        """
        config = koji.read_config(profile)
        session = koji.ClientSession(config['server'], opts=config)
        try:
            session.gssapi_login()
        except Exception:  # pylint: disable=broad-except
            pass
        else:
            return session
        # fall back to kerberos login (doesn't work with python3)
        try:
            session.krb_login()
        except (koji.AuthError, koji.krbV.Krb5Error) as e:
            raise RebaseHelperError('Login failed: {}'.format(six.text_type(e)))
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
        suffix = ''.join([random.choice(string.ascii_letters) for _ in range(8)])
        path = os.path.join('cli-build', six.text_type(time.time()), suffix)
        logger.info('Uploading SRPM')
        try:
            try:
                upload_start = time.time()
                session.uploadWrapper(srpm, path, callback=progress)
            except koji.GenericError as e:
                raise RebaseHelperError('Upload failed: {}'.format(six.text_type(e)))
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
    def download_build(cls, session, build_id, destination):
        """Downloads RPMs and logs of a Koji build.

        Args:
            session (koji.ClientSession): Active Koji session instance.
            build_id (str): Koji build ID.
            destination (str): Path where to download files to.

        Returns:
            tuple: List of downloaded RPMs and list of downloaded logs.

        Raises:
            DownloadError: If download failed.

        """
        build = session.getBuild(build_id)
        packages = session.listRPMs(buildID=build_id)
        rpms = []
        logs = []
        for pkg in packages:
            # FIXME: multiple arches
            if pkg['arch'] not in ['noarch', 'x86_64']:
                continue
            for logname in ['build.log', 'root.log', 'state.log']:
                local_path = os.path.join(destination, logname)
                if local_path not in logs:
                    url = '/'.join([
                        session.opts['topurl'],
                        'packages',
                        build['package_name'],
                        build['version'],
                        build['release'],
                        'data',
                        'logs',
                        pkg['arch'],
                        logname])
                    DownloadHelper.download_file(url, local_path)
                    logs.append(local_path)
            filename = '.'.join([pkg['nvr'], pkg['arch'], 'rpm'])
            local_path = os.path.join(destination, filename)
            if local_path not in rpms:
                url = '/'.join([
                    session.opts['topurl'],
                    'packages',
                    build['package_name'],
                    build['version'],
                    build['release'],
                    pkg['arch'],
                    filename])
                DownloadHelper.download_file(url, local_path)
                rpms.append(local_path)
        return rpms, logs


class CoprHelper(object):

    @classmethod
    def get_client(cls):
        try:
            client = copr.CoprClient.create_from_file_config()
        except (copr.client.exceptions.CoprNoConfException,
                copr.client.exceptions.CoprConfigException):
            raise RebaseHelperError(
                'Missing or invalid copr configuration file')
        else:
            return client

    @classmethod
    def create_project(cls, client, project, chroot, description, instructions):
        try:
            try:
                client.create_project(projectname=project,
                                      chroots=[chroot],
                                      description=description,
                                      instructions=instructions)
            except TypeError:
                # username argument is required since python-copr-1.67-1
                client.create_project(username=None,
                                      projectname=project,
                                      chroots=[chroot],
                                      description=description,
                                      instructions=instructions)
        except copr.client.exceptions.CoprRequestException:
            # reuse existing project
            pass

    @classmethod
    def build(cls, client, project, srpm):
        try:
            result = client.create_new_build(projectname=project, pkgs=[srpm])
        except copr.client.exceptions.CoprRequestException as e:
            raise RebaseHelperError('Failed to start copr build: {}'.format(str(e)))
        else:
            return result.builds_list[0].build_id

    @classmethod
    def get_build_url(cls, client, build_id):
        try:
            result = client.get_build_details(build_id)
        except copr.client.exceptions.CoprRequestException as e:
            raise RebaseHelperError(
                'Failed to get copr build details for id {}: {}'.format(build_id, str(e)))
        else:
            return '{}/coprs/{}/{}/build/{}/'.format(client.copr_url,
                                                     client.username,
                                                     result.project,
                                                     build_id)

    @classmethod
    def get_build_status(cls, client, build_id):
        try:
            result = client.get_build_details(build_id)
        except copr.client.exceptions.CoprRequestException as e:
            raise RebaseHelperError(
                'Failed to get copr build details for id {}: {}'.format(build_id, str(e)))
        else:
            return result.status

    @classmethod
    def watch_build(cls, client, build_id):
        try:
            while True:
                status = cls.get_build_status(client, build_id)
                if not status:
                    return False
                elif status in ['succeeded', 'skipped']:
                    return True
                elif status in ['failed', 'canceled', 'unknown']:
                    return False
                else:
                    time.sleep(10)
        except KeyboardInterrupt:
            return False

    @classmethod
    def download_build(cls, client, build_id, destination):
        logger.info('Downloading packages and logs for build %d', build_id)
        try:
            result = client.get_build_details(build_id)
        except copr.client.exceptions.CoprRequestException as e:
            raise RebaseHelperError(
                'Failed to get copr build details for {}: {}'.format(build_id, str(e)))
        rpms = []
        logs = []
        for _, url in six.iteritems(result.data['results_by_chroot']):
            url = url if url.endswith('/') else url + '/'
            d = pyquery.PyQuery(url)
            d.make_links_absolute()
            for a in d('a[href$=\'.rpm\'], a[href$=\'.log.gz\']'):
                fn = os.path.basename(urllib.parse.urlsplit(a.attrib['href']).path)
                dest = os.path.join(destination, fn)
                if fn.endswith('.src.rpm'):
                    # skip source RPM
                    continue
                DownloadHelper.download_file(a.attrib['href'], dest)
                if fn.endswith('.rpm'):
                    rpms.append(dest)
                elif fn.endswith('.log.gz'):
                    extracted = dest.replace('.log.gz', '.log')
                    try:
                        with gzip.open(dest, 'rb') as archive:
                            with open(extracted, 'wb') as f:
                                f.write(archive.read())
                    except (IOError, EOFError):
                        raise RebaseHelperError(
                            'Failed to extract {}'.format(dest))
                    logs.append(extracted)
        return rpms, logs


class FileHelper(object):

    @staticmethod
    def file_available(filename):
        if os.path.exists(filename) and os.path.getsize(filename) != 0:
            return True
        else:
            return False


class LookasideCacheHelper(object):

    """Class for downloading files from Fedora/RHEL lookaside cache"""

    rpkg_config_dir = '/etc/rpkg'

    @classmethod
    def _read_config(cls, tool):
        config = configparser.ConfigParser()
        config.read(os.path.join(cls.rpkg_config_dir, '{}.conf'.format(tool)))
        return dict(config.items(tool, raw=True))

    @classmethod
    def _read_sources(cls, basepath):
        line_re = re.compile(r'^(?P<hashtype>[^ ]+?) \((?P<filename>[^ )]+?)\) = (?P<hash>[^ ]+?)$')
        sources = []
        path = os.path.join(basepath, 'sources')
        if os.path.exists(path):
            with open(path, 'r') as f:
                for line in f.readlines():
                    line = line.strip()
                    m = line_re.match(line)
                    if m is not None:
                        d = m.groupdict()
                    else:
                        # fall back to old format of sources file
                        hsh, filename = line.split()
                        d = dict(hash=hsh, filename=filename, hashtype='md5')
                    d['hashtype'] = d['hashtype'].lower()
                    sources.append(d)
        return sources

    @classmethod
    def _write_sources(cls, basepath, sources):
        path = os.path.join(basepath, 'sources')
        with open(path, 'w') as f:
            for source in sources:
                f.write('{0} ({1}) = {2}\n'.format(source['hashtype'].upper(), source['filename'], source['hash']))

    @classmethod
    def _hash(cls, filename, hashtype):
        try:
            chksum = hashlib.new(hashtype)
        except ValueError:
            raise LookasideCacheError('Unsupported hash type \'{}\''.format(hashtype))
        with open(filename, 'rb') as f:
            chunk = f.read(8192)
            while chunk:
                chksum.update(chunk)
                chunk = f.read(8192)
        return chksum.hexdigest()

    @classmethod
    def _download_source(cls, tool, url, package, filename, hashtype, hsh, target=None):
        if target is None:
            target = os.path.basename(filename)
        if os.path.exists(target):
            if cls._hash(target, hashtype) == hsh:
                # nothing to do
                return
            else:
                os.unlink(target)
        if tool == 'fedpkg':
            url = '{}/{}/{}/{}/{}/{}'.format(url, package, filename, hashtype, hsh, filename)
        else:
            url = '{}/{}/{}/{}/{}'.format(url, package, filename, hsh, filename)
        try:
            DownloadHelper.download_file(url, target)
        except DownloadError as e:
            raise LookasideCacheError(six.text_type(e))

    @classmethod
    def download(cls, tool, basepath, package):
        try:
            config = cls._read_config(tool)
            url = config['lookaside']
        except (configparser.Error, KeyError):
            raise LookasideCacheError('Failed to read rpkg configuration')
        for source in cls._read_sources(basepath):
            cls._download_source(tool, url, package, source['filename'], source['hashtype'], source['hash'])

    @classmethod
    def _upload_source(cls, url, package, filename, hashtype, hsh, auth=SPNEGOAuth()):
        class ChunkedData(object):
            def __init__(self, check_only, chunksize=8192):
                self.check_only = check_only
                self.chunksize = chunksize
                self.start = time.time()
                fields = [
                    ('name', package),
                    ('{}sum'.format(hashtype), hsh),
                ]
                if check_only:
                    fields.append(('filename', filename))
                else:
                    with open(filename, 'rb') as f:
                        rf = RequestField('file', f.read(), filename)
                        rf.make_multipart()
                        fields.append(rf)
                self.data, content_type = encode_multipart_formdata(fields)
                self.headers = {'Content-Type': content_type}

            def __iter__(self):
                totalsize = len(self.data)
                for offset in range(0, totalsize, self.chunksize):
                    transferred = offset + self.chunksize
                    if not self.check_only:
                        DownloadHelper.progress(totalsize, transferred, self.start)
                    yield self.data[offset:transferred]

        def post(check_only=False):
            cd = ChunkedData(check_only)
            r = requests.post(url, data=cd, headers=cd.headers, auth=auth)
            if not 200 <= r.status_code < 300:
                raise LookasideCacheError(r.reason)
            return r.content

        state = post(check_only=True)
        if state.strip() == b'Available':
            # already uploaded
            return

        logger.info('Uploading %s to lookaside cache', filename)
        try:
            post()
        finally:
            sys.stdout.write('\n')
            sys.stdout.flush()

    @classmethod
    def update_sources(cls, tool, basepath, package, old_sources, new_sources):
        try:
            config = cls._read_config(tool)
            url = config['lookaside_cgi']
            hashtype = config['lookasidehash']
        except (configparser.Error, KeyError):
            raise LookasideCacheError('Failed to read rpkg configuration')
        uploaded = []
        sources = cls._read_sources(basepath)
        for idx, src in enumerate(old_sources):
            indexes = [i for i, s in enumerate(sources) if s['filename'] == src]
            if indexes:
                filename = new_sources[idx]
                if filename == src:
                    # no change
                    continue
                hsh = cls._hash(filename, hashtype)
                cls._upload_source(url, package, filename, hashtype, hsh)
                uploaded.append(filename)
                sources[indexes[0]] = dict(hash=hsh, filename=filename, hashtype=hashtype)
        cls._write_sources(basepath, sources)
        return uploaded
