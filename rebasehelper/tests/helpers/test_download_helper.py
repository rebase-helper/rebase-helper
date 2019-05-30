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

import io
import os

import pytest  # type: ignore

from rebasehelper.helpers.download_helper import DownloadHelper, DownloadError


class TestDownloadHelper:
    """ DownloadHelper tests """

    def test_keyboard_interrupt_situation(self, monkeypatch):
        """
        Test that the local file is deleted in case KeyboardInterrupt is raised during the download
        """
        KNOWN_URL = 'https://ftp.isc.org/isc/bind9/9.10.4-P1/srcid'
        LOCAL_FILE = os.path.basename(KNOWN_URL)

        def interrupter():
            raise KeyboardInterrupt

        # make sure that some function call inside tha actual download section raises the KeyboardInterrupt exception.
        monkeypatch.setattr('time.time', interrupter)

        with pytest.raises(KeyboardInterrupt):
            DownloadHelper.download_file(KNOWN_URL, LOCAL_FILE)

        assert not os.path.exists(LOCAL_FILE)

    @pytest.mark.parametrize('total, downloaded, output', [
        (100, 25, '\r 25%[=======>                      ]    25.00   eta 00:00:30 '),
        (100.0, 25.0, '\r 25%[=======>                      ]    25.00   eta 00:00:30 '),
        (-1, 1024 * 1024, '\r    [    <=>                       ]     1.00M   in 00:00:10 '),
    ], ids=[
        'integer',
        'float',
        'unknown_size',
    ])
    def test_progress(self, total, downloaded, output, monkeypatch):
        """
        Test that progress of a download is shown correctly. Test the case when size parameters are passed as integers.
        """
        buf = io.StringIO()
        monkeypatch.setattr('sys.stdout', buf)
        monkeypatch.setattr('time.time', lambda: 10.0)
        DownloadHelper.progress(total, downloaded, 0.0)
        assert buf.getvalue() == output

    @pytest.mark.parametrize('url, content', [
        ('http://integration:8000/existing_file.txt', 'content'),
        ('https://integration:4430/existing_file.txt', 'content'),
        ('ftp://integration:2100/existing_file.txt', 'content'),
        ('http://integration:8001/existing_file.txt', 'content'),
        ('https://integration:4431/existing_file.txt', 'content'),
        ('ftp://integration:2101/existing_file.txt', 'content'),
    ], ids=[
        'HTTP',
        'HTTPS',
        'FTP',
        'HTTP-unknown_size',
        'HTTPS-unknown_size',
        'FTP-unknown_size',
    ])
    @pytest.mark.integration
    def test_download_existing_file(self, url, content):
        """Test downloading existing file"""
        local_file = 'local_file'
        DownloadHelper.download_file(url, local_file)
        assert os.path.isfile(local_file)
        with open(local_file) as f:
            assert f.readline().strip() == content

    @pytest.mark.parametrize('url', [
        'http://integration:8000/non_existing_file.txt',
        'https://integration:4430/non_existing_file.txt',
        'ftp://integration:2100/non_existing_file.txt',
    ], ids=[
        'HTTP',
        'HTTPS',
        'FTP',
    ])
    @pytest.mark.integration
    def test_download_non_existing_file(self, url):
        """Test downloading NON existing file"""
        local_file = 'local_file'
        with pytest.raises(DownloadError):
            DownloadHelper.download_file(url, local_file)
        assert not os.path.isfile(local_file)
