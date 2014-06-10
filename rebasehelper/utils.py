# -*- coding: utf-8 -*-

import os
import fnmatch
import subprocess
import tempfile

from rebasehelper.logger import logger
from rebasehelper import settings

def get_temporary_name():
    return tempfile.mkstemp(prefix="rebase-helper", text=True)[1]

def get_content_temp(filename):
    lines = get_content_file(filename, "r", method=True)
    if os.path.exists(filename):
        os.unlink(filename)
    return lines

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

def get_patch_name(name):
    name, extension = os.path.splitext(name)
    return name + settings.REBASE_HELPER_SUFFIX + extension

def get_rebase_name(name):
    dir_name = os.path.dirname(name)
    file_name = os.path.basename(name)
    return os.path.join(dir_name, settings.REBASE_RESULTS_DIR, file_name)

def get_message(message=""):
    output = ['yes', 'y', 'no', 'n']
    while True:
        try:
            var = raw_input(message).lower()
        except KeyboardInterrupt:
            return None
        if var not in output:
            logger.info('You have to choose one of y/n.')
        else:
            return var

class ProcessHelper(object):

    DEV_NULL = "/dev/null"

    @staticmethod
    def run_subprocess(cmd, output=None):
        return ProcessHelper.run_subprocess_cwd(cmd, output=output)

    @staticmethod
    def run_subprocess_cwd(cmd, cwd=None, output=None, shell=False):
        return ProcessHelper.run_subprocess_cwd_env(cmd, cwd=cwd, output=output, shell=shell)

    @staticmethod
    def run_subprocess_cwd_env(cmd, cwd=None, env=None, output=None, shell=False):
        if output is not None:
            out_file = open(output, "w")
        else:
            out_file = None
        sp = subprocess.Popen(cmd,
                              stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT,
                              cwd=cwd,
                              env=env,
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

    @staticmethod
    def get_temp_dir():
        """ Returns a path to new temporary directory. """
        return tempfile.mkdtemp(prefix=settings.REBASE_HELPER_PREFIX)
