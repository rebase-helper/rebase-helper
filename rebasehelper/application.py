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
from rebasehelper import settings

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

    def build_packages(self, spec_file, sources, patches):
        kwargs = {}
        self.check_build_argument()
        builder = Builder(self.conf.build)
        kwargs['spec'] = os.path.join(os.getcwd(), spec_file)
        kwargs['sources'] = sources
        kwargs['patches'] = [ p[0] for p in patches.itervalues() ]
        # TODO: need to create some results directory where results of tests
        # will be stored!!! The results dir should be removed on startup
        # or the tool should fail if it exists
        kwargs['resultdir'] = os.path.join(os.getcwd(), "rebase-helper-results")
        builder.build(**kwargs)

    def run(self):
        kwargs = dict()
        spec_file = self.get_spec_file()
        if not spec_file:
            logger.error('You have to define a SPEC file.')
            sys.exit(1)
        spec = Specfile(spec_file)
        sources = spec.get_all_sources()
        patches = spec.get_patches()

        if self.conf.build:
            self.build_packages(spec_file, sources, patches)
            sys.exit(0)

        if not self.conf.sources:
            logger.error('You have to define a new sources.')
            sys.exit(0)
        if not os.path.exists(self.conf.sources):
            logger.error('Defined sources does not exist.')
            sys.exit(0)
        old_sources = spec.get_old_sources()
        old_dir = extract_sources(old_sources, settings.OLD_SOURCES)
        new_dir = extract_sources(self.conf.sources, settings.NEW_SOURCES)
        if patches:
            kwargs['patches'] = patches
            kwargs['old_dir'] = old_dir
            kwargs['new_dir'] = new_dir
            kwargs['diff_tool'] = self.conf.difftool
            patch = Patch(**kwargs)
            try:
                patches = patch.run_patch()
            except Exception as e:
                logger.error(e.message)
                sys.exit(0)
                #os.unlink(spec.get_rebased_spec())
            spec.write_updated_patches(patches)
            if self.conf.patches:
                sys.exit(0)
        if not self.conf.build:
            self.conf.build = 'mock'
        self.build_packages(spec_file, sources, patches)


if __name__ == '__main__':
    a = Application(None)
    a.run()
