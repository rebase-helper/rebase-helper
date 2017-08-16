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

import io
import os
import re
import sys
import fnmatch
import subprocess
import tempfile
import shutil
import rpm
import locale
import time
import random
import string
import gzip
import copr
import pyquery
import hashlib

import git
import six
from six import StringIO
from six.moves import input
from six.moves import urllib
from six.moves import configparser
from distutils.util import strtobool
from pkg_resources import parse_version

from rebasehelper.exceptions import RebaseHelperError
from rebasehelper.logger import logger
from rebasehelper import settings


try:
    import koji
    from koji_cli.lib import TaskWatcher
except ImportError:
    koji_helper_functional = False
else:
    koji_helper_functional = True


defenc = locale.getpreferredencoding()
defenc = 'utf-8' if defenc == 'ascii' else defenc


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
            choice = '[Y/n]'
        else:
            choice = '[y/N]'

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
                logger.error('You have to type y(es) or n(o).')
                continue

            if any_input:
                return True
            else:
                return bool(user_input)

    class Capturer(object):
        """ContextManager for capturing stdout/stderr"""

        def __init__(self, stdout=False, stderr=False):
            self.capture_stdout = stdout
            self.capture_stderr = stderr
            self.stdout = None
            self.stderr = None

        def __enter__(self):
            self._stdout_fileno = sys.__stdout__.fileno()  # pylint:disable=no-member
            self._stderr_fileno = sys.__stderr__.fileno()  # pylint:disable=no-member

            self._stdout_tmp = tempfile.TemporaryFile(mode='w+b') if self.capture_stdout else None
            self._stderr_tmp = tempfile.TemporaryFile(mode='w+b') if self.capture_stderr else None
            self._stdout_copy = os.fdopen(os.dup(self._stdout_fileno), 'wb') if self.capture_stdout else None
            self._stderr_copy = os.fdopen(os.dup(self._stderr_fileno), 'wb') if self.capture_stderr else None

            if self._stdout_tmp:
                sys.stdout.flush()
                os.dup2(self._stdout_tmp.fileno(), self._stdout_fileno)
            if self._stderr_tmp:
                sys.stderr.flush()
                os.dup2(self._stderr_tmp.fileno(), self._stderr_fileno)

            return self

        def __exit__(self, *args):
            if self._stdout_copy:
                sys.stdout.flush()
                os.dup2(self._stdout_copy.fileno(), self._stdout_fileno)
            if self._stderr_copy:
                sys.stderr.flush()
                os.dup2(self._stderr_copy.fileno(), self._stderr_fileno)

            if self._stdout_tmp:
                self._stdout_tmp.flush()
                self._stdout_tmp.seek(0, io.SEEK_SET)
                self.stdout = self._stdout_tmp.read()
                if six.PY3:
                    self.stdout = self.stdout.decode(defenc)
            if self._stderr_tmp:
                self._stderr_tmp.flush()
                self._stderr_tmp.seek(0, io.SEEK_SET)
                self.stderr = self._stderr_tmp.read()
                if six.PY3:
                    self.stderr = self.stderr.decode(defenc)

            if self._stdout_tmp:
                self._stdout_tmp.close()
            if self._stderr_tmp:
                self._stderr_tmp.close()
            if self._stdout_copy:
                self._stdout_copy.close()
            if self._stderr_copy:
                self._stderr_copy.close()


class DownloadError(Exception):
    """Exception indicating that download of a file failed."""
    pass


