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

import configparser
import logging
import os
import time
import types
from typing import Dict, List, Union, cast

import pyrpkg  # type: ignore

from rebasehelper.exceptions import LookasideCacheError
from rebasehelper.logger import CustomLogger
from rebasehelper.helpers.download_helper import DownloadHelper


logger: CustomLogger = cast(CustomLogger, logging.getLogger(__name__))


class LookasideCacheHelper:

    """Class for downloading files from Fedora/CentOS/RHEL lookaside cache"""

    rpkg_config_dir: str = '/etc/rpkg'

    @classmethod
    def _read_config(cls, tool: str) -> Dict[str, Union[str, bool]]:
        config = configparser.ConfigParser()
        try:
            config.read(os.path.join(cls.rpkg_config_dir, '{}.conf'.format(tool)))
            return dict(config.items(tool, raw=True))
        except (configparser.Error, KeyError) as e:
            raise LookasideCacheError('Failed to read rpkg configuration') from e

    @classmethod
    def _get_cache(cls, config: Dict[str, Union[str, bool]]) -> pyrpkg.lookaside.CGILookasideCache:
        def print_progress(self, to_download, downloaded, to_upload, uploaded):
            if to_download > 0:
                DownloadHelper.progress(to_download, downloaded, self.progress_start)
            elif to_upload > 0:
                DownloadHelper.progress(to_upload, uploaded, self.progress_start)
        cache = pyrpkg.lookaside.CGILookasideCache(
            config['lookasidehash'],
            config['lookaside'],
            config['lookaside_cgi'])
        cache.progress_start = 0
        cache.print_progress = types.MethodType(print_progress, cache)
        return cache

    @classmethod
    def download(cls, tool: str, basepath: str, package: str, target_dir: str = '') -> None:
        config = cls._read_config(tool)
        if config.get('lookaside_namespaced', False):
            package = 'rpms/' + package
        cache = cls._get_cache(config)
        try:
            sources = pyrpkg.sources.SourcesFile(os.path.join(basepath, 'sources'), 'bsd')
        except (pyrpkg.errors.MalformedLineError, ValueError) as e:
            raise LookasideCacheError(str(e)) from e
        for entry in sources.entries:
            target = os.path.join(target_dir, entry.file)
            logger.info('Downloading %s from lookaside cache', entry.file)
            cache.progress_start = time.time()
            try:
                cache.download(package, entry.file, entry.hash, target, entry.hashtype)
            except pyrpkg.errors.DownloadError as e:
                raise LookasideCacheError(str(e)) from e

    @classmethod
    def update_sources(cls, tool: str, basepath: str, package: str,
                       old_sources: List[str], new_sources: List[str],
                       upload: bool = True, source_dir: str = '') -> List[str]:
        config = cls._read_config(tool)
        if config.get('lookaside_namespaced', False):
            package = 'rpms/' + package
        cache = cls._get_cache(config)
        try:
            sources = pyrpkg.sources.SourcesFile(os.path.join(basepath, 'sources'), 'bsd')
        except (pyrpkg.errors.MalformedLineError, ValueError) as e:
            raise LookasideCacheError(str(e)) from e
        uploaded = []
        for idx, src in enumerate(old_sources):
            entry = next(iter(e for e in sources.entries if e.file == src), None)
            if entry:
                filename = new_sources[idx]
                if filename == src:
                    # no change
                    continue
                hsh = cache.hash_file(filename)
                if upload:
                    logger.info('Uploading %s to lookaside cache', filename)
                    cache.progress_start = time.time()
                    try:
                        cache.upload(package, os.path.join(source_dir, filename), hsh)
                    except pyrpkg.errors.AlreadyUploadedError:
                        logger.info('%s is already present in lookaside cache, not uploading', filename)
                    except pyrpkg.errors.UploadError as e:
                        # skip the error, the rebase can continue even after a failed upload
                        logger.error('Upload to lookaside cache failed: %s', str(e))
                uploaded.append(filename)
                entry.file = filename
                entry.hash = hsh
                entry.hashtype = cache.hashtype
        sources.write()
        return uploaded
