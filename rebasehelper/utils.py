# -*- coding: utf-8 -*-

# This tool helps you to rebase package to the latest version
# Copyright (C) 2013 Petr Hracek
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# he Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

import os
import fnmatch
import subprocess
import tempfile
#import pycurl
import shutil

from rebasehelper.logger import logger
from rebasehelper import settings


def check_empty_patch(patch_name):
    """
    Function checks whether patch is empty or not
    """
    cmd = ["lsdiff"]
    cmd.append(patch_name)
    temp_name = get_temporary_name()
    ret_code = ProcessHelper.run_subprocess(cmd, output=temp_name)
    if ret_code != 0:
        return False
    lines = get_content_file(temp_name, 'r', method=True)
    remove_temporary_name(temp_name)
    if not lines:
        return True
    else:
        return False


def get_temporary_name():
    handle, filename = tempfile.mkstemp(prefix=settings.REBASE_HELPER_PREFIX, text=True)
    os.close(handle)
    return filename


def remove_temporary_name(name):
    """
    Function removes generated temporary name
    :param name: temporary name
    :return:
    """
    if os.path.exists(name):
        os.unlink(name)


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


def get_message(message="", any=False):
    """
    Function for command line messages
    :param message: prompt string
    :param any: if True, return input without checking it first
    :return: user input
    """
    output = ['yes', 'y', 'no', 'n']
    while True:
        try:
            var = raw_input(message).lower()
        except KeyboardInterrupt:
            return None
        if any:
            return var
        if var not in output:
            logger.info('You have to choose one of y/n.')
        else:
            return var


class DownloadHelper(object):
    """
    Class for downloading sources defined in SPEC file
    """

    @staticmethod
    def download_source(url, destination_name):
        # There is some code for using pycurl
        #with open(destination_name, 'wb') as f:
        #    curl = pycurl.Curl()
        #    curl.setopt(pycurl.URL, url)
        #    curl.setopt(pycurl.CONNECTTIMEOUT, 30)
        #    curl.setopt(pycurl.FOLLOWLOCATION, 1)
        #    curl.setopt(pycurl.MAXREDIRS, 5)
        #    curl.setopt(pycurl.TIMEOUT, 300)
        #    curl.setopt(pycurl.WRITEDATA, f)
        #    try:
        #        curl.perform()
        #    except pycurl.error as error:
        #        logger.error('Downloading {0} failed with error {1}.'.format(url, error))
        #        curl.close()
        #    else:
        #        curl.close()
        logger.info('Downloading sources from URL {0}'.format(url))
        command = ['curl', '-H', 'Pragma:', '-o', destination_name, '-R', '-S', '--fail']
        command.append(url)
        return_val = ProcessHelper.run_subprocess(command)
        return return_val