class DownloadHelper(object):

    """Class for downloading sources defined in SPEC file"""

    @staticmethod
    def progress(download_total, downloaded, start_time):
        """
        The function prints download progress and remaining time of the download directly to the standard output.

        :param download_total: size of the file which is being downloaded
        :type download_total: int or float
        :param downloaded: already downloaded size of the file
        :type downloaded: int or float
        :param start_time: time in seconds since the epoch from the point when the download started.
                           This is used to calculate the remaining time of the download.
        :type start_time: float
        :return: None
        """
        bar_width = 32
        infinite_step = 256 * 1024  # move every 256 kilobytes

        delta = time.time() - start_time

        def format_time(t):
            h, rem = divmod(int(t), 3600)
            m, s = divmod(rem, 60)
            return '{:0>2d}:{:0>2d}:{:0>2d}'.format(h, m, s)

        def format_size(s):
            units = [' ', 'K', 'M', 'G', 'T']
            i = 0
            while s >= 1024.0 and i < len(units) - 1:
                s /= 1024.0
                i += 1
            return '{:>7.2F}{}'.format(s, units[i])

        if download_total < 0:
            # infinite progress bar
            pct = ' ' * 4
            pos = int(downloaded / infinite_step) % (bar_width - 5)
            bar = '[{}<=>{}]'.format(' ' * pos, ' ' * (bar_width - 5 - pos))
            ts = ' in {}'.format(format_time(delta))
        else:
            r = float(downloaded) / float(download_total) if download_total else 0.0
            pct = '{:>3d}%'.format(int(r * 100))
            pos = int(r * (bar_width - 3))
            bar = '[{}>{}]'.format('=' * pos, ' ' * (bar_width - 3 - pos))
            ts = 'eta {}'.format(format_time(delta / r - delta) if r > 0.0 else ' ' * 7 + '?')

        size = format_size(downloaded)

        # no point to log progress, write directly to stdout
        sys.stdout.write('\r{}{}  {}  {} '.format(pct, bar, size, ts))
        sys.stdout.flush()

    @staticmethod
    def download_file(url, destination_path, timeout=10, blocksize=8192):
        """
        Method for downloading file from HTTP, HTTPS and FTP URL.

        :param url: URL from which to download the file
        :param destination_path: path where to store downloaded file
        :param timeout: timeout in seconds for blocking actions like connecting, etc.
        :param blocksize: size in Bytes of blocks used for downloading the file and reporting progress
        :return: None
        """
        try:
            response = urllib.request.urlopen(url, timeout=timeout)
            file_size = int(response.info().get('Content-Length', -1))

            # file exists, check the size
            if os.path.exists(destination_path):
                if file_size < 0 or file_size != os.path.getsize(destination_path):
                    logger.debug("The destination file '%s' exists, but sizes don't match! Removing it.",
                                 destination_path)
                    os.remove(destination_path)
                else:
                    logger.debug("The destination file '%s' exists, and the size is correct! Skipping download.",
                                 destination_path)
                    return
            try:
                with open(destination_path, 'wb') as local_file:
                    logger.info('Downloading file from URL %s', url)
                    download_start = time.time()
                    downloaded = 0

                    # report progress
                    DownloadHelper.progress(file_size, downloaded, download_start)

                    # do the actual download
                    while True:
                        buffer = response.read(blocksize)

                        # no more data to read
                        if not buffer:
                            break

                        downloaded += len(buffer)
                        local_file.write(buffer)

                        # report progress
                        DownloadHelper.progress(file_size, downloaded, download_start)

                    sys.stdout.write('\n')
                    sys.stdout.flush()
            except KeyboardInterrupt as e:
                os.remove(destination_path)
                raise e

        except urllib.error.URLError as e:
            raise DownloadError(str(e))


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
                in_data = in_file.read()
            except AttributeError:
                spooled_in_file.close()
            else:
                spooled_in_file.write(in_data.encode(defenc) if six.PY3 else in_data)
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
                try:
                    out_file.write(line.decode(defenc) if six.PY3 else line)
                except TypeError:
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

        logger.debug("subprocess exited with return code %s", six.text_type(sp.returncode))

        return sp.returncode


