# -*- coding: utf-8 -*-


import sys
import os
from rebasehelper.cli import CLI
from rebasehelper.application import Application


def rebase_helper(args=None):
    cli = CLI()
    app = Application(cli)
    ret = app.run()

if __name__ == "__main__":
    sys.exit(main())
