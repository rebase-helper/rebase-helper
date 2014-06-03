# -*- coding: utf-8 -*-

import os
import fnmatch
import subprocess
from rebasehelper.logger import logger
from rebasehelper import settings


def get_content_file(path, perms, method=False):
    """
    Function returns a file content
    if method is False then file is read by function read
    if method is True then file is read by function readlines
    """
    try:
        f = open(path, perms)
        try:
            data = f.read() if not method else f.readlines()
        finally:
            f.close()
            return data
    except IOError:
        logger.error('Unable to open file %s' % path)
        raise

def write_to_file(path, perms, data):
    """
    shortcut for returning content of file:
     open(...).read()
    """
    try:
        f = open(path, perms)
        try:
            f.write(data) if isinstance(data, str) else f.writelines(data)
        finally:
            f.close()
    except IOError:
        logger.error('Unable to access file %s' % path)
        raise


def get_rebase_name(name):
    name, extension = os.path.splitext(name)
    return name + settings.REBASE_HELPER_SUFFIX + extension

class ProcessHelper(object):

    DEV_NULL = "/dev/null"

    @staticmethod
    def run_subprocess(cmd, output=None):
        return ProcessHelper.run_subprocess_cwd(cmd, output=output)

    @staticmethod
    def run_subprocess_cwd(cmd, cwd=None, output=None, shell=False):
        if output is not None:
            out_file = open(output, "w")
        else:
            out_file = None
        sp = subprocess.Popen(cmd,
                              stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT,
                              cwd=cwd,
                              shell=shell)
        for line in sp.stdout:
            if out_file is not None:
                out_file.write(line)
            else:
                print line.rstrip("\n")
        if out_file is not None:
            out_file.close()
        sp.wait()
        return sp.returncode


class PathHelper(object):

    @staticmethod
    def find_first_dir_with_file(top_path, pattern):
        """ Finds a file that matches the given 'pattern' recursively
        starting in the 'top_path' directory. If found, returns full path
        to the directory with first occurance of the file, otherwise
        returns None. """
        for root, dirs, files in os.walk(top_path):
            for f in files:
                if fnmatch.fnmatch(f, pattern):
                    return os.path.abspath(root)
        return None

    @staticmethod
    def find_first_file(top_path, pattern):
        """ Finds a file that matches the given 'pattern' recursively
        starting in the 'top_path' directory. If found, returns full path
        to the first occurance of the file, otherwise returns None. """
        for root, dirs, files in os.walk(top_path):
            for f in files:
                if fnmatch.fnmatch(f, pattern):
                    return os.path.join(os.path.abspath(root), f)
        return None

    @staticmethod
    def find_all_files(top_path, pattern):
        """ Finds a file that matches the given 'pattern' recursively
        starting in the 'top_path' directory. If found, returns full path
        to the first occurance of the file, otherwise returns None. """
        files_list = []
        for root, dirs, files in os.walk(top_path):
            for f in files:
                if fnmatch.fnmatch(f, pattern):
                    files_list.append(os.path.join(os.path.abspath(root), f))
        return files_list