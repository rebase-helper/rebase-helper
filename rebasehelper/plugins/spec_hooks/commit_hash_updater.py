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

import re

from rebasehelper.plugins.spec_hooks import BaseSpecHook
from rebasehelper.logger import logger
from rebasehelper.helpers.download_helper import DownloadHelper


class CommitHashUpdater(BaseSpecHook):
    """Tries to update commit hash present in Source0 tag according to the new version"""

    @classmethod
    def _get_commit_hash_from_github(cls, spec_file):
        """
        Tries to find a commit using Github API

        :param spec_file: SPEC file to base the search on
        :return: SHA of a commit, or None
        """
        m = re.match(r'^https?://github\.com/(?P<owner>[\w-]+)/(?P<project>[\w-]+)/.*$', spec_file.sources[0])
        if not m:
            return None
        baseurl = 'https://api.github.com/repos/{owner}/{project}'.format(**m.groupdict())
        # try to get tag name from a release matching version
        r = DownloadHelper.request('{}/releases'.format(baseurl))
        if r is None:
            return None

        if not r.ok:
            if r.status_code == 403 and r.headers.get('X-RateLimit-Remaining') == '0':
                logger.warning("Rate limit exceeded on Github API! Try again later.")
            return None
        data = r.json()
        version = spec_file.get_version()
        tag_name = None
        for release in data:
            if version in release.get('name'):
                tag_name = release.get('tag_name')
                break

        r = DownloadHelper.request('{}/tags'.format(baseurl))
        if r is None:
            return None
        if not r.ok:
            if r.status_code == 403 and r.headers.get('X-RateLimit-Remaining') == '0':
                logger.warning("Rate limit exceeded on Github API! Try again later.")
            return None
        data = r.json()
        for tag in data:
            name = tag.get('name')
            if tag_name:
                if name != tag_name:
                    continue
            else:
                # no specific tag name, try common tag names
                if name not in [version, 'v{}'.format(version)]:
                    continue
            commit = tag.get('commit')
            if commit:
                return commit.get('sha')
        return None

    @classmethod
    def _get_commit_hash(cls, spec_file):
        if 'github.com' in spec_file.sources[0]:
            return cls._get_commit_hash_from_github(spec_file)
        return None

    @classmethod
    def run(cls, spec_file, rebase_spec_file, **kwargs):
        if rebase_spec_file.sources[0] != spec_file.sources[0]:
            # nothing to do
            return
        # try to determine commit hash matching the new version
        new_commit = cls._get_commit_hash(rebase_spec_file)
        if not new_commit:
            return
        source = rebase_spec_file.sources[0]
        # try to determine commit hash matching the old version
        old_commit = cls._get_commit_hash(spec_file)
        if old_commit:
            # replace old commit hash with the new one
            source = source.replace(old_commit, new_commit)
        else:
            # try to find anything resembling SHA1 hash
            hashes = re.findall(r'[0-9a-f]{40}', source)
            if len(set(hashes)) != 1:
                # multiple different hashes (or none), cannot continue
                return
            source = source.replace(hashes[0], new_commit)
        tag = 'Source0'
        if [l for l in rebase_spec_file.spec_content.section('%package') if re.match(r'^Source\s*:.*', l)]:
            tag = 'Source'
        rebase_spec_file.set_tag(tag, source, preserve_macros=True)
