# -*- coding: utf-8 -*-

import os
from rebasehelper import specfile


class TestSpecHelper(object):
    """ SpecHelper tests """
    def test_spec_file(self):
        assert os.path.exists(self.specfile)
        
    def test_config_section(self):
        spec = specfile.Specfile(self.specfile)
        assert spec.get_config_options()
        
    def test_make_section(self):
        spec = specfile.Specfile(self.specfile)
        assert spec.get_make_options() == self.MAKE

    def test_make_install_section(self):
        spec = specfile.Specfile(self.specfile)
        assert spec.get_make_install_options() == self.MAKE_INSTALL

    def test_list_patches(self):
        
