# -*- coding: utf-8 -*-
#
# This tool helps you to rebase package to the latest version
# Copyright (C) 2013-2014 Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# he Free Software Foundation; either version 2 of the License, or
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

import os
from .base_test import BaseTest
from rebasehelper.archive import Archive


class TestArchive(BaseTest):
    """ Archive Test """
    TAR_GZ = 'archive.tar.gz'
    TGZ = 'archive.tgz'
    TAR_XZ = 'archive.tar.xz'
    TAR_BZ2 = 'archive.tar.bz2'
    ZIP = 'archive.zip'

    ARCHIVED_FILE = 'file.txt'
    ARCHIVED_FILE_CONTENT = 'simple testing file'

    #  These files located in TEST_FILES_DIR will be copied into the testing environment
    TEST_FILES = [
        TAR_GZ,
        TGZ,
        TAR_XZ,
        TAR_BZ2,
        ZIP
    ]

    def extraction_test(self, archive):
        """
        Generic test for extraction of all types of archives
        """
        EXTRACT_DIR = os.path.join(os.getcwd(), 'dir')
        EXTRACTED_FILE = os.path.join(EXTRACT_DIR, self.ARCHIVED_FILE)

        archive = Archive(archive)
        archive.extract(EXTRACT_DIR)

        #  check if the dir was created
        assert os.path.isdir(EXTRACT_DIR)
        #  check if the file was extracted
        assert os.path.isfile(EXTRACTED_FILE)
        #  check the content
        with open(EXTRACTED_FILE) as f:
            assert f.read().strip() == self.ARCHIVED_FILE_CONTENT

    def test_tar_bz2_archive(self):
        """
        Test .tar.bz2 archive extraction.
        """
        self.extraction_test(self.TAR_BZ2)

    def test_tar_gz_archive(self):
        """
        Test .tar.gz archive extraction.
        """
        self.extraction_test(self.TAR_GZ)

    def test_tgz_archive(self):
        """
        Test .tgz archive extraction.
        """
        self.extraction_test(self.TGZ)

    def test_tar_xz_archive(self):
        """
        Test .tar.xz archive extraction.
        """
        self.extraction_test(self.TAR_XZ)

    def test_zip_archive(self):
        """
        Test .zip archive extraction.
        """
        self.extraction_test(self.ZIP)
