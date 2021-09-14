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
import time
import urllib.parse
from typing import cast

import pyquery  # type: ignore
from copr.v3 import (  # type: ignore
    Client, CoprConfigException, CoprNoConfigException, CoprRequestException, CoprNoResultException)


from rebasehelper.exceptions import RebaseHelperError
from rebasehelper.helpers.download_helper import DownloadHelper
from rebasehelper.logger import CustomLogger


logger: CustomLogger = cast(CustomLogger, logging.getLogger(__name__))


class CoprHelper:

    DELETE_PROJECT_AFTER = 60

    @classmethod
    def get_client(cls):
        try:
            client = Client.create_from_config_file()
        except (CoprNoConfigException, CoprConfigException) as e:
            raise RebaseHelperError('Missing or invalid copr configuration file') from e
        else:
            return client

    @classmethod
    def create_project(cls, client, project, chroots, description, instructions, permanent=False, hide=True):
        try:
            client.project_proxy.get(ownername=client.config.get('username'), projectname=project)
            # Project found, reuse it
        except CoprNoResultException:
            try:
                client.project_proxy.add(ownername=client.config.get('username'),
                                         projectname=project,
                                         chroots=chroots,
                                         delete_after_days=None if permanent else cls.DELETE_PROJECT_AFTER,
                                         unlisted_on_hp=hide,
                                         description=description,
                                         instructions=instructions)
            except CoprRequestException as e:
                error = e.result.error
                try:
                    [[error]] = error.values()
                except AttributeError:
                    pass
                raise RebaseHelperError('Failed to create copr project. Reason: {}'.format(error)) from e

    @classmethod
    def build(cls, client, project, srpm):
        try:
            result = client.build_proxy.create_from_file(client.config.get('username'), project, srpm)
        except CoprRequestException as e:
            raise RebaseHelperError('Failed to start copr build: {}'.format(str(e))) from e
        else:
            return result.id

    @classmethod
    def get_build_url(cls, client, build_id):
        try:
            result = client.build_proxy.get(build_id)
        except CoprRequestException as e:
            raise RebaseHelperError(
                'Failed to get copr build details for id {}: {}'.format(build_id, str(e))) from e
        else:
            return '{}/coprs/{}/{}/build/{}/'.format(client.config.get('copr_url'),
                                                     result.ownername,
                                                     result.projectname,
                                                     build_id)

    @classmethod
    def get_build_status(cls, client, build_id):
        try:
            result = client.build_proxy.get(build_id)
        except CoprRequestException as e:
            raise RebaseHelperError(
                'Failed to get copr build details for id {}: {}'.format(build_id, str(e))) from e
        else:
            return result.state

    @classmethod
    def watch_build(cls, client, build_id):
        try:
            logged = False
            while True:
                status = cls.get_build_status(client, build_id)
                if not status:
                    return False
                elif status in ['succeeded', 'skipped']:
                    return True
                elif status in ['failed', 'canceled', 'unknown']:
                    return False
                else:
                    if not logged:
                        logger.info('Waiting for copr build to finish')
                        logged = True
                    time.sleep(10)
        except KeyboardInterrupt:
            return False

    @classmethod
    def download_build(cls, client, build_id, destination):
        logger.info('Downloading packages and logs for build %d', build_id)
        rpms = []
        logs = []
        for chroot in client.build_chroot_proxy.get_list(build_id):
            url = chroot.result_url
            url = url if url.endswith('/') else url + '/'
            d = pyquery.PyQuery(url)
            d.make_links_absolute()
            for a in d('a[href$=\'.rpm\'], a[href$=\'.log.gz\']'):
                fn = os.path.basename(urllib.parse.urlsplit(a.attrib['href']).path)
                dest = os.path.join(destination, chroot.name)
                os.makedirs(dest, exist_ok=True)
                dest = os.path.join(dest, fn)
                if fn.endswith('.src.rpm'):
                    # skip source RPM
                    continue
                DownloadHelper.download_file(a.attrib['href'], dest)
                if fn.endswith('.rpm'):
                    rpms.append(dest)
                elif fn.endswith('.log.gz'):
                    local_path = dest.replace('.log.gz', '.log')
                    os.rename(dest, local_path)
                    logs.append(local_path)
        return rpms, logs