class PathHelper(object):

    """Class which finds a file or files in specific directory"""

    @staticmethod
    def find_first_dir_with_file(top_path, pattern):
        """
        Finds a file that matches the given 'pattern' recursively
        starting in the 'top_path' directory. If found, returns full path
        to the directory with first occurrence of the file, otherwise
        returns None.
        """
        for root, dirs, files in os.walk(top_path):
            dirs.sort()
            for f in files:
                if fnmatch.fnmatch(f, pattern):
                    return os.path.abspath(root)
        return None

    @staticmethod
    def find_first_file(top_path, pattern, recursion_level=None):
        """
        Finds a file that matches the given 'pattern' recursively
        starting in the 'top_path' directory. If found, returns full path
        to the first occurrence of the file, otherwise returns None.
        """
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
        """
        Finds a file that matches the given 'pattern' recursively
        starting in the 'top_path' directory. If found, returns full path
        to the first occurrence of the file, otherwise returns None.
        """
        files_list = []
        for root, dirs, files in os.walk(top_path):
            dirs.sort()
            for f in files:
                if fnmatch.fnmatch(f, pattern):
                    files_list.append(os.path.join(os.path.abspath(root), f))
        return files_list

    @staticmethod
    def find_all_files_current_dir(top_path, pattern):
        """
        Finds all files that matches the given 'pattern' in the 'top_path' directory.
        If found, returns fields of all files, otherwise returns None.
        """
        files_list = []
        for files in os.listdir(top_path):
            if fnmatch.fnmatch(files, pattern):
                files_list.append(os.path.join(os.path.abspath(top_path), files))
        return files_list

    @staticmethod
    def get_temp_dir():
        """Returns a path to new temporary directory."""
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
        mi = ts.dbMatch('provides', pkg_name)
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
        cmd = ['dnf', 'builddep', spec_path]
        if os.geteuid() != 0:
            cmd = ['pkexec'] + cmd
        if assume_yes:
            cmd.append('-y')
        return ProcessHelper.run_subprocess(cmd)

    @staticmethod
    def get_header_from_rpm(rpm_name):
        """
        Function returns a rpm header from given rpm package
        for later on analysis

        :param rpm_name:
        :return: 
        """
        ts = rpm.TransactionSet()
        # disable signature checking
        ts.setVSFlags(rpm._RPMVSF_NOSIGNATURES)
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
        name = h[info].decode(defenc) if six.PY3 else h[info]
        return name


class MacroHelper(object):

    """Helper class for working with RPM macros """

    @staticmethod
    def dump():
        """
        Returns list of all defined macros

        :return: list of macros
        """
        macro_re = re.compile(
            r'''
            ^\s*
            (?P<level>-?\d+)
            (?P<used>=|:)
            [ ]
            (?P<name>\w+)
            (?P<options>\(.+?\))?
            [\t]
            (?P<value>.*)
            $
            ''',
            re.VERBOSE)

        with ConsoleHelper.Capturer(stderr=True) as capturer:
            rpm.expandMacro('%dump')

        macros = []

        def add_macro(properties):
            macro = dict(properties)
            macro['used'] = macro['used'] == '='
            macro['level'] = int(macro['level'])
            if parse_version(rpm.__version__) < parse_version('4.13.90'):
                # in RPM < 4.13.90 level of some macros is decreased by 1
                if macro['level'] == -1:
                    # this could be macro with level -1 or level 0, we can not be sure
                    # so just duplicate the macro for both levels
                    macros.append(macro)
                    macro = dict(macro)
                    macro['level'] = 0
                    macros.append(macro)
                elif macro['level'] in (-14, -16):
                    macro['level'] += 1
                    macros.append(macro)
                else:
                    macros.append(macro)
            else:
                macros.append(macro)

        for line in capturer.stderr.split('\n'):
            match = macro_re.match(line)
            if match:
                add_macro(match.groupdict())

        return macros

    @staticmethod
    def filter(macros, **kwargs):
        """
        Returns all macros satisfying specified filters

        :param macros: list of macros to be filtered
        :param kwargs: filters
        :return: filtered list of macros
        """
        def _test(macro):
            return all(macro.get(k[4:]) >= v if k.startswith('min_') else
                       macro.get(k[4:]) <= v if k.startswith('max_') else
                       macro.get(k) == v for k, v in six.iteritems(kwargs))

        return [m for m in macros if _test(m)]


