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
from __future__ import print_function
import tarfile
import zipfile
import bz2
import os
try:
    import lzma
except ImportError:
    from backports import lzma

from rebasehelper.logger import logger


# supported archive types
archive_types = {}


def register_archive_type(archive):
    archive_types[archive.EXTENSION] = archive
    return archive


class ArchiveTypeBase(object):

    """ Base class for various archive types """

    @classmethod
    def match(cls, filename=None, *args, **kwargs):
        """
        Checks if the filename matches the archive type. If yes, returns
        True, otherwise returns False.
        """
        raise NotImplementedError()

    @classmethod
    def open(cls, filename=None, *args, **kwargs):
        """
        Opens archive with the given filename and returns the proper
        archive type object.
        """
        raise NotImplementedError()

    @classmethod
    def extract(cls, filename=None, *args, **kwargs):
        """
        Extracts the archive into the given path

        :param path: Path where to extract the archive to.
        :return:
        """
        raise NotImplementedError()

@register_archive_type
class TarXzArchiveType(ArchiveTypeBase):

    """ .tar.xz archive type """

    EXTENSION = ".tar.xz"

    @classmethod
    def match(cls, filename=None):
        if filename is not None and filename.endswith(cls.EXTENSION):
            return True
        else:
            return False

    @classmethod
    def open(cls, filename=None):
        if filename is None:
            raise TypeError("Expected argument 'filename' (pos 1) is missing")
        xz_file = lzma.LZMAFile(filename, "r")

        return tarfile.open(mode='r', fileobj=xz_file)

    @classmethod
    def extract(cls, archive=None, filename=None, path=None, *args, **kwargs):
        if archive is None:
            raise TypeError("Expected argument 'archive' (pos 1) is missing")
        archive.extractall(path)

@register_archive_type
class TarBz2ArchiveType(ArchiveTypeBase):

    """ .bz2 archive type """

    EXTENSION = ".bz2"

    @classmethod
    def match(cls, filename=None):
        if filename is not None and filename.endswith(cls.EXTENSION):
            return True
        else:
            return False

    @classmethod
    def open(cls, filename=None):
        if filename is None:
            raise TypeError("Expected argument 'filename' (pos 1) is missing")

        if filename.endswith('.tar.bz2'):
            return tarfile.TarFile.open(filename)
        else:
            return bz2.BZ2File(filename)

    @classmethod
    def extract(cls, archive=None, filename=None, path=None, *args, **kwargs):
        if archive is None:
            raise TypeError("Expected argument 'archive' (pos 1) is missing")
        if filename.endswith('tar.bz2'):
            archive.extractall(path)
        else:
            data = archive.read()
            os.mkdir(path)
            with open(os.path.join(path, filename[:-4]), 'w') as f:
                f.write(data)


@register_archive_type
class TarGzArchiveType(TarBz2ArchiveType):

    """ .tar.gz archive type """

    EXTENSION = ".tar.gz"

    @classmethod
    def match(cls, filename=None):
        if filename is not None and filename.endswith(cls.EXTENSION):
            return True
        else:
            return False

    @classmethod
    def open(cls, filename=None):
        if filename is None:
            raise TypeError("Expected argument 'filename' (pos 1) is missing")

        return tarfile.TarFile.open(filename)

    @classmethod
    def extract(cls, archive=None, filename=None, path=None, *args, **kwargs):
        if archive is None:
            raise TypeError("Expected argument 'archive' (pos 1) is missing")
        archive.extractall(path)

@register_archive_type
class TgzArchiveType(TarGzArchiveType):
    """ .tgz archive type """
    EXTENSION = ".tgz"

    @classmethod
    def match(cls, filename=None):
        if filename is not None and filename.endswith(cls.EXTENSION):
            return True
        else:
            return False


@register_archive_type
class ZipArchiveType(ArchiveTypeBase):
    """ .zip archive type """
    EXTENSION = ".zip"

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
    def extract(cls, archive=None, filename=None, path=None, *args, **kwargs):
        if archive is None:
            raise TypeError("Expected argument 'archive' (pos 1) is missing")
        archive.extractall(path)


class Archive(object):

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

        logger.debug("Extracting '%s' into '%s'", self._filename, path)

        archive = self._archive_type.open(self._filename)
        self._archive_type.extract(archive, self._filename, path)
        archive.close()

    @classmethod
    def get_supported_archives(cls):
        """ Return list of supported archive types """
        return archive_types.keys()
