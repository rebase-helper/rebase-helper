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

import bz2
import lzma
import os
import tarfile
import zipfile

from typing import Dict, Type

from rebasehelper.logger import logger


# supported archive types
archive_types: Dict[str, Type['ArchiveTypeBase']] = {}


def register_archive_type(archive):
    archive_types[archive.EXTENSION] = archive
    return archive


class ArchiveTypeBase:
    """ Base class for various archive types """

    EXTENSION: str = ''

    @classmethod
    def match(cls, filename=None):
        """
        Checks if the filename matches the archive type. If yes, returns
        True, otherwise returns False.
        """
        if filename is not None and filename.endswith(cls.EXTENSION):
            return True
        else:
            return False

    @classmethod
    def open(cls, filename=None):
        """
        Opens archive with the given filename and returns the proper
        archive type object.
        """
        raise NotImplementedError()

    @classmethod
    def extract(cls, archive=None, filename=None, path=None):
        """
        Extracts the archive into the given path

        :param path: Path where to extract the archive to.
        :return:
        """
        raise NotImplementedError()


@register_archive_type
class TarXzArchiveType(ArchiveTypeBase):

    """ .tar.xz archive type """

    EXTENSION: str = '.tar.xz'

    @classmethod
    def open(cls, filename=None):
        if filename is None:
            raise TypeError("Expected argument 'filename' (pos 1) is missing")
        xz_file = lzma.LZMAFile(filename, "r")

        return tarfile.open(mode='r', fileobj=xz_file)

    @classmethod
    def extract(cls, archive=None, filename=None, path=None):
        if archive is None:
            raise TypeError("Expected argument 'archive' (pos 1) is missing")
        archive.extractall(path)


@register_archive_type
class Bz2ArchiveType(ArchiveTypeBase):

    """ .bz2 archive type """

    EXTENSION: str = '.bz2'

    @classmethod
    def open(cls, filename=None):
        if filename is None:
            raise TypeError("Expected argument 'filename' (pos 1) is missing")

        if filename.endswith('.tar.bz2'):
            return tarfile.TarFile.open(filename)
        else:
            return bz2.BZ2File(filename)

    @classmethod
    def extract(cls, archive=None, filename=None, path=None):
        if archive is None:
            raise TypeError("Expected argument 'archive' (pos 1) is missing")
        if filename.endswith('tar.bz2'):
            archive.extractall(path)
        else:
            data = archive.read()
            if not os.path.exists(path):
                os.mkdir(path)
            with open(os.path.join(path, filename[:-4]), 'wb') as f:
                f.write(data)


@register_archive_type
class TarBz2ArchiveType(Bz2ArchiveType):

    """ .tar.bz2 archive type """

    EXTENSION: str = '.tar.bz2'


@register_archive_type
class TarGzArchiveType(TarBz2ArchiveType):

    """ .tar.gz archive type """

    EXTENSION: str = '.tar.gz'

    @classmethod
    def open(cls, filename=None):
        if filename is None:
            raise TypeError("Expected argument 'filename' (pos 1) is missing")

        return tarfile.TarFile.open(filename)

    @classmethod
    def extract(cls, archive=None, filename=None, path=None):
        if archive is None:
            raise TypeError("Expected argument 'archive' (pos 1) is missing")
        archive.extractall(path)


@register_archive_type
class TgzArchiveType(TarGzArchiveType):
    """ .tgz archive type """

    EXTENSION: str = '.tgz'


@register_archive_type
class TarArchiveType(TarGzArchiveType):
    """ .tar archive type """

    EXTENSION: str = '.tar'


@register_archive_type
class ZipArchiveType(ArchiveTypeBase):
    """ .zip archive type """

    EXTENSION: str = '.zip'

    @classmethod
    def match(cls, filename=None):
        if filename is not None and zipfile.is_zipfile(filename):
            return True
        else:
            return False

    @classmethod
    def open(cls, filename=None):
        if filename is None:
            raise TypeError("Expected argument 'filename' (pos 1) is missing")

        return zipfile.ZipFile(filename, "r")

    @classmethod
    def extract(cls, archive=None, filename=None, path=None):
        if archive is None:
            raise TypeError("Expected argument 'archive' (pos 1) is missing")
        archive.extractall(path)


class Archive:

    """ Class representing an archive with sources """

    def __init__(self, filename=None):
        if filename is None:
            raise TypeError("Expected argument 'filename' (pos 1) is missing")
        self._filename = filename
        self._archive_type = None

        for archive_type in archive_types.values():
            if archive_type.match(self._filename):
                self._archive_type = archive_type

        if self._archive_type is None:
            raise NotImplementedError("Unsupported archive type")

    def extract_archive(self, path=None):
        """
        Extracts the archive into the given path

        :param path: Path where to extract the archive to.
        :return:
        """
        if path is None:
            TypeError("Expected argument 'path' (pos 1) is missing")

        logger.verbose("Extracting '%s' into '%s'", self._filename, path)

        try:
            archive = self._archive_type.open(self._filename)
        except (EOFError, tarfile.ReadError, lzma.LZMAError) as e:
            raise IOError(str(e))

        self._archive_type.extract(archive, self._filename, path)
        try:
            archive.close()
        except AttributeError:
            # pseudo archive types don't return real file-like object
            pass

    @classmethod
    def get_supported_archives(cls):
        """Return list of supported archive types"""
        return archive_types.keys()
