# -*- coding: utf-8 -*-

import tarfile
import zipfile

class Archive(object):
    """ Class representing an archive with sources """

    def __init__(self, filename):
        if tarfile.is_tarfile(filename):
            self._open = tarfile.TarFile.open
        elif zipfile.is_zipfile(filename):
            self._open = zipfile.ZipFile
        else:
            raise NotImplementedError("Unsupported archive type")
        self._filename = filename

    def extract(self, path="."):
        """ Extracts the archive into the given path """
        archive = self._open(self._filename)
        archive.extractall(path)
        archive.close()