#!/usr/bin/python -tt
# -*- coding: utf-8 -*-


import sys
import os
from rebasehelper.cli import CLI
from rebasehelper.application import Application

def main(args=None):
    cli = CLI()
    app = Application(cli)
    ret = app.run()
    return ret


if __name__ == "__main__":
    sys.exit(main())