class GitHelper(object):

    """Class which operates with git repositories"""

    # provide fallback values if system is not configured
    GIT_USER_NAME = 'rebase-helper'
    GIT_USER_EMAIL = 'rebase-helper@localhost.local'

    @classmethod
    def get_user(cls):
        try:
            return git.cmd.Git().config('--global', 'user.name', get=True, stdout_as_string=six.PY3)
        except git.GitCommandError:
            return cls.GIT_USER_NAME

    @classmethod
    def get_email(cls):
        try:
            return git.cmd.Git().config('--global', 'user.email', get=True, stdout_as_string=six.PY3)
        except git.GitCommandError:
            return cls.GIT_USER_EMAIL

    @classmethod
    def run_mergetool(cls, repo):
        # we can't use GitPython here, as it doesn't allow
        # for the command to attach to stdout directly
        cwd = os.getcwd()
        try:
            os.chdir(repo.working_tree_dir)
            ProcessHelper.run_subprocess(['git', 'mergetool'])
        finally:
            os.chdir(cwd)


class KojiHelper(object):

    functional = koji_helper_functional
    cert = os.path.expanduser('~/.fedora.cert')
    ca_cert = os.path.expanduser('~/.fedora-server-ca.cert')
    koji_web = "koji.fedoraproject.org"
    server = "https://%s/kojihub" % koji_web
    scratch_url = "http://%s/work/" % koji_web
    baseurl = 'http://kojipkgs.fedoraproject.org/work/'
    baseurl_pkg = 'https://kojipkgs.fedoraproject.org/packages/'

    @classmethod
    def _unique_path(cls, prefix):
        suffix = ''.join([random.choice(string.ascii_letters) for i in range(8)])
        return '%s/%r.%s' % (prefix, time.time(), suffix)

    @classmethod
    def session_maker(cls, baseurl=None):
        if baseurl is None:
            koji_session = koji.ClientSession(cls.server, {'timeout': 3600})
        else:
            koji_session = koji.ClientSession(baseurl)
            return koji_session
        try:
            koji_session.krb_login()
        except koji.krbV.Krb5Error:
            # fall back to login using certificate
            koji_session.ssl_login(cls.cert, cls.ca_cert, cls.ca_cert)
        return koji_session

    @classmethod
    def upload_srpm(cls, session, source):
        server_dir = cls._unique_path('cli-build')
        session.uploadWrapper(source, server_dir)
        return '%s/%s' % (server_dir, os.path.basename(source))

    @classmethod
    def display_task_results(cls, tasks):
        """Taken from from koji_cli.lib"""
        for task in [task for task in tasks.values() if task.level == 0]:
            state = task.info['state']
            task_label = task.str()

            logger.info('State %s (%s)', state, task_label)
            if state == koji.TASK_STATES['CLOSED']:
                logger.info('%s completed successfully', task_label)
            elif state == koji.TASK_STATES['FAILED']:
                logger.info('%s failed', task_label)
            elif state == koji.TASK_STATES['CANCELED']:
                logger.info('%s was canceled', task_label)
            else:
                # shouldn't happen
                logger.info('%s has not completed', task_label)

    @classmethod
    def watch_koji_tasks(cls, session, tasklist):
        """Taken from from koji_cli.lib"""
        if not tasklist:
            return
        sys.stdout.flush()
        rh_tasks = {}
        try:
            tasks = {}
            for task_id in tasklist:
                tasks[task_id] = TaskWatcher(task_id, session, quiet=False)
            while True:
                all_done = True
                for task_id, task in list(tasks.items()):
                    with ConsoleHelper.Capturer(stdout=True) as capturer:
                        changed = task.update()
                    for line in capturer.stdout.split('\n'):
                        if line:
                            logger.info(line)
                    info = session.getTaskInfo(task_id)
                    state = task.info['state']
                    if state == koji.TASK_STATES['FAILED']:
                        return {info['id']: state}
                    else:
                        if info['arch'] == 'x86_64' or info['arch'] == 'noarch':
                            rh_tasks[info['id']] = state
                    if not task.is_done():
                        all_done = False
                    else:
                        if changed:
                            # task is done and state just changed
                            cls.display_task_results(tasks)
                        if not task.is_success():
                            rh_tasks = None
                    for child in session.getTaskChildren(task_id):
                        child_id = child['id']
                        if not child_id in list(tasks.keys()):
                            tasks[child_id] = TaskWatcher(child_id, session, task.level + 1, quiet=False)
                            with ConsoleHelper.Capturer(stdout=True) as capturer:
                                tasks[child_id].update()
                            for line in capturer.stdout.split('\n'):
                                if line:
                                    logger.info(line)
                            info = session.getTaskInfo(child_id)
                            state = task.info['state']
                            if state == koji.TASK_STATES['FAILED']:
                                return {info['id']: state}
                            else:
                                if info['arch'] == 'x86_64' or info['arch'] == 'noarch':
                                    rh_tasks[info['id']] = state
                            # If we found new children, go through the list again,
                            # in case they have children also
                            all_done = False
                if all_done:
                    cls.display_task_results(tasks)
                    break

                sys.stdout.flush()
                time.sleep(1)
        except KeyboardInterrupt:
            rh_tasks = None
        return rh_tasks

    @classmethod
    def download_scratch_build(cls, session, task_list, dir_name):
        rpms = []
        logs = []
        for task_id in task_list:
            logger.info('Downloading packages and logs for %s taskID', task_id)
            task = session.getTaskInfo(task_id)
            tasks = [task]
            for task in tasks:
                base_path = koji.pathinfo.taskrelpath(task_id)
                output = session.listTaskOutput(task['id'])
                for filename in output:
                    if filename.endswith('.src.rpm'):
                        continue
                    logger.info('Downloading file %s', filename)
                    downloaded_file = os.path.join(dir_name, filename)
                    DownloadHelper.download_file(cls.scratch_url + base_path + '/' + filename,
                                                 downloaded_file)
                    if filename.endswith('.rpm'):
                        rpms.append(downloaded_file)
                    if filename.endswith('.log'):
                        logs.append(downloaded_file)
        return rpms, logs

    @classmethod
    def get_koji_tasks(cls, task_id, dir_name):
        session = cls.session_maker(baseurl=cls.server)
        task_id = int(task_id)
        rpm_list = []
        log_list = []
        tasks = []
        task = session.getTaskInfo(task_id, request=True)
        if task['state'] in (koji.TASK_STATES['FREE'], koji.TASK_STATES['OPEN']):
            return None, None
        elif task['state'] != koji.TASK_STATES['CLOSED']:
            logger.info('Task %i did not complete successfully' % task_id)

        if task['method'] == 'build':
            logger.info('Getting rpms for chilren of task %i: %s',
                        task['id'],
                        koji.taskLabel(task))
            # getting rpms from children of task
            tasks = session.listTasks(opts={'parent': task_id,
                                            'method': 'buildArch',
                                            'state': [koji.TASK_STATES['CLOSED'], koji.TASK_STATES['FAILED']],
                                            'decode': True})
        elif task['method'] == 'buildArch':
            tasks = [task]
        for task in tasks:
            base_path = koji.pathinfo.taskrelpath(task['id'])
            output = session.listTaskOutput(task['id'])
            if output is None:
                return None
            for filename in output:
                download = False
                full_path_name = os.path.join(dir_name, filename)
                if filename.endswith('.src.rpm'):
                    continue
                if filename.endswith('.rpm'):
                    if task['state'] != koji.TASK_STATES['CLOSED']:
                        continue
                    arch = filename.rsplit('.', 3)[2]
                    if full_path_name not in rpm_list:
                        download = arch in ['noarch', 'x86_64']
                        if download:
                            rpm_list.append(full_path_name)
                else:
                    if full_path_name not in log_list:
                        log_list.append(full_path_name)
                        download = True
                if download:
                    DownloadHelper.download_file(cls.baseurl + base_path + '/' + filename,
                                                 full_path_name)
        return rpm_list, log_list

    @classmethod
    def get_latest_build(cls, package):
        """
        Searches for the latest Koji build of a package

        :param package: package name
        :return: (latest version, Koji build ID)
        """
        session = cls.session_maker(baseurl=cls.server)
        builds = session.getLatestBuilds('rawhide', package=package)
        if builds:
            return builds[0]['version'], builds[0]['id']
        return None, None

    @classmethod
    def download_build(cls, build_id, destination):
        """
        Downloads all x86_64 RPMs and logs of a Koji build

        :param build_id: Koji build ID
        :param destination: target path
        :return: (list of paths to RPMs, list of paths to logs)
        """
        session = cls.session_maker(baseurl=cls.server)
        build = session.getBuild(build_id)
        rpms = session.listRPMs(buildID=build_id)
        rpm_list = []
        log_list = []
        for rpm in rpms:
            if rpm['arch'] not in ['noarch', 'x86_64']:
                continue
            for logname in ['build.log', 'root.log', 'state.log']:
                dest_path = os.path.join(destination, logname)
                if not dest_path in log_list:
                    url = '/'.join([
                        cls.baseurl_pkg,
                        build['package_name'],
                        build['version'],
                        build['release'],
                        'data',
                        'logs',
                        rpm['arch'],
                        logname])
                    DownloadHelper.download_file(url, dest_path)
                    log_list.append(dest_path)
            filename = '.'.join([rpm['nvr'], rpm['arch'], 'rpm'])
            dest_path = os.path.join(destination, filename)
            if not dest_path in rpm_list:
                url = '/'.join([
                    cls.baseurl_pkg,
                    build['package_name'],
                    build['version'],
                    build['release'],
                    rpm['arch'],
                    filename])
                DownloadHelper.download_file(url, dest_path)
                rpm_list.append(dest_path)
        return rpm_list, log_list

