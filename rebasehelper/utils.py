# -*- coding: utf-8 -*-

import subprocess

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
    return sp.returncode
