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
import tempfile
import random
import string
import sys

import git
import rpm
import pytest

from six import StringIO

from rebasehelper.utils import GitHelper
from rebasehelper.utils import ConsoleHelper
from rebasehelper.utils import DownloadHelper
from rebasehelper.utils import DownloadError
from rebasehelper.utils import ProcessHelper
from rebasehelper.utils import PathHelper
from rebasehelper.utils import TemporaryEnvironment
from rebasehelper.utils import RpmHelper
from rebasehelper.utils import MacroHelper
from rebasehelper.utils import LookasideCacheHelper


class TestGitHelper(object):

    def write_config_file(self, config_file, name, email):
        with open(config_file, 'w') as f:
            f.write('[user]\n'
                    '    name = {0}\n'
                    '    email = {1}\n'.format(name, email))

    @pytest.mark.parametrize('config', [
        # Get from $XDG_CONFIG_HOME/git/config
        'global',
        # Get from included file in $XDG_CONFIG_HOME/git/config
        'global_include',
        # Get from $repo_path/.git/config
        'local',
        # Get from GIT_CONFIG
        'env',
    ])
    def test_get_user_and_email(self, config, workdir):
        name = 'Foo Bar'
        email = 'foo@bar.com'
        env_git_config = os.environ.get('GIT_CONFIG')
        env_xdg_config_home = os.environ.get('XDG_CONFIG_HOME')

        try:
            if config == 'global':
                work_git_path = os.path.join(workdir, 'git')
                os.makedirs(work_git_path)

                config_file = os.path.join(work_git_path, 'config')
                self.write_config_file(config_file, name, email)
                os.environ['XDG_CONFIG_HOME'] = workdir
            elif config == 'global_include':
                work_git_path = os.path.join(workdir, 'git')
                os.makedirs(work_git_path)

                config_file = os.path.join(work_git_path, 'config')
                with open(config_file, 'w') as f:
                    f.write('[include]\n'
                            '    path = included_config\n')
                included_config_file = os.path.join(work_git_path, 'included_config')
                self.write_config_file(included_config_file, name, email)
                os.environ['XDG_CONFIG_HOME'] = workdir
            elif config == 'local':
                repo = git.Repo.init(workdir)
                repo.git.config('user.name', name, local=True)
                repo.git.config('user.email', email, local=True)
            elif config == 'env':
                config_file = os.path.join(workdir, 'git_config')
                os.environ['GIT_CONFIG'] = config_file
                self.write_config_file(config_file, name, email)
            else:
               raise RuntimeError()

            assert name == GitHelper.get_user()
            assert email == GitHelper.get_email()
        finally:
            if env_git_config:
                os.environ['GIT_CONFIG'] = env_git_config
            elif 'GIT_CONFIG' in os.environ:
                del os.environ['GIT_CONFIG']
            if env_xdg_config_home:
                os.environ['XDG_CONFIG_HOME'] = env_xdg_config_home
            elif 'XDG_CONFIG_HOME' in os.environ:
                del os.environ['XDG_CONFIG_HOME']


class TestConsoleHelper(object):

    @pytest.mark.parametrize('suffix, answer, kwargs, expected_input', [
        (' [Y/n]? ', 'yes', None, True),
        (' [Y/n]? ', 'no', None, False),
        (' [y/N]? ', 'yes', dict(default_yes=False), True),
        (' [Y/n]? ', '\n', None, True),
        (' [y/N]? ', '\n', dict(default_yes=False), False),
        (' ', 'random input\ndsfdf', dict(any_input=True), True),
        (' ', 'random input\n', dict(default_yes=False, any_input=True), False),
    ], ids=[
        'yes',
        'no',
        'yes-default_no',
        'no_input-default_yes',
        'no_input-default_no',
        'any_input-default_yes',
        'any_input-default_no',
    ])
    def test_get_message(self, monkeypatch, capsys, suffix, answer, kwargs, expected_input):
        question = 'bla bla'
        monkeypatch.setattr('sys.stdin', StringIO(answer))
        inp = ConsoleHelper.get_message(question, **(kwargs or {}))
        assert capsys.readouterr()[0] == question + suffix
        assert inp is expected_input

    def test_capture_output(self):
        def write():
            with os.fdopen(sys.__stdout__.fileno(), 'w') as f:  # pylint:disable=no-member
                f.write('test stdout')
            with os.fdopen(sys.__stderr__.fileno(), 'w') as f:  # pylint:disable=no-member
                f.write('test stderr')

        with ConsoleHelper.Capturer(stdout=True, stderr=True) as capturer:
            write()

        assert capturer.stdout == 'test stdout'
        assert capturer.stderr == 'test stderr'


