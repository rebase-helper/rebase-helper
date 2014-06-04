# -*- coding: utf-8 -*-

import os
import sys
import shutil

from rebasehelper.archive import Archive
from rebasehelper.specfile import Specfile
from rebasehelper.patch_checker import Patch
from rebasehelper.build_helper import *
from rebasehelper.diff_helper import diff_tools
from rebasehelper.logger import logger
from rebasehelper.settings import *

def extract_sources(source_name, source_dir):
    """
    Function extracts tar ball and returns a full dirname to sources
    """
    if os.path.isdir(source_dir):
        shutil.rmtree(source_dir)
    arch = Archive(source_name)
    arch.extract(source_dir)
    package_dir = ""
    for dir_name in os.listdir(source_dir):
        package_dir = dir_name
    return os.path.join(os.getcwd(), source_dir, package_dir)


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

    def check_build_argument(self):
        if self.conf.build not in build_tools.keys():
            logger.error('You have to specify one of these builders {0}'.format(build_tools.keys()))
            sys.exit(0)

    def check_difftool_argument(self):
        if self.conf.difftool not in diff_tools.keys():
            logger.error('You have to specify one of these builders {0}'.format(diff_tools.keys()))
            sys.exit(0)

    def run(self):
        kwargs = dict()
        if self.conf.build:
            self.check_build_argument()
            builder = Builder(self.conf.build)
            kwargs['spec'] = self.conf.specfile
            kwargs['sources'] = self.conf.sources
            builder.build(kwargs)
            sys.exit(0)

        spec_file = self.get_spec_file()
        patches = None
        if spec_file:
            spec = Specfile(spec_file)
            patches = spec.get_patches()
            old_sources = spec.get_old_sources()
            old_dir = extract_sources(old_sources, settings.OLD_SOURCES)
            new_dir = extract_sources(self.conf.sources, settings.NEW_SOURCES)
        if patches:
            kwargs['patches'] = patches
            kwargs['old_dir'] = old_dir
            kwargs['new_dir'] = new_dir
            kwargs['diff_tool'] = self.conf.difftool
            patch = Patch(**kwargs)
            patch.run_patch()
            if self.conf.patches:
                sys.exit(0)



if __name__ == '__main__':
    a = Application(None)
    a.run()
