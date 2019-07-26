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
import os
import re
import sys
import time

import requests
import requests_gssapi  # type: ignore

from urllib3.fields import RequestField  # type: ignore
from urllib3.filepost import encode_multipart_formdata  # type: ignore

from rebasehelper.exceptions import LookasideCacheError, DownloadError
from rebasehelper.logger import logger
from rebasehelper.helpers.download_helper import DownloadHelper


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
            url = '{0}/{1}/{2}/{3}/{4}/{2}'.format(url, package, filename, hashtype, hsh)
        else:
            url = '{0}/{1}/{2}/{3}/{2}'.format(url, package, filename, hsh)
        try:
            DownloadHelper.download_file(url, target)
        except DownloadError as e:
            raise LookasideCacheError(str(e))

    @classmethod
    def download(cls, tool, basepath, package, target_dir=None):
        try:
            config = cls._read_config(tool)
            url = config['lookaside']
        except (configparser.Error, KeyError):
            raise LookasideCacheError('Failed to read rpkg configuration')
        for source in cls._read_sources(basepath):
            target = os.path.join(target_dir, source['filename'])
            cls._download_source(tool, url, package, source['filename'], source['hashtype'], source['hash'], target)

    @classmethod
    def _upload_source(cls, url, package, source_dir, filename, hashtype, hsh, auth=requests_gssapi.HTTPSPNEGOAuth()):
        class ChunkedData:
            def __init__(self, check_only, chunksize=8192):
                self.check_only = check_only
                self.chunksize = chunksize
                self.start = time.time()
                self.uploaded = False
                fields = [
                    ('name', package),
                    ('{}sum'.format(hashtype), hsh),
                ]
                if check_only:
                    fields.append(('filename', filename))
                else:
                    with open(path, 'rb') as f:
                        rf = RequestField('file', f.read(), filename)
                        rf.make_multipart()
                        fields.append(rf)
                self.data, content_type = encode_multipart_formdata(fields)
                self.headers = {'Content-Type': content_type}

            def __iter__(self):
                if self.uploaded:
                    # ensure the progressbar is shown only once (HTTPSPNEGOAuth causes second request)
                    yield self.data
                else:
                    totalsize = len(self.data)
                    for offset in range(0, totalsize, self.chunksize):
                        transferred = min(offset + self.chunksize, totalsize)
                        if not self.check_only:
                            DownloadHelper.progress(totalsize, transferred, self.start)
                        yield self.data[offset:transferred]
                    self.uploaded = True

        def post(check_only=False):
            cd = ChunkedData(check_only)
            r = requests.post(url, data=cd, headers=cd.headers, auth=auth)
            if not 200 <= r.status_code < 300:
                raise LookasideCacheError(r.reason)
            return r.content

        path = os.path.join(source_dir, filename)
        state = post(check_only=True)
        if state.strip() == b'Available':
            # already uploaded
            return

        logger.info('Uploading %s to lookaside cache', path)
        try:
            post()
        finally:
            sys.stdout.write('\n')
            sys.stdout.flush()

    @classmethod
    def update_sources(cls, tool, basepath, package, old_sources, new_sources, upload=True, source_dir=''):
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
                if upload:
                    cls._upload_source(url, package, source_dir, filename, hashtype, hsh)
                uploaded.append(filename)
                sources[indexes[0]] = dict(hash=hsh, filename=filename, hashtype=hashtype)
        cls._write_sources(basepath, sources)
        return uploaded
