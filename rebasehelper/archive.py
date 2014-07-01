# -*- coding: utf-8 -*-

# This tool helps you to rebase package to the latest version
# Copyright (C) 2013 Petr Hracek
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

import tarfile
import zipfile
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
    def match(cls, *args, **kwargs):
        """
        Checks if the filename matches the archive type. If yes, returns
        True, otherwise returns False.
        """
        raise NotImplementedError()

    @classmethod
    def open(cls, *args, **kwargs):
        """
        Opens archive with the given filename and returns the proper
        archive type object.
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
        try:
            return tarfile.open(mode='r', fileobj=xz_file)
        except IOError as ioe:
            raise


@register_archive_type
class TarBz2ArchiveType(ArchiveTypeBase):
    """ .tar.bz2 archive type """
    EXTENSION = ".tar.bz2"

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
        try:
            return tarfile.TarFile.open(filename)
        except IOError as ioe:
            raise


@register_archive_type
class TarGzArchiveType(TarBz2ArchiveType):
    """ .tar.gz archive type """
    EXTENSION = ".tar.gz"
    EXTENSION2 = ".tgz"
    @classmethod
    def match(cls, filename=None):
        if filename is not None:
            if filename.endswith(cls.EXTENSION) or filename.endswith(cls.EXTENSION2):
                return True
            else:
                return False
        else:
            return False

    @classmethod
    def open(cls, filename=None):
        if filename is None:
            raise TypeError("Expected argument 'filename' (pos 1) is missing")
        try:
            return tarfile.TarFile.open(filename)
        except IOError as ioe:
            raise


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
        try:
            return zipfile.ZipFile(filename, "r")
        except IOError as ioe:
            raise


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

    def extract(self, path=None):
        if path is None:
            logger.info("Specify path where to extract sources.")
            raise
        """ Extracts the archive into the given path """
        logger.debug("Archive: Extracting '{0}' into '{1}'".format(
                     self._filename, path))
        try:
            archive = self._archive_type.open(self._filename)
        except IOError as ioe:
            raise
        archive.extractall(path)
        archive.close()
        return path
