# -*- coding: utf-8 -*-

import os
import tempfile
import shutil
from rebasehelper.utils import ProcessHelper

class TestProcessHelper(object):
    """ProcessHelper tests"""

    class TestRunSubprocessCwd(object):
        """ProcessHelper - run_subprocess_cwd() tests"""
        TEMP_FILE = "temp_file"
        TEMP_DIR = "temp_dir"
        OUT_FILE = "output_file"
        PHRASE = "hello world"
        ECHO_COMMAND = ["echo", PHRASE]
        TOUCH_COMMAND = ["touch", TEMP_FILE]
        LS_COMMAND = ["ls"]
        WORKING_DIR = tempfile.gettempdir()

        def setup(self):
            self.WORKING_DIR = tempfile.mkdtemp(prefix="rebase-helper-test-")
            os.chdir(self.WORKING_DIR)

        def teardown(self):
            os.chdir(tempfile.gettempdir())
            shutil.rmtree(self.WORKING_DIR)
            self.WORKING_DIR = tempfile.gettempdir()

        def test_simple_cmd(self):
            ret = ProcessHelper.run_subprocess_cwd(self.TOUCH_COMMAND)
            assert ret == 0
            assert os.path.exists(self.TEMP_FILE)

        def test_simple_cmd_with_redirected_output(self):
            ret = ProcessHelper.run_subprocess_cwd(self.ECHO_COMMAND,
                                                   output=self.OUT_FILE)
            assert ret == 0
            assert os.path.exists(self.OUT_FILE)
            assert open(self.OUT_FILE).readline().strip("\n") == self.PHRASE

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
                                                   self.OUT_FILE)
            assert ret == 0
            assert os.path.exists(os.path.join(self.TEMP_DIR, self.TEMP_FILE))
            assert os.path.exists(self.OUT_FILE)
            assert open(self.OUT_FILE).readline().strip("\n") == self.TEMP_FILE
