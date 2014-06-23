# -*- coding: utf-8 -*-

import os
import sys
import shutil
import logging

from rebasehelper.archive import Archive
from rebasehelper.specfile import SpecFile
from rebasehelper.logger import logger
from rebasehelper import settings, patch_helper, build_helper
from rebasehelper import output_tool
from rebasehelper.utils import get_value_from_kwargs
from rebasehelper.base_checker import Checker
import rebasehelper.pkgdiff_checker


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
    except IOError as ioe:
        logger.error("Archive with the name {0} does not exist or is corrupted.".format(source_name))
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
    old_sources = ""
    spec_file = ""

    def __init__(self, conf):
        """ conf is CLI object """
        self.conf = conf

    def _initialize_dictionary(self):
        """
        Function initializes a dictionaries used by rebase-helper
        """
        self.kwargs = {}
        self.kwargs['old'] = {}
        self.kwargs['new'] = {}

    def _initialize_data(self):
        """
        Function fill dictionary by default data
        """
        old_values = {}
        old_values['spec'] = os.path.join(os.getcwd(), self.spec_file)
        self.kwargs['old'] = old_values
        self.kwargs['old'].update(self.spec.get_old_information())
        new_values = {}
        new_values['spec'] = os.path.join(os.getcwd(), self.spec.get_rebased_spec())
        self.kwargs['new'] = new_values
        self.kwargs['new'].update(self.spec.get_new_information())

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

    def build_packages(self):
        """
        Function calls build class for building packages
        """
        if not build_helper.check_build_argument(self.conf.buildtool):
            sys.exit(0)
        builder = build_helper.Builder(self.conf.buildtool)
        old_patches = get_value_from_kwargs(self.kwargs, settings.FULL_PATCHES)
        self.kwargs['old']['patches'] = [p[0] for p in old_patches.itervalues()]
        new_patches = get_value_from_kwargs(self.kwargs, settings.FULL_PATCHES, source='new')
        self.kwargs['new']['patches'] = [p[0] for p in new_patches.itervalues()]
        # TODO: need to create some results directory where results of tests
        # will be stored!!! The results dir should be removed on startup
        # or the tool should fail if it exists
        result_path = os.path.join(os.getcwd(), "rebase-helper-results")
        if os.path.exists(result_path):
            shutil.rmtree(result_path)
        self.kwargs['resultdir'] = result_path
        builder.build_packages(**self.kwargs)

    def pkgdiff_packages(self):
        """
        Function calls pkgdiff class for comparing packages
        :return:
        """
        try:
            pkgchecker = Checker(self.conf.pkgcomparetool)
        except NotImplementedError:
            logger.error('You have to specify one of these check tools {0}'.format(Checker.get_supported_tools()))
            sys.exit(1)
        else:
            pkgchecker.run_check(**self.kwargs)

    def print_summary(self):
        output_tool.check_output_argument(self.conf.outputtool)
        output = output_tool.OutputTool(self.conf.outputtool)
        output.print_information(**self.kwargs)

    def run(self):
        if self.conf.verbose:
            logger.setLevel(logging.DEBUG)
        if not os.path.exists(settings.REBASE_RESULTS_DIR):
            os.makedirs(settings.REBASE_RESULTS_DIR)
        self._initialize_dictionary()
        self.spec_file = self._get_spec_file()
        if not self.spec_file:
            logger.error('You have to define a SPEC file.')
            sys.exit(1)
        self.spec = SpecFile(self.spec_file, self.conf.sources)
        self.old_sources, new_sources = self.spec.get_tarballs()
        if new_sources:
            self.conf.sources = new_sources

        old_dir = extract_sources(self.old_sources, settings.OLD_SOURCES)
        new_dir = extract_sources(self.conf.sources, settings.NEW_SOURCES)
        self._initialize_data()

        if not self.conf.sources:
            logger.error('You have to define a new sources.')
            sys.exit(0)

        if not self.conf.build_only:
            # Patch sources
            if not patch_helper.check_difftool_argument(self.conf.difftool):
                sys.exit(0)
            self.kwargs['old_dir'] = old_dir
            self.kwargs['new_dir'] = new_dir
            self.kwargs['diff_tool'] = self.conf.difftool
            patch = patch_helper.Patch(self.conf.patchtool)
            try:
                self.kwargs['new']['patches'] = patch.patch(**self.kwargs)
            except Exception as e:
                if os.path.exists(self.spec.get_rebased_spec()):
                    os.unlink(self.spec.get_rebased_spec())
                logger.error(e.message)
                sys.exit(0)
            update_patches = self.spec.write_updated_patches(**self.kwargs)
            self.kwargs['summary_info'] = update_patches
            if self.conf.patch_only:
                self.print_summary()
                sys.exit(0)
        # Build packages
        self.build_packages()

        # Perform checks
        self.pkgdiff_packages()

        # print summary information
        self.print_summary()


if __name__ == '__main__':
    a = Application(None)
    a.run()
