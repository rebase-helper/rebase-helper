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
import hashlib
import logging
import os
import re
import sys
import threading
import time
from typing import cast

import requests
import requests_gssapi  # type: ignore
from urllib3.fields import RequestField  # type: ignore
from urllib3.filepost import encode_multipart_formdata  # type: ignore

from rebasehelper.exceptions import LookasideCacheError, DownloadError
from rebasehelper.logger import CustomLogger
from rebasehelper.helpers.download_helper import DownloadHelper


logger: CustomLogger = cast(CustomLogger, logging.getLogger(__name__))


class LookasideCacheHelper:

    """Class for downloading files from Fedora/RHEL lookaside cache"""

    rpkg_config_dir: str = '/etc/rpkg'

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
        if os.path.isfile(path):
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
        elif os.path.exists(path):
            logger.warning("\"sources\" is not a file, skipping parsing it")
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
        except ValueError as e:
            raise LookasideCacheError('Unsupported hash type \'{}\''.format(hashtype)) from e
        with open(filename, 'rb') as f:
            chunk = f.read(8192)
            while chunk:
                chksum.update(chunk)
                chunk = f.read(8192)
        return chksum.hexdigest()

    @classmethod
    def _download_source(cls, url, package, filename, hashtype, hsh, target=None):
        if target is None:
            target = os.path.basename(filename)
        if os.path.exists(target):
            if cls._hash(target, hashtype) == hsh:
                # nothing to do
                return
            else:
                os.unlink(target)
        url = '{0}/rpms/{1}/{2}/{3}/{4}/{2}'.format(url, package, filename, hashtype, hsh)
        try:
            DownloadHelper.download_file(url, target)
        except DownloadError as e:
            raise LookasideCacheError(str(e)) from e

    @classmethod
    def download(cls, tool, basepath, package, target_dir=None):
        try:
            config = cls._read_config(tool)
            url = config['lookaside']
        except (configparser.Error, KeyError) as e:
            raise LookasideCacheError('Failed to read rpkg configuration') from e
        for source in cls._read_sources(basepath):
            target = os.path.join(target_dir, source['filename'])
            cls._download_source(url, package, source['filename'], source['hashtype'], source['hash'], target)

    @classmethod
    def _upload_source(cls, url, package, source_dir, filename, hashtype, hsh, auth=requests_gssapi.HTTPSPNEGOAuth()):
        class ChunkedData:
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
                    fields.append(('mtime', str(int(os.stat(filename).st_mtime))))
                    with open(path, 'rb') as f:
                        rf = RequestField('file', f.read(), filename)
                        rf.make_multipart()
                        fields.append(rf)
                self.data, content_type = encode_multipart_formdata(fields)
                self.headers = {'Content-Type': content_type}

            def __iter__(self):
                totalsize = len(self.data)
                for offset in range(0, totalsize, self.chunksize):
                    transferred = min(offset + self.chunksize, totalsize)
                    if not self.check_only:
                        DownloadHelper.progress(totalsize, transferred, self.start)
                    yield self.data[offset:transferred]

        class FakeProgress(threading.Thread):
            def __init__(self, check_only, interval=0.2):
                self.check_only = check_only
                self.interval = interval
                self.stop_event = threading.Event()
                super().__init__()

            def run(self):
                if self.check_only:
                    return
                n = 0
                start = time.time()
                while not self.stop_event.is_set():
                    DownloadHelper.progress(-1, n * 256 * 1024, start, show_size=False)
                    n += 1
                    self.stop_event.wait(self.interval)

            def stop(self):
                self.stop_event.set()
                super().join()

        def post(check_only=False):
            cd = ChunkedData(check_only)
            if 'src.fedoraproject.org' in url:
                # src.fedoraproject.org can't handle chunked requests properly and requires opportunistic authentication
                fp = FakeProgress(check_only)
                fp.start()
                try:
                    r = requests.post(url, data=cd.data, headers=cd.headers,
                                      auth=requests_gssapi.HTTPSPNEGOAuth(opportunistic_auth=True))
                finally:
                    fp.stop()
            else:
                r = requests.post(url, data=cd, headers=cd.headers, auth=auth)
            if not 200 <= r.status_code < 300:
                raise LookasideCacheError('{0}: {1}'.format(r.reason, r.text.strip()))
            return r.content

        path = os.path.join(source_dir, filename)

        try:
            state = post(check_only=True)
        except (requests.exceptions.ConnectionError, LookasideCacheError) as e:
            # just log the error and bail out
            logger.error('Attempt to upload to lookaside cache failed: %s', str(e))
            return

        if state.strip() == b'Available':
            # already uploaded
            logger.info('%s is already present in lookaside cache, not uploading', path)
            return

        logger.info('Uploading %s to lookaside cache', path)
        try:
            try:
                post()
            finally:
                sys.stdout.write('\n')
                sys.stdout.flush()
        except (requests.exceptions.ConnectionError, LookasideCacheError) as e:
            # Skip error, the rebase can continue even after a failed upload
            logger.error("Upload to lookaside cache failed: %s", str(e))

    @classmethod
    def update_sources(cls, tool, basepath, package, old_sources, new_sources, upload=True, source_dir=''):
        try:
            config = cls._read_config(tool)
            url = config['lookaside_cgi']
            hashtype = config['lookasidehash']
        except (configparser.Error, KeyError) as e:
            raise LookasideCacheError('Failed to read rpkg configuration') from e
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
                if upload:
                    cls._upload_source(url, package, source_dir, filename, hashtype, hsh)
                uploaded.append(filename)
                sources[indexes[0]] = dict(hash=hsh, filename=filename, hashtype=hashtype)
        cls._write_sources(basepath, sources)
        return uploaded
