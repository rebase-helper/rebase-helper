# -*- coding: utf-8 -*-

import tarfile
import zipfile
import lzma
from rebasehelper import settings
from rebasehelper.logger import logger

class Archive(object):
    """ Class representing an archive with sources """
    _filename = None
    _archive = None
    def __init__(self, filename):
        self._filename = filename
        if self._filename.endswith(".tar.xz"):
            xz_file = lzma.LZMAFile(self._filename,"r")
            self._archive = tarfile.open(mode='r',fileobj=xz_file)
        elif self._filename.endswith(".tar.bz2") or self._filename.endswith("tar.gz"):
            self._archive = tarfile.TarFile.open(self._filename)
        elif zipfile.is_zipfile(filename):
            self._archive = zipfile.ZipFile(self._filename,"r")
        else:
            raise NotImplementedError("Unsupported archive type")

    def extract(self, path=settings.TEMPLATE_DIR):
        """ Extracts the archive into the given path """
        logger.info("extracting {0}".format(self._filename))
        self._archive.extractall(path)
        self._archive.close()

