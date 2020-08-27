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
import logging
import lzma
import os
import shutil
import tarfile
import zipfile
from typing import Dict, Type, cast

from rebasehelper.logger import CustomLogger
from rebasehelper.helpers.path_helper import PathHelper


logger: CustomLogger = cast(CustomLogger, logging.getLogger(__name__))


# supported archive types
archive_types: Dict[str, Type['ArchiveTypeBase']] = {}


def register_archive_type(archive):
    archive_types[archive.EXTENSION] = archive
    return archive


class ArchiveTypeBase:
    """Base class for various archive types"""

    EXTENSION: str = ''

    @classmethod
    def match(cls, filename):
        """
        Checks if the filename matches the archive type. If yes, returns
        True, otherwise returns False.
        """
        return filename.endswith(cls.EXTENSION)

    @classmethod
    def open(cls, filename):
        """
        Opens archive with the given filename and returns the proper
        archive type object.
        """
        raise NotImplementedError()

    @classmethod
    def extract(cls, archive, filename, path):
        """
        Extracts the archive into the given path

        :param path: Path where to extract the archive to.
        :return:
        """
        raise NotImplementedError()


@register_archive_type
class TarXzArchiveType(ArchiveTypeBase):
    EXTENSION: str = '.tar.xz'

    @classmethod
    def open(cls, filename):
        return tarfile.open(mode='r', fileobj=lzma.LZMAFile(filename, 'r'))

    @classmethod
    def extract(cls, archive, filename, path):
        archive.extractall(path)


@register_archive_type
class TarBz2ArchiveType(ArchiveTypeBase):
    EXTENSION: str = '.tar.bz2'

    @classmethod
    def open(cls, filename):
        if filename.endswith(TarBz2ArchiveType.EXTENSION):
            return tarfile.TarFile.open(filename)
        else:
            return bz2.BZ2File(filename)

    @classmethod
    def extract(cls, archive, filename, path):
        if filename.endswith(TarBz2ArchiveType.EXTENSION):
            archive.extractall(path)
        else:
            data = archive.read()
            if not os.path.exists(path):
                os.mkdir(path)
            with open(os.path.join(path, os.path.basename(filename[:-len(cls.EXTENSION)])), 'wb') as f:
                f.write(data)


@register_archive_type
class Bz2ArchiveType(TarBz2ArchiveType):
    EXTENSION: str = '.bz2'


@register_archive_type
class TarGzArchiveType(TarBz2ArchiveType):
    EXTENSION: str = '.tar.gz'

    @classmethod
    def open(cls, filename):
        return tarfile.TarFile.open(filename)

    @classmethod
    def extract(cls, archive, filename, path):
        archive.extractall(path)


@register_archive_type
class TgzArchiveType(TarGzArchiveType):
    EXTENSION: str = '.tgz'


@register_archive_type
class TarArchiveType(TarGzArchiveType):
    EXTENSION: str = '.tar'


@register_archive_type
class CrateArchiveType(TarGzArchiveType):
    EXTENSION: str = '.crate'


@register_archive_type
class ZipArchiveType(ArchiveTypeBase):
    EXTENSION: str = '.zip'

    @classmethod
    def match(cls, filename):
        return zipfile.is_zipfile(filename)

    @classmethod
    def open(cls, filename):
        return zipfile.ZipFile(filename, 'r')

    @classmethod
    def extract(cls, archive, filename, path):
        archive.extractall(path)


@register_archive_type
class GemArchiveType(ArchiveTypeBase):
    EXTENSION: str = '.gem'

    class GemArchive:
        def __init__(self, filename):
            self.tmp = PathHelper.get_temp_dir()
            TarArchiveType.extract(TarArchiveType.open(filename), '', self.tmp)
            self.data = TarGzArchiveType.open(os.path.join(self.tmp, 'data.tar.gz'))

        def extract(self, path):
            TarGzArchiveType.extract(self.data, '', path)

        def close(self):
            self.data.close()
            shutil.rmtree(self.tmp, onerror=lambda func, path, excinfo: shutil.rmtree(path))

    @classmethod
    def open(cls, filename):
        return cls.GemArchive(filename)

    @classmethod
    def extract(cls, archive, filename, path):
        tld = os.path.join(path, os.path.basename(filename[:-len(cls.EXTENSION)]))
        os.makedirs(tld)
        archive.extract(tld)


class Archive:
    """Class representing an archive with sources"""

    def __init__(self, filename):
        self._filename = filename
        self._archive_type = None

        for archive_type in archive_types.values():
            if archive_type.match(self._filename):
                self._archive_type = archive_type

        if self._archive_type is None:
            raise NotImplementedError('Unsupported archive type')

    def extract_archive(self, path):
        """
        Extracts the archive into the given path

        :param path: Path where to extract the archive to.
        """
        logger.verbose('Extracting %s to %s', self._filename, path)

        try:
            archive = self._archive_type.open(self._filename)
        except (EOFError, tarfile.ReadError, lzma.LZMAError) as e:
            raise IOError(str(e)) from e

        try:
            self._archive_type.extract(archive, self._filename, path)
        finally:
            archive.close()

    @classmethod
    def get_supported_archives(cls):
        return archive_types.keys()
