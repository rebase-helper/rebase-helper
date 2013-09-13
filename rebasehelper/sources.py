# -*- coding: utf-8 -*-

import os
from rebasehelper.utils import PathHelper
from rebasehelper.utils import ProcessHelper
from rebasehelper.logger import logger

class Sources(object):
    """ Class representing sources that can be buit, installed, ... """
    SETUP_TYPE_CONFIGURE = "configure"
    SETUP_TYPE_CMAKE = "cmake"

    def __init__(self, path):
        self._abspath = os.path.abspath(path)
        self._setup_done = False        # was setup script run?
        self._build_done = False        # was Makefile run?
        if not os.path.isdir(self._abspath):
            raise ValueError("Given path is not a valid directory: {0}".format(path))
        self._setup_script_path, self._setup_script_type = self._find_setup()

    def _find_setup_path_configure(self):
        logger.debug("Sources: Looking for configure script in {0}".format(self.get_path()))
        script_path = PathHelper.find_file(self.get_path(), "configure")
        if script_path is not None:
            return os.path.dirname(script_path)
        else:
            return None

    def _find_setup_path_cmake(self):
        logger.debug("Sources: Looking for CMake script in {0}".format(self.get_path()))
        script_path = PathHelper.find_file(self.get_path(), "CMakeList.txt")
        if script_path is not None:
            return os.path.dirname(script_path)
        else:
            return None

    def _find_setup(self):
        functions = [(self.SETUP_TYPE_CONFIGURE, self._find_setup_path_configure),
                     (self.SETUP_TYPE_CMAKE, self._find_setup_path_cmake)]
        for setup_type, find_setup_path in functions:
            setup_path = find_setup_path()
            if setup_path is not None:
                logger.debug("Sources: Found {0} script in {1}".format(setup_type, setup_path))
                return setup_path, setup_type
        return None, None

    def get_path(self):
        return self._abspath

    def build(self):
        raise NotImplementedError("Not implemented yet")

    def _run_setup_configure(self, args=None, output=None):

        cmd = ["./configure"]
        if args is not None:
            cmd.extend(args)
        return ProcessHelper.run_subprocess_cwd(cmd,
                                                self._setup_script_path,
                                                output)

    def _run_setup_cmake(self, args=None, output=None):
        cmd = ["cmake"]
        if args is not None:
            cmd.extend(args)
        cmd.append(self._setup_script_path)
        return ProcessHelper.run_subprocess(cmd, output)


    def run_setup(self, args=None, output=None):
        functions = {self.SETUP_TYPE_CONFIGURE : self._run_setup_configure,
                     self.SETUP_TYPE_CMAKE : self._run_setup_cmake}
        if self._setup_script_path is not None and self._setup_script_type is not None:
            return functions[self._setup_script_type](args, output)
        else:
            logger.debug("Sources: Could not run script '{0}' in '{1}'".format(self._setup_script_type,
                         self._setup_script_path))
            return 1

