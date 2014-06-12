# -*- coding: utf-8 -*-

import os
import shutil
from rebasehelper import specfile
from rebasehelper import settings
from rebasehelper.logger import logger
from rebasehelper.archive import *
from rebasehelper.utils import get_content_file


class TestArchive(object):
    """ Archive Test"""
    TAR_GZ = "tar_gz"
    TAR_XZ = "tar_xz"
    ZIP = "zip"
    TAR_BZ2 = "tar_bz2"
    list_archives = {TAR_BZ2: tarfile.TarFile,
                     TAR_GZ: tarfile.TarFile,
                     TAR_XZ: lzma.LZMAFile,
                     ZIP: zipfile.ZipFile
                     }
    list_names = {TAR_BZ2: 'tar_bz2.tar.bz2',
                  TAR_GZ: 'tar_gz.tar.gz',
                  TAR_XZ: 'tar_xz.tar.xz',
                  ZIP: 'zip.zip'
                  }
    dir_name = os.path.join(os.path.dirname(__file__))
    extr = "extract"
    test_file = 'test_file'

    def extract_sources(self, name):
        archive_name = os.path.join(self.dir_name, self.list_names[name])
        archive_dir = os.path.join(self.dir_name, self.extr + "-" + name)
        archive = Archive(archive_name)
        archive.extract(archive_dir)
        return archive_dir

    def get_extract_file(self, archive_dir):
        lines = get_content_file(os.path.join(archive_dir, self.test_file),
                                 'r',
                                 method=True)
        return lines

    def setup(self):
        for key, value in self.list_archives.iteritems():
            arch_name = os.path.join(self.dir_name, self.list_names[key])
            if key == self.TAR_XZ:
                xz_file = value(arch_name, 'w')
                archive = tarfile.open(mode='w', fileobj=xz_file)
                for file_name in os.listdir(os.path.join(self.dir_name, key)):
                    archive.add(os.path.join('test', key, file_name))
            elif key == self.ZIP:
                archive = value(arch_name, 'w', zipfile.ZIP_DEFLATED)
                for root, dirs, files in os.walk(os.path.join(self.dir_name, key)):
                    archive.write(root, '.')
                    for file_name in files:
                        filePath = os.path.join(root, file_name)
                        inzipFile = filePath.replace(self.dir_name, "", 1).lstrip("\\/")
                        archive.write(filePath, inzipFile)
                archive.close()
            elif key == self.TAR_GZ:
                archive = value.open(arch_name, 'w:gz')
                for file_name in os.listdir(os.path.join(self.dir_name, key)):
                    archive.add(os.path.join(self.dir_name, key, file_name), arcname=file_name)
                archive.close()
            elif key == self.TAR_BZ2:
                archive = value.open(arch_name, 'w:bz2')
                for file_name in os.listdir(os.path.join(self.dir_name, key)):
                    archive.add(os.path.join(self.dir_name, key, file_name), arcname=file_name)
                archive.close()
        assert True

    def teardown(self):
        for key, value in self.list_archives.iteritems():
            arch_name = os.path.join(self.dir_name, self.list_names[key])
            #if os.path.exists(arch_name):
            #    os.unlink(arch_name)
            dir_name = os.path.join(self.dir_name, self.extr + "-" + key)
            #if os.path.isdir(dir_name):
            #    shutil.rmtree(dir_name)

    def test_bz2_archive(self):
        archive_dir = self.extract_sources(self.TAR_BZ2)
        assert os.path.isdir(archive_dir)
        lines = self.get_extract_file(archive_dir)
        expected_contain = "{0} archive".format(self.TAR_BZ2.replace('_', '.'))
        assert lines[0].strip() == expected_contain

    def test_gz_archive(self):
        archive_dir = self.extract_sources(self.TAR_GZ)
        assert os.path.isdir(archive_dir)
        lines = self.get_extract_file(archive_dir)
        expected_contain = "{0} archive".format(self.TAR_GZ.replace('_', '.'))
        assert lines[0].strip() == expected_contain

    def test_zip_archive(self):
        archive_dir = self.extract_sources(self.ZIP)
        assert os.path.isdir(archive_dir)
        lines = self.get_extract_file(archive_dir)
        expected_contain = "{0} archive".format(self.ZIP.replace('_', '.'))
        assert lines[0].strip() == expected_contain

    #def test_xz_archive(self):
    #    archive_name = os.path.join(self.dir_name, self.list_names[self.TAR_XZ])
    #    archive_dir = os.path.join(self.dir_name, self.extr+self.TAR_XZ)
    #    logger.info(archive_dir)
    #    archive = Archive(archive_name)
    #    archive.extract(archive_dir)
