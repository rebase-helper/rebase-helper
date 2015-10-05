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
import pycurl
import shutil
import rpm
import six
import locale
from six import StringIO
from six.moves import input
from distutils.util import strtobool
from rebasehelper.exceptions import RebaseHelperError
from rebasehelper.logger import logger
from rebasehelper import settings

defenc = locale.getpreferredencoding()
defenc = 'utf-8' if defenc == 'ascii' else defenc


def exc_as_decode_string(e):
    if six.PY2:
        s = unicode(e)
    else:
        s = str(e)
    return s


class GitRuntimeError(RuntimeError):

    """Error indicating problems with Git"""

    pass


class GitRebaseError(RuntimeError):

    """Error indicating problems with Git"""

    pass


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

    """Class for command line interaction with the user."""

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

    """Class for downloading sources defined in SPEC file"""

    @staticmethod
    def download_file(url, destination_name):
        """
        Method for downloading file using pycurl

        :param url: URL from which to download the file
        :param destination_name: path where to store downloaded file
        :return None
        """
        if os.path.exists(destination_name):
            return
        with open(destination_name, 'wb') as f:
            curl = pycurl.Curl()
            curl.setopt(pycurl.URL, url)
            curl.setopt(pycurl.CONNECTTIMEOUT, 30)
            curl.setopt(pycurl.FOLLOWLOCATION, 1)
            curl.setopt(pycurl.MAXREDIRS, 5)
            curl.setopt(pycurl.TIMEOUT, 300)
            curl.setopt(pycurl.WRITEDATA, f)
            try:
                logger.info('Downloading sources from URL %s', url)
                curl.perform()
            except pycurl.error as error:
                curl.close()
                raise ReferenceError("Downloading '%s' failed with error '%s'." % (url, error))

            else:
                curl.close()


class ProcessHelper(object):

    """Class for execution subprocess"""

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
        Runs the passed command as a subprocess in different
        working directory with possibly changed ENVIRONMENT VARIABLES.

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

        logger.debug("cmd=%s, cwd=%s, env=%s, input=%s, output=%s, shell=%s",
                     str(cmd), str(cwd), str(env), str(input), str(output), str(shell))

        # write the output to a file/file-like object?
        try:
            out_file = open(output, 'wb')
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
                out_file.write(line)
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

        logger.debug("subprocess exited with return code %s", exc_as_decode_string(sp.returncode))

        return sp.returncode


class PathHelper(object):

    """Class which finds a file or files in specific directory"""

    @staticmethod
    def find_first_dir_with_file(top_path, pattern):

        """ Finds a file that matches the given 'pattern' recursively
        starting in the 'top_path' directory. If found, returns full path
        to the directory with first occurrence of the file, otherwise
        returns None. """
        for root, dirs, files in os.walk(top_path):
            dirs.sort()
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
            dirs.sort()
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
            dirs.sort()
            for f in files:
                if fnmatch.fnmatch(f, pattern):
                    files_list.append(os.path.join(os.path.abspath(root), f))
        return files_list

    @staticmethod
    def get_temp_dir():

        """ Returns a path to new temporary directory. """
        return tempfile.mkdtemp(prefix=settings.REBASE_HELPER_PREFIX)


class TemporaryEnvironment(object):

    """
    Class representing a temporary environment (directory) that can be used
    as a workspace. It can be used with with statement.
    """

    TEMPDIR = 'TEMPDIR'

    def __init__(self, exit_callback=None, **kwargs):
        self._env = {}
        self._exit_callback = exit_callback

    def __enter__(self):
        self._env[self.TEMPDIR] = PathHelper.get_temp_dir()
        logger.debug("Created environment in '%s'", self.path())
        return self

    def __exit__(self, type, value, traceback):
        # run callback before removing the environment
        try:
            self._exit_callback(**self.env())
        except TypeError:
            pass
        else:
            logger.debug("Exit callback executed successfully")

        shutil.rmtree(self.path(), onerror=lambda func, path, excinfo: shutil.rmtree(path))
        logger.debug("Destroyed environment in '%s'", self.path())

    def __str__(self):
        return "<TemporaryEnvironment path='%s'>", self.path()

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

    """Helper class for doing various tasks with RPM database, packages, ..."""

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
        cmd = ['pkexec', 'dnf builddep', spec_path]
        if assume_yes:
            cmd.append('-y')
        return ProcessHelper.run_subprocess(cmd)

    @staticmethod
    def get_header_from_rpm(rpm_name):

        """
        Function returns a rpm header from given rpm package
        for later on analysis
        :param pkg_name:
        :return:
        """
        ts = rpm.TransactionSet()
        h = None
        with open(rpm_name, "r") as f:
            h = ts.hdrFromFdno(f)
        return h

    @staticmethod
    def get_info_from_rpm(rpm_name, info):

        """
        Method returns a name of the package from RPM file format
        :param pkg_name:
        :return:
        """
        h = RpmHelper.get_header_from_rpm(rpm_name)
        name = h[info]
        return name


