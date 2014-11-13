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
from six import StringIO

from .base_test import BaseTest
from rebasehelper.utils import ConsoleHelper
from rebasehelper.utils import ProcessHelper
from rebasehelper.utils import PathHelper
from rebasehelper.utils import TemporaryEnvironment
from rebasehelper.utils import RpmHelper


class TestConsoleHelper(BaseTest):
    """
    ConsoleHelper tests
    """

    @staticmethod
    def _setup_fake_IO(input_str):
        """
        Function to setup fake STDIN and STDOUT for console testing.
        """
        #  Use StringIO to be able to write and read to STDIN and from STDOUT
        sys.stdin = StringIO(input_str)
        sys.stdout = StringIO()

    def test_get_message_yes(self):
        question = 'bla bla'
        answer = 'yes'

        self._setup_fake_IO(answer)
        inp = ConsoleHelper.get_message(question)
        sys.stdout.seek(0)

        assert sys.stdout.readline() == question + ' ([y]/n)? '
        assert inp is True

    def test_get_message_no(self):
        question = 'bla bla'
        answer = 'no'

        self._setup_fake_IO(answer)
        inp = ConsoleHelper.get_message(question)
        sys.stdout.seek(0)

        assert sys.stdout.readline() == question + ' ([y]/n)? '
        assert inp is False

    def test_get_message_yes_default_no(self):
        question = 'bla bla'
        answer = 'yes'

        self._setup_fake_IO(answer)
        inp = ConsoleHelper.get_message(question, default_yes=False)
        sys.stdout.seek(0)

        assert sys.stdout.readline() == question + ' (y/[n])? '
        assert inp is True

    def test_get_message_no_input_default_yes(self):
        question = 'bla bla'
        answer = '\n'

        self._setup_fake_IO(answer)
        inp = ConsoleHelper.get_message(question)
        sys.stdout.seek(0)

        assert sys.stdout.readline() == question + ' ([y]/n)? '
        assert inp is True

    def test_get_message_no_input_default_no(self):
        question = 'bla bla'
        answer = '\n'

        self._setup_fake_IO(answer)
        inp = ConsoleHelper.get_message(question, default_yes=False)
        sys.stdout.seek(0)

        assert sys.stdout.readline() == question + ' (y/[n])? '
        assert inp is False

    def test_get_message_any_input_default_yes(self):
        question = 'bla bla'
        answer = 'random input\ndsfdf'

        self._setup_fake_IO(answer)
        inp = ConsoleHelper.get_message(question, any_input=True)
        sys.stdout.seek(0)

        assert sys.stdout.readline() == question + ' '
        assert inp is True

    def test_get_message_any_input_default_no(self):
        question = 'bla bla'
        answer = 'random input\n'

        self._setup_fake_IO(answer)
        inp = ConsoleHelper.get_message(question, default_yes=False, any_input=True)
        sys.stdout.seek(0)

        assert sys.stdout.readline() == question + ' '
        assert inp is False


