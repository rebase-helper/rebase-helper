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
        if not os.path.isdir(self._abspath):
            raise ValueError(
                "Given path is not a valid directory: {0}".format(path))
        self._setup_done = False
        self._build_done = False
        self._setup_script_path = None
        self._setup_script_type = None
        self._makefile_path = None

    def _find_setup_path_configure(self):
        logger.debug("Sources: Looking for configure script in {0}".format(
            self.get_path()))
        return PathHelper.find_first_dir_with_file(self.get_path(), "configure")

    def _find_setup_path_cmake(self):
        logger.debug("Sources: Looking for CMake script in {0}".format(
            self.get_path()))
        return PathHelper.find_first_dir_with_file(self.get_path(), "CMakeList.txt")

    def _find_setup(self):
        functions = [(
            self.SETUP_TYPE_CONFIGURE, self._find_setup_path_configure),
            (self.SETUP_TYPE_CMAKE, self._find_setup_path_cmake)]
        for setup_type, find_setup_path in functions:
            setup_path = find_setup_path()
            if setup_path is not None:
                logger.debug("Sources: Found {0} script in {1}".format(
                    setup_type, setup_path))
                return setup_path, setup_type
        return None, None

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
        cmd.append(".")
        return ProcessHelper.run_subprocess_cwd(cmd,
                                                self._setup_script_path,
                                                output)

    def setup(self, args=None, output=None):
        """Runs setup script with given list of arguments and writes script
        output to the given file"""
        functions = {self.SETUP_TYPE_CONFIGURE: self._run_setup_configure,
                     self.SETUP_TYPE_CMAKE: self._run_setup_cmake}
        if not self._setup_script_path or not self._setup_script_type:
            self._setup_script_path, self._setup_script_type = self._find_setup()
        if self._setup_script_path and self._setup_script_type:
            ret = functions[self._setup_script_type](args, output)
            if ret == 0:
                self._setup_done = True
                return True
            else:
                logger.debug("Sources: Setup script failed")
                return False
        else:
            logger.debug("Sources: Could not find setup script")
            return False

    def get_path(self):
        return self._abspath

    def _find_makefile(self):
        logger.debug(
            "Sources: Looking for Makefile in {0}".format(self.get_path()))
        return PathHelper.find_first_dir_with_file(self.get_path(), "Makefile")

    def _pre_make_check(self):
        if self._setup_done is False:
            logger.debug(
                "Sources: Setup script needs to be executed before make")
            return False
        if self._makefile_path is None:
            self._makefile_path = self._find_makefile()
        if self._makefile_path is None:
            logger.debug("Sources: Could not find Makefile")
            return False
        return True

    def build(self, args=None, output=None):
        """Runs make with the given list of argumens and writes make output
        to the given file"""
        if self._pre_make_check() is False:
            return False
        cmd = ["make"]
        if args is not None:
            cmd.extend(args)
        ret = ProcessHelper.run_subprocess_cwd(cmd,
                                               self._makefile_path,
                                               output)
        if ret == 0:
            self._build_done = True
            return True
        else:
            logger.debug("Sources: Building failed")
            return False

    def install(self, path=None, output=None):
        """Runs make install with DESTDIR='path' and writes output to the given
        file"""
        if self._pre_make_check() is False:
            return False
        if self._build_done is False:
            logger.debug("Sources: Sources need to be built before intsall")
            return False
        cmd = ["make", "install"]
        if path is not None:
            cmd.append("DESTDIR=" + path)
        ret = ProcessHelper.run_subprocess_cwd(cmd,
                                               self._makefile_path,
                                               output)
        if ret == 0:
            return True
        else:
            logger.debug("Sources: 'make install' failed")
            return False

    def clean(self):
        """Runs make clean"""
        if self._pre_make_check() is False:
            return False
        cmd = ["make", "clean"]
        ret = ProcessHelper.run_subprocess_cwd(cmd,
                                               self._makefile_path,
                                               ProcessHelper.DEV_NULL)
        if ret == 0:
            self._build_done = False
            return True
        else:
            logger.debug("Sources: 'make clean' failed")
            return False
