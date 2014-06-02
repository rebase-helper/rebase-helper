# -*- coding: utf-8 -*-

import os
import sys

from rebasehelper.specfile import Specfile
from rebasehelper.patch_checker import Patch
class Application(object):
    result_file = ""
    temp_dir = ""

    def __init__(self, conf):
        """ conf is CLI object """
        self.conf = conf

    def build_command(self,binary):
        """
        create command from CLI options
        """
        command = [binary]
        command.extend(self.command_eval)
        if self.conf.devel:
            command.append("--devel")
        if self.conf.verbose:
            command.append("--verbose")
        return command

    def get_spec_file(self):
        """
        Function get a spec file from current directory
        """
        cwd = os.getcwd()
        spec_file = None
        for filename in os.listdir(cwd):
            if filename.endswith(".spec"):
                spec_file = filename
                break
        return spec_file

    def run(self):
        spec_file = self.get_spec_file()
        if spec_file:
            spec = Specfile(spec_file)
            patches = spec.get_patches()

        if patches:
            patch = Patch(patches)
            patch.run_patch()



if __name__ == '__main__':
    a = Application(None)
    a.run()
