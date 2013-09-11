# -*- coding: utf-8 -*-

import tarfile
import zipfile
import lzma
from rebasehelper import settings
from rebasehelper.logger import logger

class Archive(object):
    """ Class representing an archive with sources """
    filename = None
    archive = None
    def __init__(self, filename):
        self.filename = filename
        if self.filename.endswith(".tar.xz"):
            xz_file = lzma.LZMAFile(self.filename,"r")
            self.archive = tarfile.open(mode='r',fileobj=xz_file)
        elif self.filename.endswith(".tar.bz2") or self.filename.endswith("tar.gz"):
            self.archive = tarfile.TarFile.open(self.filename)
        elif zipfile.is_zipfile(filename):
            self._open = zipfile.ZipFile
        else:
            raise NotImplementedError("Unsupported archive type")
        self._filename = filename

    def extract(self, path=settings.TEMPLATE_DIR):
        """ Extracts the archive into the given path """
        logger.info("extracting {0}".format(self.filename))
        self.archive.extractall(path)
        self.archive.close()

