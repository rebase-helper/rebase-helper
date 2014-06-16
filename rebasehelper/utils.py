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
    """
    Function return a content of temp filename
    :param filename:
    :return: list of lines from temporary filename
    """
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
        with open(path, perms) as f:
            data = f.read() if not method else f.readlines()
        return data
    except IOError:
        logger.error('Unable to open file %s' % path)
        raise


def get_value_from_kwargs(kwargs, field, source='old'):
    """
    Function returns a part of self.kwargs dictionary
    :param kwargs:
    :param source: 'old' or 'new'
    :param field: like 'patches', 'source'
    :return: value from dictionary
    """
    if not kwargs:
        raise
    if source not in kwargs:
        raise
    if field not in kwargs[source]:
        raise
    return kwargs[source][field]


def write_to_file(path, perms, data):
    """
    Function writes a data to file
    :param path: path to file
    :param perms: permission like "w"
    :param data: string or list
    :return:
    """
    try:
        with open(path, perms) as f:
            f.write(data) if isinstance(data, str) else f.writelines(data)
    except IOError:
        logger.error('Unable to access file %s' % path)
        raise


def get_message(message="", keyboard=False):
    """
    Function for command line messages
    :param message:
    :return: variable y/n
    """
    output = ['yes', 'y', 'no', 'n']
    while True:
        try:
            var = raw_input(message).lower()
        except KeyboardInterrupt:
            return None
        if keyboard:
            return var
        if var not in output:
            logger.info('You have to choose one of y/n.')
        else:
            return var

class ProcessHelper(object):

    DEV_NULL = os.devnull

    @staticmethod
    def run_subprocess(cmd, output=None):
        """
        Runs the passed command as a subprocess.

        :param cmd: command with arguments to be run
        :param output: file to write the output of the command. If None, write to STDOUT
        :return: exit code of the process
        """
        return ProcessHelper.run_subprocess_cwd(cmd, output=output)

    @staticmethod
    def run_subprocess_cwd(cmd, cwd=None, output=None, shell=False):
        """
        Runs the passed command as a subprocess in different working directory.

        :param cmd: command with arguments to be run
        :param cwd: the directory to change the working dir to
        :param output: file to write the output of the command. If None, write to STDOUT
        :param shell: if to run the command as shell command (default: False)
        :return: exit code of the process
        """
        return ProcessHelper.run_subprocess_cwd_env(cmd, cwd=cwd, output=output, shell=shell)

    @staticmethod
    def run_subprocess_env(cmd, env=None, output=None, shell=False):
        """
        Runs the passed command as a subprocess with possibly changed ENVIRONMENT VARIABLES.

        :param cmd: command with arguments to be run
        :param env: dictionary with ENVIRONMENT VARIABLES to define
        :param output: file to write the output of the command. If None, write to STDOUT
        :param shell: if to run the command as shell command (default: False)
        :return: exit code of the process
        """
        return ProcessHelper.run_subprocess_cwd_env(cmd, env=env, output=output, shell=shell)

    @staticmethod
    def run_subprocess_cwd_env(cmd, cwd=None, env=None, output=None, shell=False):
        """
        Runs the passed command as a subprocess in different working directory with possibly changed ENVIRONMENT VARIABLES.

        :param cmd: command with arguments to be run
        :param cwd: the directory to change the working dir to
        :param env: dictionary with ENVIRONMENT VARIABLES to define
        :param output: file to write the output of the command. If None, write to STDOUT
        :param shell: if to run the command as shell command (default: False)
        :return: exit code of the process
        """
        # write the output to a file?
        if output is not None:
            out_file = open(output, "w")
        else:
            out_file = None

        # need to change enviroment variables?
        if env is not None:
            local_env = os.environ.copy()
            local_env.update(env)
        else:
            local_env = None

        sp = subprocess.Popen(cmd,
                              stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT,
                              cwd=cwd,
                              env=local_env,
                              shell=shell)
        for line in sp.stdout:
            if out_file is not None:
                out_file.write(line)
            else:
                logger.debug(line.rstrip("\n"))
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