class TestDownloadHelper(object):
    """ DownloadHelper tests """

    COMMIT = 'cf5ae2989a32c391d7769933e0267e6fbfae8e14'

    def test_keyboard_interrupt_situation(self, monkeypatch):
        """
        Test that the local file is deleted in case KeyboardInterrupt is raised during the download
        """
        KNOWN_URL = 'https://ftp.isc.org/isc/bind9/9.10.4-P1/srcid'
        LOCAL_FILE = os.path.basename(KNOWN_URL)

        def interrupter(*args, **kwargs):
            raise KeyboardInterrupt

        # make sure that some function call inside tha actual download section raises the KeyboardInterrupt exception.
        monkeypatch.setattr('time.time', interrupter)

        with pytest.raises(KeyboardInterrupt):
            DownloadHelper.download_file(KNOWN_URL, LOCAL_FILE)

        assert not os.path.exists(LOCAL_FILE)

    @pytest.mark.parametrize('total, downloaded, output', [
        (100, 25, '\r 25%[=======>                      ]    25.00   eta 00:00:30 '),
        (100.0, 25.0, '\r 25%[=======>                      ]    25.00   eta 00:00:30 '),
        (-1, 1024 * 1024, '\r    [    <=>                       ]     1.00M   in 00:00:10 '),
    ], ids=[
        'integer',
        'float',
        'unknown_size',
    ])
    def test_progress(self, total, downloaded, output, monkeypatch):
        """
        Test that progress of a download is shown correctly. Test the case when size parameters are passed as integers.
        """
        buffer = StringIO()
        monkeypatch.setattr('sys.stdout', buffer)
        monkeypatch.setattr('time.time', lambda: 10.0)
        DownloadHelper.progress(total, downloaded, 0.0)
        assert buffer.getvalue() == output

    @pytest.mark.parametrize('url, content', [
        ('http://fedoraproject.org/static/hotspot.txt', 'OK'),
        ('https://ftp.isc.org/isc/bind9/9.10.4-P1/srcid', 'SRCID=adfc588'),
        ('ftp://ftp.isc.org/isc/bind9/9.10.4-P1/srcid', 'SRCID=adfc588'),
        (
            'https://git.kernel.org/cgit/linux/kernel/git/stable/linux-stable.git/patch/?id={}'.format(COMMIT),
            'From {} Mon Sep 17 00:00:00 2001'.format(COMMIT),
        ),
        ('ftp://ftp.gnupg.org/README', 'Welcome hacker!'),
    ], ids=[
        'HTTP',
        'HTTPS',
        'FTP',
        'HTTPS-unknown_size',
        'FTP-unknown_size',
    ])
    def test_download_existing_file(self, url, content):
        """Test downloading existing file"""
        local_file = 'local_file'
        DownloadHelper.download_file(url, local_file)
        assert os.path.isfile(local_file)
        with open(local_file) as f:
            assert f.readline().strip() == content

    @pytest.mark.parametrize('url', [
        'https://ftp.isc.org/isc/bind9/9.10.3-P5/srcid',
        'ftp://ftp.isc.org/isc/bind9/9.10.3-P5/srcid',
    ], ids=[
        'HTTPS',
        'FTP',
    ])
    def test_download_non_existing_file(self, url):
        """Test downloading NON existing file"""
        local_file = 'local_file'
        with pytest.raises(DownloadError):
            DownloadHelper.download_file(url, local_file)
        assert not os.path.isfile(local_file)


