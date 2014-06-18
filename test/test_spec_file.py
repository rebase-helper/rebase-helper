# -*- coding: utf-8 -*-

import os
import shutil
from rebasehelper import specfile
from rebasehelper import settings
from rebasehelper.logger import logger


class TestSpecHelper(object):
    """ SpecHelper tests """
    dir_name = ""
    spec_file = None
    test_spec = 'test.spec'
    result_dir = ""

    def setup(self):
        self.dir_name = os.path.dirname(__file__)
        self.result_dir = os.path.join(self.dir_name, settings.REBASE_RESULTS_DIR)
        if os.path.exists(self.result_dir):
            shutil.rmtree(self.result_dir)
        os.makedirs(self.result_dir)
        file_name = os.path.join(self.dir_name, self.test_spec)
        self.spec_file = specfile.SpecFile(file_name, '', download=False)
        self.spec_file.get_old_information()

    def teardown(self):
        if os.path.exists(self.result_dir):
            shutil.rmtree(self.result_dir)

    def test_spec_file(self):
        spec_path = os.path.join(self.dir_name,
                                           settings.REBASE_RESULTS_DIR,
                                           self.test_spec)
        assert os.path.exists(spec_path)

    def test_old_tarball(self):
        expected_tarball = 'test-1.0.2.tar.gz'
        test_tarball = self.spec_file.get_old_tarball()
        assert test_tarball == expected_tarball

    def test_all_sources(self):
        sources = ['test-source.sh', 'source-tests.sh', 'test-1.0.2.tar.gz']
        expected_sources = [os.path.join(os.getcwd(), x) for x in sources]
        test_sources = self.spec_file._get_all_sources()
        logger.info(test_sources)
        assert expected_sources == test_sources

    def test_list_patches(self):
        cwd = os.getcwd()
        dir_name = os.path.join(cwd, self.dir_name)
        expected_patches = {1: [os.path.join(dir_name, 'test-testing.patch' ), ' ', 0, False],
                            2: [os.path.join(dir_name, 'test-testing2.patch' ), '-p1', 1, False],
                            3: [os.path.join(dir_name, 'test-testing3.patch' ), '-p1', 2, False],
        }
        os.chdir(os.path.dirname(__file__))
        test_patches = self.spec_file._get_patches()
        os.chdir(cwd)
        assert expected_patches == test_patches
        
