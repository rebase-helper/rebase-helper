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
import sys
import time
import urllib.error
import urllib.request

import requests

from rebasehelper.exceptions import DownloadError
from rebasehelper.logger import logger


class DownloadHelper:

    """Class for downloading files and performing HTTP requests."""

    @staticmethod
    def progress(download_total, downloaded, start_time):
        """Prints current progress and estimated remaining time of a download to the standard output.

        Args:
            download_total (int): Total download size in bytes.
            downloaded (int): Size of the already downloaded portion of a file in bytes.
            start_time (float): Time when the download started in seconds since epoch.

        """
        bar_width = 32
        infinite_step = 256 * 1024  # move every 256 kilobytes

        delta = time.time() - start_time

        def format_time(t):
            h, rem = divmod(int(t), 3600)
            m, s = divmod(rem, 60)
            return '{:0>2d}:{:0>2d}:{:0>2d}'.format(h, m, s)

        def format_size(s):
            units = [' ', 'K', 'M', 'G', 'T']
            i = 0
            while s >= 1024.0 and i < len(units) - 1:
                s /= 1024.0
                i += 1
            return '{:>7.2F}{}'.format(s, units[i])

        if download_total < 0:
            # infinite progress bar
            pct = ' ' * 4
            pos = int(downloaded / infinite_step) % (bar_width - 5)
            bar = '[{}<=>{}]'.format(' ' * pos, ' ' * (bar_width - 5 - pos))
            ts = ' in {}'.format(format_time(delta))
        else:
            r = float(downloaded) / float(download_total) if download_total else 0.0
            pct = '{:>3d}%'.format(int(r * 100))
            pos = int(r * (bar_width - 3))
            bar = '[{}>{}]'.format('=' * pos, ' ' * (bar_width - 3 - pos))
            ts = 'eta {}'.format(format_time(delta / r - delta) if r > 0.0 else ' ' * 7 + '?')

        size = format_size(downloaded)

        # no point to log progress, write directly to stdout
        sys.stdout.write('\r{}{}  {}  {} '.format(pct, bar, size, ts))
        sys.stdout.flush()

    @staticmethod
    def request(url, **kwargs):
        """Performs an HTTP request or an FTP RETR command.

        Args:
            url (str): HTTP, HTTPS or FTP URL.
            **kwargs: Keyword arguments to be passed to requests.session.get().

        Returns:
            requests.Response: Response object.

        """

        class FTPAdapter(requests.adapters.BaseAdapter):

            def send(self, request, stream=False, timeout=None, verify=True,  # pylint: disable=unused-argument
                     cert=None, proxies=None):  # pylint: disable=unused-argument
                response = requests.models.Response()
                response.request = request
                response.connection = self
                try:
                    resp = urllib.request.urlopen(request.url)
                except urllib.error.URLError as e:
                    response.status_code = 400
                    response.reason = e.reason
                else:
                    response.status_code = 200
                    response.headers = requests.structures.CaseInsensitiveDict(getattr(resp, 'headers', {}))
                    response.raw = resp
                    response.url = resp.url
                return response

            def close(self):
                pass

        session = requests.Session()
        session.mount('ftp://', FTPAdapter())

        try:
            return session.get(url, **kwargs)
        except requests.exceptions.RequestException as e:
            logger.error('%s: %s', type(e).__name__, str(e))
            return None

    @staticmethod
    def download_file(url, destination_path, blocksize=8192):
        """Downloads a file from HTTP, HTTPS or FTP URL.

        Args:
            url (str): URL to be downloaded.
            destination_path (str): Path to where the downloaded file will be stored.
            blocksize (int): Block size in bytes.

        """
        r = DownloadHelper.request(url, stream=True)
        if r is None:
            raise DownloadError("An unexpected error occurred during the download.")

        if not 200 <= r.status_code < 300:
            raise DownloadError(r.reason)

        file_size = int(r.headers.get('content-length', -1))

        # file exists, check the size
        if os.path.exists(destination_path):
            if file_size < 0 or file_size != os.path.getsize(destination_path):
                logger.verbose("The destination file '%s' exists, but sizes don't match! Removing it.",
                               destination_path)
                os.remove(destination_path)
            else:
                logger.verbose("The destination file '%s' exists, and the size is correct! Skipping download.",
                               destination_path)
                return
        try:
            with open(destination_path, 'wb') as local_file:
                logger.info('Downloading file from URL %s', url)
                download_start = time.time()
                downloaded = 0

                # report progress
                DownloadHelper.progress(file_size, downloaded, download_start)

                # do the actual download
                for chunk in r.iter_content(chunk_size=blocksize):
                    downloaded += len(chunk)
                    local_file.write(chunk)

                    # report progress
                    DownloadHelper.progress(file_size, downloaded, download_start)

                sys.stdout.write('\n')
                sys.stdout.flush()
        except KeyboardInterrupt as e:
            os.remove(destination_path)
            raise e