class TestProcessHelper(object):
    """ ProcessHelper tests """

    class TestRunSubprocess(object):
        """ ProcessHelper - run_subprocess() tests """
        TEMP_FILE = "temp_file"
        TEMP_DIR = "temp_dir"
        OUT_FILE = "output_file"
        IN_FILE = "input_file"
        PHRASE = "hello world"
        ECHO_COMMAND = ["echo", PHRASE]
        TOUCH_COMMAND = ["touch", TEMP_FILE]
        LS_COMMAND = ["ls"]
        CAT_COMMAND = ["cat"]

        def test_simple_cmd(self):
            ret = ProcessHelper.run_subprocess(self.TOUCH_COMMAND)
            assert ret == 0
            assert os.path.exists(self.TEMP_FILE)

        def test_simple_cmd_with_redirected_output_path(self):
            ret = ProcessHelper.run_subprocess(self.ECHO_COMMAND,
                                               output=self.OUT_FILE)
            assert ret == 0
            assert os.path.exists(self.OUT_FILE)
            assert open(self.OUT_FILE).readline().strip('\n') == self.PHRASE

        def test_simple_cmd_with_redirected_output_fileobject(self):
            buff = StringIO()
            ret = ProcessHelper.run_subprocess(self.ECHO_COMMAND,
                                               output=buff)
            assert ret == 0
            assert not os.path.exists(self.OUT_FILE)
            assert buff.readline().strip('\n') == self.PHRASE
            buff.close()

        def test_simple_cmd_with_input_path_and_redirected_output_path(self):
            with open(self.IN_FILE, 'w') as f:
                f.write(self.PHRASE)

            assert os.path.exists(self.IN_FILE)
            assert open(self.IN_FILE).readline().strip('\n') == self.PHRASE

            ret = ProcessHelper.run_subprocess(self.CAT_COMMAND,
                                               input=self.IN_FILE,
                                               output=self.OUT_FILE)
            assert ret == 0
            assert os.path.exists(self.OUT_FILE)
            assert open(self.OUT_FILE).readline().strip('\n') == self.PHRASE

        def test_simple_cmd_with_input_fileobject_and_redirected_output_path(self):
            in_buff = StringIO()
            in_buff.write(self.PHRASE)

            assert not os.path.exists(self.IN_FILE)
            in_buff.seek(0)
            assert in_buff.readline().strip('\n') == self.PHRASE

            ret = ProcessHelper.run_subprocess(self.CAT_COMMAND,
                                               input=in_buff,
                                               output=self.OUT_FILE)
            in_buff.close()
            assert ret == 0
            assert os.path.exists(self.OUT_FILE)
            assert open(self.OUT_FILE).readline().strip('\n') == self.PHRASE

        def test_simple_cmd_with_input_path_and_redirected_output_fileobject(self):
            out_buff = StringIO()
            with open(self.IN_FILE, 'w') as f:
                f.write(self.PHRASE)

            assert os.path.exists(self.IN_FILE)
            assert open(self.IN_FILE).readline().strip('\n') == self.PHRASE

            ret = ProcessHelper.run_subprocess(self.CAT_COMMAND,
                                               input=self.IN_FILE,
                                               output=out_buff)
            assert ret == 0
            assert not os.path.exists(self.OUT_FILE)
            out_buff.seek(0)
            assert out_buff.readline().strip('\n') == self.PHRASE
            out_buff.close()

        def test_simple_cmd_with_input_fileobject_and_redirected_output_fileobject(self):
            out_buff = StringIO()
            in_buff = StringIO()
            in_buff.write(self.PHRASE)

            assert not os.path.exists(self.IN_FILE)
            in_buff.seek(0)
            assert in_buff.readline().strip('\n') == self.PHRASE

            ret = ProcessHelper.run_subprocess(self.CAT_COMMAND,
                                               input=in_buff,
                                               output=out_buff)
            in_buff.close()
            assert ret == 0
            assert not os.path.exists(self.OUT_FILE)
            out_buff.seek(0)
            assert out_buff.readline().strip('\n') == self.PHRASE
            out_buff.close()

    class TestRunSubprocessCwd(object):
        """ ProcessHelper - run_subprocess_cwd() tests """
        TEMP_FILE = "temp_file"
        TEMP_DIR = "temp_dir"
        OUT_FILE = "output_file"
        PHRASE = "hello world"
        ECHO_COMMAND = ["echo", PHRASE]
        TOUCH_COMMAND = ["touch", TEMP_FILE]
        LS_COMMAND = ["ls"]

        def test_simple_cmd_changed_work_dir(self):
            os.mkdir(self.TEMP_DIR)
            ret = ProcessHelper.run_subprocess_cwd(self.TOUCH_COMMAND,
                                                   self.TEMP_DIR)
            assert ret == 0
            assert os.path.exists(os.path.join(self.TEMP_DIR, self.TEMP_FILE))

        def test_simple_cmd_changed_work_dir_with_redirected_output(self):
            # create temp_file in temp_dir
            self.test_simple_cmd_changed_work_dir()
            ret = ProcessHelper.run_subprocess_cwd(self.LS_COMMAND,
                                                   self.TEMP_DIR,
                                                   output=self.OUT_FILE)
            assert ret == 0
            assert os.path.exists(os.path.join(self.TEMP_DIR, self.TEMP_FILE))
            assert os.path.exists(self.OUT_FILE)
            assert open(self.OUT_FILE).readline().strip("\n") == self.TEMP_FILE

    class TestRunSubprocessCwdEnv(object):
        """ ProcessHelper - run_subprocess_cwd_env() tests """
        OUT_FILE = "output_file"
        PHRASE = "hello world"

        def test_setting_new_env(self):
            # make copy of existing environment
            en_variables = os.environ.copy().keys()

            # pick up non-existing name
            while True:
                rand_name = ''.join(random.choice(string.ascii_letters) for _ in range(6)).upper()
                if rand_name not in en_variables:
                    break

            cmd = 'echo "$' + rand_name + '"'
            ret = ProcessHelper.run_subprocess_cwd_env(cmd,
                                                       env={rand_name: self.PHRASE},
                                                       output=self.OUT_FILE,
                                                       shell=True)
            assert ret == 0
            assert os.path.exists(self.OUT_FILE)
            assert open(self.OUT_FILE).readline().strip("\n") == self.PHRASE

        def test_setting_existing_env(self):
            # make copy of existing environment
            en_variables = list(os.environ.copy().keys())

            # there are no variables set on the system -> nothing to test
            if not en_variables:
                pass

            assert os.environ.get(en_variables[0]) != self.PHRASE

            cmd = 'echo "$' + en_variables[0] + '"'
            ret = ProcessHelper.run_subprocess_cwd_env(cmd,
                                                       env={en_variables[0]: self.PHRASE},
                                                       output=self.OUT_FILE,
                                                       shell=True)
            assert ret == 0
            assert os.path.exists(self.OUT_FILE)
            assert open(self.OUT_FILE).readline().strip("\n") == self.PHRASE