class GitHelper(object):

    """Class which operates with git repositories"""

    GIT = 'git'
    output_data = []

    def __init__(self, git_directory):
        self.git_directory = git_directory

    def _call_git_command(self, command, input_file=None, output_file=None):

        """
        Class calls git command
        :param command: git command which is executed
        :param directory: git directory
        :param input_file: input file for git operations
        :return: ret_code and output of git command
        """
        cmd = []
        cmd.append(self.GIT)
        cmd.extend(command)
        self.output_data = []
        if not output_file:
            output = StringIO()
        else:
            output = output_file
        ret_code = ProcessHelper.run_subprocess_cwd(cmd,
                                                    cwd=self.git_directory,
                                                    input=input_file,
                                                    output=output)
        if not output_file:
            out = output.readlines()
            for o in out:
                self.output_data.append(o.strip().encode(defenc))
        return ret_code

    def check_git_config(self):

        """
        Function checks whether you have setup a merge tool in ~/.gitconfig
        :return: True or False
        """
        merge = self.command_config('--get', 'merge.tool')
        git_config_name = os.path.expanduser('~/{0}'.format(settings.GIT_CONFIG))
        if not merge:
            message = """[merge] section is not defined in %s.\n
One of the possible configuration can be:\n
[mergetool "mymeld"]
    cmd = meld --auto-merge --output $MERGED $LOCAL $BASE $REMOTE --diff $BASE $LOCAL --diff $BASE $REMOTE
[merge]
    tool = mymeld
    conflictstyle = diff3"""
            raise RebaseHelperError(message % git_config_name)
        return merge

    @staticmethod
    def get_commit_hash_log(commit_log, number=None):
        commit = commit_log[number]
        fields = commit.split()
        return fields[0]

    @staticmethod
    def get_untracked_files(output):
        untracked_files = []
        for line in output:
            if not line.startswith("Untracked files:"):
                continue
            # skip two lines
            output.next()
            output.next()

            for untracked_info in output:
                if not untracked_info.startswith("\t"):
                    break
                untracked_files.append(untracked_info.replace("\t", "").rstrip())
                # END for each utracked info line
        # END for each line
        return untracked_files

    @staticmethod
    def get_modified_files(output):

        """Function returns list of modified files from output text"""

        modified_files = []
        for line in output:
            if 'modified:' not in line:
                continue
            modified_files.append(line.strip().split()[1])
        return modified_files

    @staticmethod
    def get_unapplied_patch(output):
        patch_name = None
        lines = [x for x in output if x.startswith("Patch failed at")]
        if not lines:
            return patch_name
        fields = lines[0].split()
        # We need to return only patch name
        return fields[len(fields)-1]

    def command_init(self, directory):
        cmd = ['init']
        cmd.append(directory)
        return self._call_git_command(cmd)

    def command_commit(self, message=None, amend=False):

        """
        Method commits message to Git
        :param directory: Git directtory
        :param message: commit message
        :return: return code from ProcessHelper
        """
        cmd = ['commit']
        if message:
            cmd.extend(['-m', message])
        else:
            cmd.extend(['-m', 'Empty message'])

        if amend:
            cmd.append('--amend')

        return self._call_git_command(cmd)

    def command_remote_add(self, upstream_name, directory):

        """Function add remote git repository to old_sources before a rebase"""

        cmd = []
        cmd.append('remote')
        cmd.append('add')
        cmd.append(upstream_name)
        cmd.append(directory)
        return self._call_git_command(cmd)

    def command_diff_status(self):

        """Function shows which files are modified"""

        cmd = []
        cmd.append('diff')
        cmd.append('--name-only')
        cmd.append('--staged')
        self._call_git_command(cmd)
        return self.output_data

    def command_fetch(self, upstream_name):
        cmd = ['fetch']
        cmd.append(upstream_name)
        return self._call_git_command(cmd)

    def command_log(self, parameters=None):

        """
        Function returns git log
        :param parameters: a parameter to git log command
        :return:
        """
        cmd = ['log']
        if parameters:
            cmd.append(parameters)
        ret_code = self._call_git_command(cmd)
        if int(ret_code) != 0:
            return None
        else:
            return self.output_data

    def command_mergetool(self):

        """Function calls git mergetool program"""

        cmd = ['mergetool']
        ret_code = self._call_git_command(cmd)
        return ret_code

    def command_rebase(self, parameters, upstream_name=None, first_hash=None, last_hash=None):

        """Function calls git rebase"""

        cmd = ['rebase']
        if parameters == '--onto':
            cmd.append(parameters)
            cmd.append(upstream_name + '/master')
            cmd.append(first_hash)
            cmd.append(last_hash)
        else:
            cmd.append(parameters)
        return self._call_git_command(cmd)

    def command_add_files(self, parameters=None):
        cmd = ['add']
        if parameters:
            cmd.extend(parameters)
        return self._call_git_command(cmd)

    def command_diff(self, head, output_file=None):
        cmd = ['diff']
        cmd.append(head)
        return self._call_git_command(cmd, output_file=output_file)

    def command_am(self, parameters=None, input_file=None):
        cmd = ['am']
        if parameters:
            cmd.append(parameters)
        return self._call_git_command(cmd, input_file=input_file)

    def command_apply(self, input_file=None, option=None, ignore_space=False):
        cmd = ['apply']
        if option is not None:
            cmd.append(option)
        if ignore_space:
            cmd.append('--reject')
            cmd.append('--whitespace=fix')
        return self._call_git_command(cmd, input_file=input_file)

    def command_config(self, parameters, variable=None):
        cmd = ['config']
        cmd.append(parameters)
        cmd.append(variable)
        self._call_git_command(cmd)
        if not self.output_data:
            return None
        return self.output_data[0]

    def get_output_data(self):
        """ Function returns output_data after calling call_git_command """
        return self.output_data