class CoprHelper(object):

    @classmethod
    def get_client(cls):
        try:
            client = copr.CoprClient.create_from_file_config()
        except (copr.client.exceptions.CoprNoConfException,
                copr.client.exceptions.CoprConfigException):
            raise RebaseHelperError(
                'Missing or invalid copr configuration file')
        else:
            return client

    @classmethod
    def create_project(cls, client, project, chroot, description, instructions):
        try:
            try:
                client.create_project(projectname=project,
                                      chroots=[chroot],
                                      description=description,
                                      instructions=instructions)
            except TypeError:
                # username argument is required since python-copr-1.67-1
                client.create_project(username=None,
                                      projectname=project,
                                      chroots=[chroot],
                                      description=description,
                                      instructions=instructions)
        except copr.client.exceptions.CoprRequestException:
            # reuse existing project
            pass

    @classmethod
    def build(cls, client, project, srpm):
        try:
            result = client.create_new_build(projectname=project, pkgs=[srpm])
        except copr.client.exceptions.CoprRequestException as e:
            raise RebaseHelperError('Failed to start copr build: {}'.format(str(e)))
        else:
            return result.builds_list[0].build_id

    @classmethod
    def get_build_url(cls, client, build_id):
        try:
            result = client.get_build_details(build_id)
        except copr.client.exceptions.CoprRequestException as e:
            raise RebaseHelperError(
                'Failed to get copr build details for id {}: {}'.format(build_id, str(e)))
        else:
            return '{}/coprs/{}/{}/build/{}/'.format(client.copr_url,
                                                     client.username,
                                                     result.project,
                                                     build_id)

    @classmethod
    def get_build_status(cls, client, build_id):
        try:
            result = client.get_build_details(build_id)
        except copr.client.exceptions.CoprRequestException as e:
            raise RebaseHelperError(
                'Failed to get copr build details for id {}: {}'.format(build_id, str(e)))
        else:
            return result.status

    @classmethod
    def watch_build(cls, client, build_id):
        try:
            while True:
                status = cls.get_build_status(client, build_id)
                if not status:
                    return False
                elif status in ['succeeded', 'skipped']:
                    return True
                elif status in ['failed', 'canceled', 'unknown']:
                    return False
                else:
                    time.sleep(10)
        except KeyboardInterrupt:
            return False

    @classmethod
    def download_build(cls, client, build_id, destination):
        logger.info('Downloading packages and logs for build %d', build_id)
        try:
            result = client.get_build_details(build_id)
        except copr.client.exceptions.CoprRequestException as e:
            raise RebaseHelperError(
                'Failed to get copr build details for {}: {}'.format(build_id, str(e)))
        rpms = []
        logs = []
        for _, url in six.iteritems(result.data['results_by_chroot']):
            url = url if url.endswith('/') else url + '/'
            d = pyquery.PyQuery(url, opener=lambda x: urllib.request.urlopen(x))
            d.make_links_absolute()
            for a in d('a[href$=\'.rpm\'], a[href$=\'.log.gz\']'):
                fn = os.path.basename(urllib.parse.urlsplit(a.attrib['href']).path)
                dest = os.path.join(destination, fn)
                if fn.endswith('.src.rpm'):
                    # skip source RPM
                    continue
                DownloadHelper.download_file(a.attrib['href'], dest)
                if fn.endswith('.rpm'):
                    rpms.append(dest)
                elif fn.endswith('.log.gz'):
                    extracted = dest.replace('.log.gz', '.log')
                    try:
                        with gzip.open(dest, 'rb') as archive:
                            with open(extracted, 'wb') as f:
                                f.write(archive.read())
                    except (IOError, EOFError):
                        raise RebaseHelperError(
                            'Failed to extract {}'.format(dest))
                    logs.append(extracted)
        return rpms, logs