class TestPathHelper(object):
    """ PathHelper tests """

    @pytest.fixture
    def filelist(self):
        files = [
            'file',
             'ffile',
             'ppythooon',
             'dir1/fileee',
             'dir1/faa/pythooon',
             'dir1/foo/pythooon',
             'dir1/foo/bar/file',
             'dir1/foo/baz/file',
             'dir1/baz/ffile',
             'dir1/bar/file',
             'dir1/baz/bar/ffile',
             'dir1/baz/bar/test.spec',
        ]

        for f in files:
            try:
                os.makedirs(os.path.dirname(f))
            except OSError:
                pass
            with open(f, 'w') as fd:
                fd.write(f)

        return files

    class TestFindFirstDirWithFile(object):
        """ PathHelper - find_first_dir_with_file() tests """
        def test_find_file(self, filelist):
            assert PathHelper.find_first_dir_with_file(
                "dir1", "file") == os.path.abspath(
                os.path.dirname(filelist[9]))
            assert PathHelper.find_first_dir_with_file(
                os.path.curdir, "file") == os.path.abspath(os.path.dirname(filelist[0]))
            assert PathHelper.find_first_dir_with_file(
                "dir1/baz", "file") is None

        def test_find_ffile(self, filelist):
            assert PathHelper.find_first_dir_with_file(
                "dir1", "*le") == os.path.abspath(
                os.path.dirname(filelist[9]))
            assert PathHelper.find_first_dir_with_file(
                "dir1", "ff*") == os.path.abspath(
                os.path.dirname(filelist[8]))
            assert PathHelper.find_first_dir_with_file(
                "dir1/foo", "ff*") is None

        def test_find_pythoon(self, filelist):
            assert PathHelper.find_first_dir_with_file(
                "dir1", "pythooon") == os.path.abspath(
                os.path.dirname(filelist[4]))
            assert PathHelper.find_first_dir_with_file(
                os.path.curdir, "py*n") == os.path.abspath(os.path.dirname(filelist[4]))
            assert PathHelper.find_first_dir_with_file(
                "dir1/bar", "pythooon") is None

    class TestFindFirstFile(object):
        """ PathHelper - find_first_file() tests """
        def test_find_file(self, filelist):
            assert PathHelper.find_first_file(
                "dir1", "file") == os.path.abspath(filelist[9])
            assert PathHelper.find_first_file(
                os.path.curdir, "file") == os.path.abspath(filelist[0])
            assert PathHelper.find_first_file("dir1/baz", "file") is None

        def test_find_ffile(self, filelist):
            assert PathHelper.find_first_file(
                "dir1", "*le") == os.path.abspath(filelist[9])
            assert PathHelper.find_first_file(
                "dir1", "ff*") == os.path.abspath(filelist[8])
            assert PathHelper.find_first_file("dir1/foo", "ff*") is None

        def test_find_pythoon(self, filelist):
            assert PathHelper.find_first_file(
                "dir1", "pythooon") == os.path.abspath(filelist[4])
            assert PathHelper.find_first_file(
                os.path.curdir, "py*n") == os.path.abspath(filelist[4])
            assert PathHelper.find_first_file("dir1/bar", "pythooon") is None

        def test_find_with_recursion(self, filelist):
            assert PathHelper.find_first_file(os.path.curdir, "*.spec", 0) is None
            assert PathHelper.find_first_file(os.path.curdir, "*.spec", 1) is None
            assert PathHelper.find_first_file(os.path.curdir, "*.spec", 2) is None
            assert PathHelper.find_first_file(os.path.curdir, "*.spec", 3) is None
            assert PathHelper.find_first_file(os.path.curdir, "*.spec", 4) == os.path.abspath(filelist[-1])

        def test_find_without_recursion(self, filelist):
            assert PathHelper.find_first_file(os.path.curdir, "*.spec") == os.path.abspath(filelist[-1])


