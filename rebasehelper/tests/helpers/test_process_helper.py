# -*- coding: utf-8 -*-
#
# This tool helps you rebase your package to the latest version
# Copyright (C) 2013-2019 Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
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
# Authors: Petr Hráček <phracek@redhat.com>
#          Tomáš Hozza <thozza@redhat.com>
#          Nikola Forró <nforro@redhat.com>
#          František Nečas <fifinecas@seznam.cz>

import io
import os
import random
import string

from typing import List

from rebasehelper.helpers.process_helper import ProcessHelper


class TestProcessHelper:
    """ ProcessHelper tests """

    class TestRunSubprocess:
        """ ProcessHelper - run_subprocess() tests """
        TEMP_FILE: str = "temp_file"
        TEMP_DIR: str = "temp_dir"
        OUT_FILE: str = "output_file"
        IN_FILE: str = "input_file"
        PHRASE: str = "hello world"
        ECHO_COMMAND: List[str] = ["echo", PHRASE]
        TOUCH_COMMAND: List[str] = ["touch", TEMP_FILE]
        LS_COMMAND: List[str] = ["ls"]
        CAT_COMMAND: List[str] = ["cat"]

        def test_simple_cmd(self):
            ret = ProcessHelper.run_subprocess(self.TOUCH_COMMAND)
            assert ret == 0
            assert os.path.exists(self.TEMP_FILE)

        def test_simple_cmd_with_redirected_output_path(self):
            ret = ProcessHelper.run_subprocess(self.ECHO_COMMAND,
                                               output_file=self.OUT_FILE)
            assert ret == 0
            assert os.path.exists(self.OUT_FILE)
            assert open(self.OUT_FILE).readline().strip('\n') == self.PHRASE

        def test_simple_cmd_with_redirected_output_fileobject(self):
            buff = io.StringIO()
            ret = ProcessHelper.run_subprocess(self.ECHO_COMMAND,
                                               output_file=buff)
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
                                               input_file=self.IN_FILE,
                                               output_file=self.OUT_FILE)
            assert ret == 0
            assert os.path.exists(self.OUT_FILE)
            assert open(self.OUT_FILE).readline().strip('\n') == self.PHRASE

        def test_simple_cmd_with_input_fileobject_and_redirected_output_path(self):
            in_buff = io.StringIO()
            in_buff.write(self.PHRASE)

            assert not os.path.exists(self.IN_FILE)
            in_buff.seek(0)
            assert in_buff.readline().strip('\n') == self.PHRASE

            ret = ProcessHelper.run_subprocess(self.CAT_COMMAND,
                                               input_file=in_buff,
                                               output_file=self.OUT_FILE)
            in_buff.close()
            assert ret == 0
            assert os.path.exists(self.OUT_FILE)
            assert open(self.OUT_FILE).readline().strip('\n') == self.PHRASE

        def test_simple_cmd_with_input_path_and_redirected_output_fileobject(self):
            out_buff = io.StringIO()
            with open(self.IN_FILE, 'w') as f:
                f.write(self.PHRASE)

            assert os.path.exists(self.IN_FILE)
            assert open(self.IN_FILE).readline().strip('\n') == self.PHRASE

            ret = ProcessHelper.run_subprocess(self.CAT_COMMAND,
                                               input_file=self.IN_FILE,
                                               output_file=out_buff)
            assert ret == 0
            assert not os.path.exists(self.OUT_FILE)
            out_buff.seek(0)
            assert out_buff.readline().strip('\n') == self.PHRASE
            out_buff.close()

        def test_simple_cmd_with_input_fileobject_and_redirected_output_fileobject(self):
            out_buff = io.StringIO()
            in_buff = io.StringIO()
            in_buff.write(self.PHRASE)

            assert not os.path.exists(self.IN_FILE)
            in_buff.seek(0)
            assert in_buff.readline().strip('\n') == self.PHRASE

            ret = ProcessHelper.run_subprocess(self.CAT_COMMAND,
                                               input_file=in_buff,
                                               output_file=out_buff)
            in_buff.close()
            assert ret == 0
            assert not os.path.exists(self.OUT_FILE)
            out_buff.seek(0)
            assert out_buff.readline().strip('\n') == self.PHRASE
            out_buff.close()

    class TestRunSubprocessCwd:
        """ ProcessHelper - run_subprocess_cwd() tests """
        TEMP_FILE: str = "temp_file"
        TEMP_DIR: str = "temp_dir"
        OUT_FILE: str = "output_file"
        PHRASE: str = "hello world"
        ECHO_COMMAND: List[str] = ["echo", PHRASE]
        TOUCH_COMMAND: List[str] = ["touch", TEMP_FILE]
        LS_COMMAND: List[str] = ["ls"]

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
                                                   output_file=self.OUT_FILE)
            assert ret == 0
            assert os.path.exists(os.path.join(self.TEMP_DIR, self.TEMP_FILE))
            assert os.path.exists(self.OUT_FILE)
            assert open(self.OUT_FILE).readline().strip("\n") == self.TEMP_FILE

    class TestRunSubprocessCwdEnv:
        """ ProcessHelper - run_subprocess_cwd_env() tests """
        OUT_FILE: str = "output_file"
        PHRASE: str = "hello world"

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
                                                       output_file=self.OUT_FILE,
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
                                                       output_file=self.OUT_FILE,
                                                       shell=True)
            assert ret == 0
            assert os.path.exists(self.OUT_FILE)
            assert open(self.OUT_FILE).readline().strip("\n") == self.PHRASE