class ProcessHelper(object):
    """
    Class for execution subprocess
    """

    DEV_NULL = os.devnull

    @staticmethod
    def run_subprocess(cmd, input=None, output=None):
        """
        Runs the passed command as a subprocess.

        :param cmd: command with arguments to be run
        :param input: file to read the input from. If None, read from STDIN
        :param output: file to write the output of the command. If None, write to STDOUT
        :return: exit code of the process
        """
        return ProcessHelper.run_subprocess_cwd(cmd, input=input, output=output)

    @staticmethod
    def run_subprocess_cwd(cmd, cwd=None, input=None, output=None, shell=False):
        """
        Runs the passed command as a subprocess in different working directory.

        :param cmd: command with arguments to be run
        :param cwd: the directory to change the working dir to
        :param input: file to read the input from. If None, read from STDIN
        :param output: file to write the output of the command. If None, write to STDOUT
        :param shell: if to run the command as shell command (default: False)
        :return: exit code of the process
        """
        return ProcessHelper.run_subprocess_cwd_env(cmd, cwd=cwd, input=input, output=output, shell=shell)

    @staticmethod
    def run_subprocess_env(cmd, env=None, input=None, output=None, shell=False):
        """
        Runs the passed command as a subprocess with possibly changed ENVIRONMENT VARIABLES.

        :param cmd: command with arguments to be run
        :param env: dictionary with ENVIRONMENT VARIABLES to define
        :param input: file to read the input from. If None, read from STDIN
        :param output: file to write the output of the command. If None, write to STDOUT
        :param shell: if to run the command as shell command (default: False)
        :return: exit code of the process
        """
        return ProcessHelper.run_subprocess_cwd_env(cmd, env=env, input=input, output=output, shell=shell)

    @staticmethod
    def run_subprocess_cwd_env(cmd, cwd=None, env=None, input=None, output=None, shell=False):
        """
        Runs the passed command as a subprocess in different working directory with possibly changed ENVIRONMENT VARIABLES.

        :param cmd: command with arguments to be run
        :param cwd: the directory to change the working dir to
        :param env: dictionary with ENVIRONMENT VARIABLES to define
        :param input: file to read the input from. If None, read from STDIN
        :param output: file to write the output of the command. If None, write to STDOUT
        :param shell: if to run the command as shell command (default: False)
        :return: exit code of the process
        """
        close_out_file = False
        close_in_file = False

        logger.debug("ProcessHelper.run_subprocess: cmd={cmd}, cwd={cwd}, env={env}, input={input}, output={output}, shell={shell}".format(
            cmd=str(cmd),
            cwd=str(cwd),
            env=str(env),
            input=str(input),
            output=str(output),
            shell=str(shell),
        ))

        # write the output to a file/file-like object?
        try:
            out_file = open(output, 'w')
        except TypeError:
            out_file = output
        else:
            close_out_file = True

        # read the input from a file/file-like object?
        try:
            in_file = open(input, 'r')
        except TypeError:
            in_file = input
        else:
            close_in_file = True

        # we need to rewind the file object pointer to the beginning
        try:
            in_file.seek(0)
        except AttributeError:
            # we don't mind - in_file might be None
            pass

        # check if in_file has fileno() method - which is needed for Popen
        try:
            in_file.fileno()
        except AttributeError:
            spooled_in_file = tempfile.SpooledTemporaryFile(mode='w+b')
            try:
                in_data = in_file.read()
            except AttributeError:
                spooled_in_file.close()
            else:
                spooled_in_file.write(in_data)
                spooled_in_file.seek(0)
                in_file = spooled_in_file
                close_in_file = True

        # need to change environment variables?
        if env is not None:
            local_env = os.environ.copy()
            local_env.update(env)
        else:
            local_env = None

        sp = subprocess.Popen(cmd,
                              stdin=in_file,
                              stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT,
                              cwd=cwd,
                              env=local_env,
                              shell=shell)

        # read the output
        for line in sp.stdout:
            if out_file is not None:
                out_file.write(line)
            else:
                logger.debug(line.rstrip("\n"))

        # we need to rewind the file object pointer to the beginning
        try:
            out_file.seek(0)
        except AttributeError:
            # we don't mind - out_file might be None
            pass

        if close_out_file:
            out_file.close()

        if close_in_file:
            in_file.close()

        sp.wait()

        logger.debug("ProcessHelper.run_subprocess: subprocess exited with return code {ret}".format(ret=str(sp.returncode)))

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


class TemporaryEnvironment(object):
    """ Class representing a temporary environment (directory) that can be used
     as a workspace. It can be used with with statement. """

    TEMPDIR = 'TEMPDIR'

    def __init__(self, exit_callback=None, **kwargs):
        self._env = {}
        self._exit_callback = exit_callback

    def __enter__(self):
        self._env[self.TEMPDIR] = PathHelper.get_temp_dir()
        logger.debug("TemporaryEnvironment: Created environment in '{0}'".format(self.path()))
        return self

    def __exit__(self, type, value, traceback):
        # run callback before removing the environment
        try:
            self._exit_callback(**self.env())
        except TypeError:
            pass
        else:
            logger.debug("TemporaryEnvironment: Exit callback executed successfully")

        shutil.rmtree(self.path())
        logger.debug("TemporaryEnvironment: Destroyed environment in '{0}'".format(self.path()))

    def __str__(self):
        return "<TemporaryEnvironment path='{0}'>".format(self.path())

    def path(self):
        """
        Returns path to the temporary environment.
        :return: abs path to the environment
        """
        return self._env.get(self.TEMPDIR, '')

    def env(self):
        """
        Returns copy of _env dictionary.
        :return: copy of _env dictionary
        """
        return self._env.copy()
