# -*- coding: utf-8 -*-

import subprocess
import tempfile
import os
import openscap_api as openscap
import sys


def run_subprocess(cmd):
    sp = subprocess.Popen(cmd,
                          stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT,
                          shell=False)

    while True:
        lines = sp.stdout.readline()
        if lines == "":
            break
        print lines,
    sp.wait()
    print 'Exit code:', sp.returncode
    return sp.returncode

class Application(object):
    result_file = ""
    temp_dir = ""

    def __init__(self, conf):
        """ conf is CLI object """
        self.conf = conf

    def build_command(self):
        """
        create command from CLI options
        """
        command = [self.binary]
        command.extend(self.command_eval)
        if self.conf.devel:
            command.append("--devel")
        if self.conf.verbose:
            command.append("--verbose")
        return command

    def run(self):
        cmd = self.build_command()
        print "running command:\n%s" % ' '.join(cmd)

if __name__ == '__main__':
    a = Application(None)
    a.run()