class FileHelper(object):

    @staticmethod
    def file_available(filename):
        if os.path.exists(filename) and os.path.getsize(filename) != 0:
            return True
        else:
            return False


class LookasideCacheError(Exception):

    """Exception indicating a problem accessing lookaside cache"""

    pass


class LookasideCacheHelper(object):

    """Class for downloading files from Fedora/RHEL lookaside cache"""

    rpkg_config_dir = '/etc/rpkg'

    @classmethod
    def _read_config(cls, tool):
        config = configparser.ConfigParser()
        config.read(os.path.join(cls.rpkg_config_dir, '{}.conf'.format(tool)))
        return dict(config.items(tool, raw=True))

    @classmethod
    def _read_sources(cls, basepath):
        line_re = re.compile(r'^(?P<hashtype>[^ ]+?) \((?P<file>[^ )]+?)\) = (?P<hash>[^ ]+?)$')
        sources = []
        path = os.path.join(basepath, 'sources')
        if os.path.exists(path):
            with open(path, 'r') as f:
                for line in f.readlines():
                    line = line.strip()
                    m = line_re.match(line)
                    if m is not None:
                        d = m.groupdict()
                    else:
                        # fall back to old format of sources file
                        hash, file = line.split()
                        d = dict(hash=hash, file=file, hashtype='md5')
                    d['hashtype'] = d['hashtype'].lower()
                    sources.append(d)
        return sources

    @classmethod
    def _hash(cls, filename, hashtype):
        try:
            sum = hashlib.new(hashtype)
        except ValueError:
            raise LookasideCacheError('Unsupported hash type \'{}\''.format(hashtype))
        with open(filename, 'rb') as f:
            chunk = f.read(8192)
            while chunk:
                sum.update(chunk)
                chunk = f.read(8192)
        return sum.hexdigest()

    @classmethod
    def _download_source(cls, tool, url, package, filename, hashtype, hash, target=None):
        if target is None:
            target = os.path.basename(filename)
        if os.path.exists(target):
            if cls._hash(target, hashtype) == hash:
                # nothing to do
                return
            else:
                os.unlink(target)
        if tool == 'fedpkg':
            url = '{}/{}/{}/{}/{}/{}'.format(url, package, filename, hashtype, hash, filename)
        else:
            url = '{}/{}/{}/{}/{}'.format(url, package, filename, hash, filename)
        try:
            DownloadHelper.download_file(url, target)
        except DownloadError as e:
            raise LookasideCacheError(str(e))

    @classmethod
    def download(cls, tool, basepath, package):
        try:
            config = cls._read_config(tool)
            url = config['lookaside']
        except (configparser.Error, KeyError):
            raise LookasideCacheError('Failed to read rpkg configuration')
        for source in cls._read_sources(basepath):
            cls._download_source(tool, url, package, source['file'], source['hashtype'], source['hash'])