class TestTemporaryEnvironment(object):
    """ TemporaryEnvironment class tests. """

    def test_with_statement(self):
        with TemporaryEnvironment() as temp:
            path = temp.path()
            assert path != ''
            assert os.path.exists(path)
            assert os.path.isdir(path)
            env = temp.env()
            assert env.get(temp.TEMPDIR, None) is not None
            assert env.get(temp.TEMPDIR, None) == path

        assert not os.path.exists(path)
        assert not os.path.isdir(path)

    def test_with_statement_exception(self):
        path = ''

        try:
            with TemporaryEnvironment() as temp:
                path = temp.path()
                raise RuntimeError()
        except RuntimeError:
            pass

        assert not os.path.exists(path)
        assert not os.path.isdir(path)

    def test_with_statement_callback(self):
        tmp_file, tmp_path = tempfile.mkstemp(text=True)
        os.close(tmp_file)

        def callback(**kwargs):
            path = kwargs.get(TemporaryEnvironment.TEMPDIR, '')
            assert path != ''
            with open(tmp_path, 'w') as f:
                f.write(path)

        with TemporaryEnvironment(exit_callback=callback) as temp:
            path = temp.path()

        with open(tmp_path, 'r') as f:
            assert f.read() == path

        os.unlink(tmp_path)

    def test_with_statement_callback_exception(self):
        path = ''
        tmp_file, tmp_path = tempfile.mkstemp(text=True)
        os.close(tmp_file)

        def callback(**kwargs):
            path = kwargs.get(TemporaryEnvironment.TEMPDIR, '')
            assert path != ''
            with open(tmp_path, 'w') as f:
                f.write(path)

        try:
            with TemporaryEnvironment(exit_callback=callback) as temp:
                path = temp.path()
                raise RuntimeError()
        except RuntimeError:
            pass

        with open(tmp_path, 'r') as f:
            assert f.read() == path

        os.unlink(tmp_path)


