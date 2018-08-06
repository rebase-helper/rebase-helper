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

import requests
import random

from rebasehelper.helpers.git_helper import GitHelper
from rebasehelper.logger import logger


class FedoraApiHelper(object):

    fedora_api_url = 'https://src.fedoraproject.org/api/0'
    token = ''
    headers = {
        'Authorization': 'token ' + token
    }

    @classmethod
    def push_private_branch(cls, name='rebase-helper', patch_path=None):
        GitHelper.git_checkout(name)
        GitHelper.git_am(patch_path)
        GitHelper.git_push('origin', name)

    @classmethod
    def fork_project(cls, repo, namespace='rpms', username=None, wait=None):
        url = cls.fedora_api_url + '/fork'
        logger.info("Forking project {repo} from {fedora_api}".format(repo=repo, fedora_api=url))
        data = {
            'repo': repo,
            'namespace': namespace,
            'username': username,
            'wait': wait
        }
        res = requests.post(url, data, headers=cls.headers)
        logger.info("Fork API call response: {}".format(res.text))

    @classmethod
    def fork_and_push_changes(cls, repo, namespace='rpms', username=None, wait=None, patch_path=None):
        username = 'skisela'
        remote = 'fork'
        branch = 'f28'
        mybranch = 'my' + branch
        try:
            cls.fork_project(repo, namespace, username, wait)
        except Exception:
            logger.warning("Project {repo} already forked for {username} user.".format(repo=repo, username=username))

        try:
            GitHelper.git_remote_add('fork',
                                     'ssh://{name}@pkgs.fedoraproject.org/forks/{name}/{namespace}/{repo}.git'.format(
                                             name=username,
                                             namespace=namespace,
                                             repo=repo
                                     ))
            GitHelper.git_fetch_all(remote)
            GitHelper.git_checkout(mybranch, '{remote}/{branch}'.format(remote=remote, branch=branch))
            GitHelper.git_am(patch_path)
            logger.info("'{}' applied successfully.".format(patch_path))
            import pdb
            pdb.set_trace()
            while 1:
                try:
                    GitHelper.git_push(remote, mybranch)
                    GitHelper.git_checkout(mybranch)
                    break
                except Exception:
                    # Remove branch with this name exists, lets generate a random new one.
                    while GitHelper.git_rev_parse(mybranch):
                        mybranch = mybranch + str(random.randint(0, 10))
                    GitHelper.git_branch(mybranch)
            logger.info("'{branch}' successfully pushed to {remote} remote.".format(branch=mybranch, remote=remote))
        except Exception as e:
            logger.error(e)
