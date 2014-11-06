# -*- coding: utf-8 -*-
#
# This tool helps you to rebase package to the latest version
# Copyright (C) 2013-2014 Red Hat, Inc.
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
#
# Authors: Petr Hracek <phracek@redhat.com>
#          Tomas Hozza <thozza@redhat.com>

import os
import fnmatch
import subprocess
import tempfile
#import pycurl
import shutil
import rpm
import six
from six.moves import input
from six import StringIO
from distutils.util import strtobool

from rebasehelper.logger import logger
from rebasehelper import settings


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


class ConsoleHelper(object):
    """
    Class for command line interaction with the user.
    """

    @staticmethod
    def get_message(message, default_yes=True, any_input=False):
        """
        Function for command line messages

        :param message: prompt string
        :param default_yes: If the default value is YES
        :param any_input: if True, return input without checking it first
        :return: True or False, based on user's input
        """
        if default_yes:
            choice = '([y]/n)'
        else:
            choice = '(y/[n])'

        if any_input:
            msg = '{0} '.format(message)
        else:
            msg = '{0} {1}? '.format(message, choice)

        while True:
            user_input = input(msg).lower()

            if not user_input or any_input:
                return True if default_yes else False

            try:
                user_input = strtobool(user_input)
            except ValueError:
                logger.error('You have to type [y]es or [n]o.')
                continue

            if any_input:
                return True
            else:
                return bool(user_input)


class DownloadHelper(object):
    """
    Class for downloading sources defined in SPEC file
    """

    @staticmethod
    def download_source(url, destination_name):
        # There is some code for using pycurl
        # with open(destination_name, 'wb') as f:
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
        except:
            spooled_in_file = tempfile.SpooledTemporaryFile(mode='w+b')
            try:
                in_data = six.b(in_file.read())
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

        if out_file:
            stdout = subprocess.PIPE
        else:
            stdout = None

        sp = subprocess.Popen(cmd,
                              stdin=in_file,
                              stdout=stdout,
                              stderr=subprocess.STDOUT,
                              cwd=cwd,
                              env=local_env,
                              shell=shell)

        if out_file is not None:
            # read the output
            for line in sp.stdout:
                out_file.write(line.decode())
            # TODO: Need to figure out how to send output to stdout (without logger) and to logger
            #else:
            #   logger.debug(line.rstrip("\n"))

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
        to the directory with first occurrence of the file, otherwise
        returns None. """
        for root, dirs, files in os.walk(top_path):
            for f in files:
                if fnmatch.fnmatch(f, pattern):
                    return os.path.abspath(root)
        return None

    @staticmethod
    def find_first_file(top_path, pattern, recursion_level=None):
        """ Finds a file that matches the given 'pattern' recursively
        starting in the 'top_path' directory. If found, returns full path
        to the first occurrence of the file, otherwise returns None. """
        for loop, (root, dirs, files) in enumerate(os.walk(top_path)):
            for f in files:
                if fnmatch.fnmatch(f, pattern):
                    return os.path.join(os.path.abspath(root), f)
            if recursion_level is not None:
                if loop == recursion_level:
                    break
        return None

    @staticmethod
    def find_all_files(top_path, pattern):
        """ Finds a file that matches the given 'pattern' recursively
        starting in the 'top_path' directory. If found, returns full path
        to the first occurrence of the file, otherwise returns None. """
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


class RpmHelper(object):
    """
    Helper class for doing various tasks with RPM database, packages, ...
    """

    @staticmethod
    def is_package_installed(pkg_name=None):
        """
        Checks whether package with passed name is installed.

        :param package_name: package name we want to check for
        :return: True if installed, False if not installed
        """
        ts = rpm.TransactionSet()
        mi = ts.dbMatch('name', pkg_name)
        return len(mi) > 0

    @staticmethod
    def all_packages_installed(pkg_names=None):
        """
        Check if all packages in passed list are installed.

        :param pkg_names: iterable with package named to check for
        :return: True if all packages are installed, False if at least one package is not installed.
        """
        for pkg in pkg_names:
            if not RpmHelper.is_package_installed(pkg):
                return False
        return True

    @staticmethod
    def install_build_dependencies(spec_path=None, assume_yes=False):
        """
        Install all build requires for a package using PolicyKits
        :param spec_path: absolute path to SPEC file
        :return:
        """
        cmd = ['pkexec', 'yum-builddep', spec_path]
        if assume_yes:
            cmd.append('-y')
        return ProcessHelper.run_subprocess(cmd)
