# -*- coding: utf-8 -*-

import os
import fnmatch

class Sources(object):
    """ Class representing sources that can be buit, installed, ... """

    def __init__(self, path):
        self._abspath = os.path.abspath(path)
        self._setup_done = False        # was setup script run?
        self._build_done = False        # was Makefile run?
        if not os.path.isdir(self._abspath):
            raise ValueError("Given path is not a valid directory: {0}".format(path))
        self._setup = self._find_setup()

    def _find_file(self, top_path, patern):
        """ Finds a file that matches the given 'patern' recursively
        starting in the 'top_path' directory. If found, returns full path
        to the first occurance of the file, otherwise returns None. """
        for root, dirs, files in os.walk(top_path):
            for f in files:
                if fnmatch.fnmatch(f, patern):
                    return os.path.join(root, f)
        return None

    def _find_setup_configure(self):
        return self._find_file(self.get_path(), "configure")

    def _find_setup_cmake(self):
        return self._find_file(self.get_path(), "CMakeList.txt")

    def _find_setup(self):
        functions = [self._find_setup_configure,
                     self._find_setup_cmake]
        for func in functions:
            setup = func()
            if setup is not None:
                return setup
        return None

    def get_path(self):
        return self._abspath

    def build(self):
        raise NotImplementedError("Not implemented yet")

    def run_setup(self, args=None):
        raise NotImplementedError("Not implemented yet")
