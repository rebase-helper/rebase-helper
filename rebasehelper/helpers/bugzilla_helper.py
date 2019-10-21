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
import re
from typing import cast, Optional, Tuple

import git  # type: ignore
import requests

from rebasehelper.exceptions import RebaseHelperError
from rebasehelper.logger import CustomLogger


logger: CustomLogger = cast(CustomLogger, logging.getLogger(__name__))


class BugzillaHelper:

    """Class for working with Upstream Release Monitoring on bugzilla."""

    DIST_GIT_REPO_URL = 'https://src.fedoraproject.org/rpms'
    BUGZILLA_REST_API_URL = 'https://bugzilla.redhat.com/rest'
    UPSTREAM_RELEASE_MONITORING_USERNAME = 'upstream-release-monitoring'

    @classmethod
    def get_bugzilla_component(cls, bugzilla_id: str) -> str:
        """Gets a component of the bugzilla.

        Args:
            bugzilla_id: ID of the bugzilla.

        Returns:
            Component of the bugzilla.

        Raises:
            RebaseHelperError: If no such bugzilla exists or if the bugzilla
            was not created by Upstream Release Monitoring.

        """
        r = requests.get('{}/bug/{}'.format(cls.BUGZILLA_REST_API_URL, bugzilla_id))
        if not r.ok:
            raise RebaseHelperError('Could not obtain data from bugzilla')

        response_json = r.json()
        if 'error' in response_json:
            logger.error('Bugzilla error: %s', response_json['error'])
            raise RebaseHelperError('Could not obtain data from bugzilla')

        bug = response_json['bugs'][0]
        if bug['creator_detail']['email'] != cls.UPSTREAM_RELEASE_MONITORING_USERNAME:
            raise RebaseHelperError('The given bugzilla was not created by Upstream Release Monitoring')
        return bug['component'][0]

    @classmethod
    def get_version_from_comments(cls, bugzilla_id: str) -> Optional[str]:
        """Gets version from bugzilla comments.

        Args:
            bugzilla_id: ID of the bugzilla.

        Returns:
            Version specified by Upstream Release Monitoring in comments
            or None, if no version could be found.

        Raises:
            RebaseHelperError: If no such bugzilla exists.

        """
        r = requests.get('{}/bug/{}/comment'.format(cls.BUGZILLA_REST_API_URL, bugzilla_id))
        if not r.ok:
            raise RebaseHelperError('Could not obtain data from bugzilla')
        version = None
        comments = r.json()['bugs'][bugzilla_id]['comments']
        pattern = re.compile(r'^Latest upstream release: (?P<version>.*)\n')
        for comment in comments:
            if comment['creator'] != cls.UPSTREAM_RELEASE_MONITORING_USERNAME:
                continue
            match = pattern.match(comment['text'])
            if match:
                version = match.group('version')

        return version

    @classmethod
    def clone_repository(cls, component: str, bugzilla_id: str) -> str:
        """Clones remote dist-git repository of a component.

        Args:
            component: Package to clone.
            bugzilla_id: ID of the bugzilla.

        Returns:
            Path to the cloned repository.

        Raises:
            RebaseHelperError: If the directory, that the repository
            is supposed to be cloned into, exists.

        """
        path = os.path.abspath('{}-{}'.format(bugzilla_id, component))
        if os.path.exists(path):
            raise RebaseHelperError('Could not clone the repository because the directory '
                                    '{} already exists'.format(path))

        url = '{}/{}.git'.format(cls.DIST_GIT_REPO_URL, component)
        logger.info("Cloning %s into %s", url, path)
        git.Repo.clone_from(url, path)
        return path

    @classmethod
    def prepare_rebase_repository(cls, bugzilla_id: str) -> Tuple[str, str]:
        """Clones a repository based on Upstream Release Monitoring bugzilla.

        Args:
            bugzilla_id: ID of the bugzilla.

        Returns:
            Path of the cloned repository and version to rebase to.

        Raises:
            RebaseHelperError: If there was an error while obtaining
            data from bugzilla or if there was a problem while cloning
            the repository.

        """
        component = cls.get_bugzilla_component(bugzilla_id)
        version = cls.get_version_from_comments(bugzilla_id)
        if not version:
            raise RebaseHelperError('Could not obtain version from the bugzilla')

        path = cls.clone_repository(component, bugzilla_id)
        return path, version
