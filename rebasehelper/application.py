# -*- coding: utf-8 -*-

import os
import sys
import shutil

from rebasehelper.archive import Archive
from rebasehelper.specfile import SpecFile
from rebasehelper.patch_checker import PatchTool
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
    arch = None
    try:
        arch = Archive(source_name)
        arch.extract(source_dir)
    except NotImplementedError as nie:
        if nie.message == "Unsupported archive type":
            logger.error("This archive is not supported yet.")
        sys.exit(0)
    package_dir = ""
    for dir_name in os.listdir(source_dir):
        package_dir = dir_name
    return os.path.join(os.getcwd(), source_dir, package_dir)


class Application(object):
    result_file = ""
    temp_dir = ""
    kwargs = {}
    spec = None

    def __init__(self, conf):
        """ conf is CLI object """
        self.conf = conf

    def _initialize_dictionary(self):
        self.kwargs = {}
        self.kwargs['old'] = {}
        self.kwargs['new'] = {}

    def _initialize_data(self):
        spec_file = self._get_spec_file()
        if not spec_file:
            logger.error('You have to define a SPEC file.')
            sys.exit(1)
        self.spec = SpecFile(spec_file)
        old_values = {}
        old_values['spec'] = os.path.join(os.getcwd(), spec_file)
        old_values['sources'] = self.spec.get_all_sources()
        old_values['patches'] = self.spec.get_patches()
        self.kwargs['old'] = old_values
        new_values = {}
        new_values['spec'] = os.path.join(os.getcwd(), self.spec.get_rebased_spec())
        new_values['sources'] = self.spec.get_all_sources()
        self.kwargs['new'] = new_values

    def _build_command(self, binary):
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

    def _get_spec_file(self):
        """
        Function get a spec file from current directory
        """
        cwd = os.getcwd()
        spec_file = None
        for filename in os.listdir(cwd):
            if filename.endswith(".spec"):
                if settings.REBASE_HELPER_SUFFIX in filename:
                    continue
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

    def build_packages(self):
        self.check_build_argument()
        builder = Builder(self.conf.build)
        old_patches = self.kwargs['old'].get('patches')
        self.kwargs['old']['patches'] = [p[0] for p in old_patches.itervalues()]
        new_patches = self.kwargs['new'].get('patches')
        self.kwargs['new']['patches'] = [p[0] for p in new_patches.itervalues()]
        # TODO: need to create some results directory where results of tests
        # will be stored!!! The results dir should be removed on startup
        # or the tool should fail if it exists
        result_path = os.path.join(os.getcwd(), "rebase-helper-results")
        if os.path.exists(result_path):
            shutil.rmtree(result_path)

        self.kwargs['resultdir'] = result_path
        builder.build(**self.kwargs)

    def run(self):
        if not os.path.exists(settings.REBASE_RESULTS_DIR):
            os.makedirs(settings.REBASE_RESULTS_DIR)
        self._initialize_dictionary()
        self._initialize_data()

        if not self.conf.sources:
            logger.error('You have to define a new sources.')
            sys.exit(0)
        if not os.path.exists(self.conf.sources):
            logger.error('Defined sources does not exist.')
            sys.exit(0)
        old_sources = self.spec.get_old_tarball()
        old_dir = extract_sources(old_sources, settings.OLD_SOURCES)
        new_dir = extract_sources(self.conf.sources, settings.NEW_SOURCES)
        if not self.conf.build_only:
            self.kwargs['old_dir'] = old_dir
            self.kwargs['new_dir'] = new_dir
            self.kwargs['diff_tool'] = self.conf.difftool
            patch = PatchTool(self.conf.patch_tool)
            try:
                self.kwargs['new']['patches'] = patch.patch(**self.kwargs)
            except Exception as e:
                if os.path.exists(self.spec.get_rebased_spec()):
                    os.unlink(self.spec.get_rebased_spec())
                logger.error(e.message)
                sys.exit(0)
            self.spec.write_updated_patches(**self.kwargs)
        self.build_packages()


if __name__ == '__main__':
    a = Application(None)
    a.run()
