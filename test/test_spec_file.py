# -*- coding: utf-8 -*-

import os
import tempfile
import shutil
from rebasehelper import specfile


class TestSpecHelper(object):
    """ SpecHelper tests """
    print __file__
    specfile = "test.spec"
    def find_config_section(self):
        spec = specfile.Spec(specfile)
        assert spec.get_config_options()
        
    def find_make_section(self):
        spec = specfile.Spec(specfile)
        assert spec.get_make_options()

    def find_make_install_section(self):
        spec = specfile.Spec(specfile)
        assert spec.get_make_install_options()
