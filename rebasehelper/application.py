# -*- coding: utf-8 -*-

import os
import sys
import shutil

from rebasehelper.archive import Archive
from rebasehelper.specfile import SpecFile
from rebasehelper.patch_helper import PatchTool
from rebasehelper.build_helper import Builder, build_tools
from rebasehelper.diff_helper import diff_tools
from rebasehelper.pkgdiff_checker import PkgCompare, pkgdiff_tools
from rebasehelper.logger import logger
from rebasehelper import settings
from rebasehelper.utils import get_value_from_kwargs


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
        self.spec.update_new_version()
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

    def check_build_argument(self):
        """
        Function checks whether build argument is allowed
        """
        if self.conf.buildtool not in build_tools.keys():
            logger.error('You have to specify one of these builders {0}'.format(build_tools.keys()))
            sys.exit(0)

    def check_difftool_argument(self):
        """
        Function checks whether difftool argument is allowed
        """
        if self.conf.difftool not in diff_tools.keys():
            logger.error('You have to specify one of these builders {0}'.format(diff_tools.keys()))
            sys.exit(0)

    def check_pkgdiff_argument(self):
        """
        Function checks whether pkgdifftool argument is allowed
        """
        if self.conf.pkgcomparetool not in pkgdiff_tools.keys():
            logger.error('You have to specify one of these package diff tool {0}'.format(pkgdiff_tools.keys()))
            sys.exit(0)

    def build_packages(self):
        """
        Function calls build class for building packages
        """
        self.check_build_argument()
        builder = Builder(self.conf.buildtool)
        old_patches = get_value_from_kwargs(self.kwargs, 'patches')
        self.kwargs['old']['patches'] = [p[0] for p in old_patches.itervalues()]
        new_patches = get_value_from_kwargs(self.kwargs, 'patches', source='new')
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
        self.check_pkgdiff_argument()
        pkgchecker = PkgCompare(self.conf.pkgcomparetool)
        pkgchecker.compare_pkgs(**self.kwargs)

    def run(self):
        if not os.path.exists(settings.REBASE_RESULTS_DIR):
            os.makedirs(settings.REBASE_RESULTS_DIR)
        self._initialize_dictionary()
        self.spec_file = self._get_spec_file()
        if not self.spec_file:
            logger.error('You have to define a SPEC file.')
            sys.exit(1)
        self.spec = SpecFile(self.spec_file, self.conf.sources)
        self.old_sources = self.spec.get_old_tarball()
        self.spec.get_new_tarball()

        old_dir = extract_sources(self.old_sources, settings.OLD_SOURCES)
        new_dir = extract_sources(self.conf.sources, settings.NEW_SOURCES)
        self._initialize_data()

        if not self.conf.sources:
            logger.error('You have to define a new sources.')
            sys.exit(0)

        if not self.conf.build_only:
            self.kwargs['old_dir'] = old_dir
            self.kwargs['new_dir'] = new_dir
            self.kwargs['diff_tool'] = self.conf.difftool
            patch = PatchTool(self.conf.patchtool)
            try:
                self.kwargs['new']['patches'] = patch.patch(**self.kwargs)
            except Exception as e:
                if os.path.exists(self.spec.get_rebased_spec()):
                    os.unlink(self.spec.get_rebased_spec())
                logger.error(e.message)
                sys.exit(0)
            self.spec.write_updated_patches(**self.kwargs)
        # Build packages
        self.build_packages()

        # Perform checks
        self.pkgdiff_packages()


if __name__ == '__main__':
    a = Application(None)
    a.run()