class TestRpmHelper(object):
    """ RpmHelper class tests. """

    def test_is_package_installed_existing(self):
        assert RpmHelper.is_package_installed('glibc') is True
        assert RpmHelper.is_package_installed('coreutils') is True

    def test_is_package_installed_non_existing(self):
        assert RpmHelper.is_package_installed('non-existing-package') is False
        assert RpmHelper.is_package_installed('another-non-existing-package') is False

    def test_all_packages_installed_existing(self):
        assert RpmHelper.all_packages_installed(['glibc', 'coreutils']) is True

    def test_all_packages_installed_one_non_existing(self):
        assert RpmHelper.all_packages_installed(['glibc', 'coreutils', 'non-existing-package']) is False

    @pytest.mark.parametrize('string, name, epoch, version, release, arch', [
        ('libtiff-static-4.0.7-5.fc26.x86_64', 'libtiff-static', None, '4.0.7', '5.fc26', 'x86_64'),
        ('libtiff-debuginfo-4.0.8-1.fc25', 'libtiff-debuginfo', None, '4.0.8', '1.fc25', None),
        ('libtiff-tools.i686', 'libtiff-tools', None, None, None, 'i686'),
        ('libtiff-devel', 'libtiff-devel', None, None, None, None),
        ('libpng-devel-debuginfo-2:1.6.31-1.fc27.aarch64', 'libpng-devel-debuginfo', 2, '1.6.31', '1.fc27', 'aarch64'),
        (
            'python-genmsg-0.3.10-14.20130617git95ca00d.fc28',
            'python-genmsg',
            None,
            '0.3.10',
            '14.20130617git95ca00d.fc28',
            None,
        ),
        (
            'golang-github-MakeNowJust-heredoc-devel-0-0.9.gitbb23615.fc28.noarch',
            'golang-github-MakeNowJust-heredoc-devel',
            None,
            '0',
            '0.9.gitbb23615.fc28',
            'noarch',
        ),
    ], ids=[
        'libtiff-static-4.0.7-5.fc26.x86_64',
        'libtiff-debuginfo-4.0.8-1.fc25',
        'libtiff-tools.i686',
        'libtiff-devel',
        'libpng-devel-debuginfo-2:1.6.31-1.fc27.aarch64',
        'python-genmsg-0.3.10-14.20130617git95ca00d.fc28',
        'golang-github-MakeNowJust-heredoc-devel-0-0.9.gitbb23615.fc28.noarch',
    ])
    def test_split_nevra(self, string, name, epoch, version, release, arch):
        assert RpmHelper.split_nevra(string) == dict(name=name, epoch=epoch, version=version,
                                                     release=release, arch=arch)


class TestMacroHelper(object):

    def test_get_macros(self):
        rpm.addMacro('test_macro', 'test_macro value')
        macros = MacroHelper.dump()
        macros = MacroHelper.filter(macros, name='test_macro', level=-1)
        assert len(macros) == 1
        assert macros[0]['name'] == 'test_macro'
        assert macros[0]['value'] == 'test_macro value'
        assert macros[0]['level'] == -1


class TestLookasideCacheHelper(object):

    @pytest.mark.parametrize('package, filename, hashtype, hash', [
        ('vim-go', 'v1.6.tar.gz', 'md5', '847d3e3577982a9515ad0aec6d5111b2'),
        ('rebase-helper', '0.8.0.tar.gz', 'md5', '91de540caef64cb8aa7fd250f2627a93'),
        (
            'man-pages',
            'man-pages-posix-2013-a.tar.xz',
            'sha512',
            'e6ec8eb57269fadf368aeaac31b5a98b9c71723d4d5cc189f9c4642d6e865c88'
            'e44f77481dccbdb72e31526488eb531f624d455016361687a834ccfcac19fa14',
        ),
    ], ids=[
        'vim-go',
        'rebase-helper',
        'man-pages',
    ])
    def test_download(self, package, filename, hashtype, hash):
        target = os.path.basename(filename)
        LookasideCacheHelper._download_source('fedpkg',
                                              'https://src.fedoraproject.org/repo/pkgs',
                                              package,
                                              filename,
                                              hashtype,
                                              hash,
                                              target)
        assert os.path.isfile(target)
        assert LookasideCacheHelper._hash(target, hashtype) == hash