class TestProcessHelper(BaseTest):
    """ ProcessHelper tests """

    class TestRunSubprocess(BaseTest):
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
        WORKING_DIR = tempfile.gettempdir()

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

    class TestRunSubprocessCwd(BaseTest):
        """ ProcessHelper - run_subprocess_cwd() tests """
        TEMP_FILE = "temp_file"
        TEMP_DIR = "temp_dir"
        OUT_FILE = "output_file"
        PHRASE = "hello world"
        ECHO_COMMAND = ["echo", PHRASE]
        TOUCH_COMMAND = ["touch", TEMP_FILE]
        LS_COMMAND = ["ls"]
        WORKING_DIR = tempfile.gettempdir()

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

    class TestRunSubprocessCwdEnv(BaseTest):
        """ ProcessHelper - run_subprocess_cwd_env() tests """
        OUT_FILE = "output_file"
        PHRASE = "hello world"
        WORKING_DIR = tempfile.gettempdir()

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

    class TestPathHelperFindBase(BaseTest):
        """ Base class for find methods """
        WORKING_DIR = tempfile.gettempdir()
        dirs = ["dir1",
                "dir1/foo",
                "dir1/faa",
                "dir1/foo/bar",
                "dir1/foo/baz",
                "dir1/bar",
                "dir1/baz",
                "dir1/baz/bar"]
        files = ["file",
                 "ffile",
                 "ppythooon",
                 "dir1/fileee",
                 "dir1/faa/pythooon",
                 "dir1/foo/pythooon",
                 "dir1/foo/bar/file",
                 "dir1/foo/baz/file",
                 "dir1/baz/ffile",
                 "dir1/bar/file",
                 "dir1/baz/bar/ffile",
                 "dir1/baz/bar/test.spec"]

        def setup(self):
            super(TestPathHelper.TestPathHelperFindBase, self).setup()
            for d in self.dirs:
                os.mkdir(d)
            for f in self.files:
                with open(f, "w") as fd:
                    fd.write(f)

    class TestFindFirstDirWithFile(TestPathHelperFindBase):
        """ PathHelper - find_first_dir_with_file() tests """
        def test_find_file(self):
            assert PathHelper.find_first_dir_with_file(
                "dir1", "file") == os.path.abspath(
                os.path.dirname(self.files[9]))
            assert PathHelper.find_first_dir_with_file(
                os.path.curdir, "file") == os.path.abspath(os.path.dirname(self.files[0]))
            assert PathHelper.find_first_dir_with_file(
                "dir1/baz", "file") is None

        def test_find_ffile(self):
            assert PathHelper.find_first_dir_with_file(
                "dir1", "*le") == os.path.abspath(
                os.path.dirname(self.files[8]))
            assert PathHelper.find_first_dir_with_file(
                "dir1", "ff*") == os.path.abspath(
                os.path.dirname(self.files[8]))
            assert PathHelper.find_first_dir_with_file(
                "dir1/foo", "ff*") is None

        def test_find_pythoon(self):
            assert PathHelper.find_first_dir_with_file(
                "dir1", "pythooon") == os.path.abspath(
                os.path.dirname(self.files[4]))
            assert PathHelper.find_first_dir_with_file(
                os.path.curdir, "py*n") == os.path.abspath(os.path.dirname(self.files[4]))
            assert PathHelper.find_first_dir_with_file(
                "dir1/bar", "pythooon") is None

    class TestFindFirstFile(TestPathHelperFindBase):
        """ PathHelper - find_first_file() tests """
        def test_find_file(self):
            assert PathHelper.find_first_file(
                "dir1", "file") == os.path.abspath(self.files[9])
            assert PathHelper.find_first_file(
                os.path.curdir, "file") == os.path.abspath(self.files[0])
            assert PathHelper.find_first_file("dir1/baz", "file") is None

        def test_find_ffile(self):
            assert PathHelper.find_first_file(
                "dir1", "*le") == os.path.abspath(self.files[8])
            assert PathHelper.find_first_file(
                "dir1", "ff*") == os.path.abspath(self.files[8])
            assert PathHelper.find_first_file("dir1/foo", "ff*") is None

        def test_find_pythoon(self):
            assert PathHelper.find_first_file(
                "dir1", "pythooon") == os.path.abspath(self.files[4])
            assert PathHelper.find_first_file(
                os.path.curdir, "py*n") == os.path.abspath(self.files[4])
            assert PathHelper.find_first_file("dir1/bar", "pythooon") is None

        def test_find_with_recursion(self):
            assert PathHelper.find_first_file(os.path.curdir, "*.spec", 0) is None
            assert PathHelper.find_first_file(os.path.curdir, "*.spec", 1) is None
            assert PathHelper.find_first_file(os.path.curdir, "*.spec", 2) is None
            assert PathHelper.find_first_file(os.path.curdir, "*.spec", 3) == os.path.abspath(self.files[-1])

        def test_find_without_recursion(self):
            assert PathHelper.find_first_file(os.path.curdir, "*.spec") == os.path.abspath(self.files[-1])


class TestTemporaryEnvironment(BaseTest):
    """ TemporaryEnvironment class tests. """

    def test_with_statement(self):
        path = ''
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
        path = ''
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


class TestRpmHelper(BaseTest):
    """ RpmHelper class tests. """

    def test_is_package_installed_existing(self):
        assert RpmHelper.is_package_installed('kernel') is True
        assert RpmHelper.is_package_installed('filesystem') is True

    def test_is_package_installed_non_existing(self):
        assert RpmHelper.is_package_installed('non-existing-package') is False
        assert RpmHelper.is_package_installed('another-non-existing-package') is False

    def test_all_packages_installed_existing(self):
        assert RpmHelper.all_packages_installed(['kernel', 'filesystem']) is True

    def test_all_packages_installed_one_non_existing(self):
        assert RpmHelper.all_packages_installed(['kernel', 'filesystem', 'non-existing-package']) is False
