# -*- coding: utf-8 -*-

# This tool helps you to rebase package to the latest version
# Copyright (C) 2013 Petr Hracek
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# he Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

try:
    from functools import reduce
except ImportError:
    pass  # we're on Python 2 => ok
import os
try:
    import rpm
except ImportError:
    pass
import re
from rebasehelper.utils import DownloadHelper
from rebasehelper.logger import logger
from rebasehelper import settings
from rebasehelper.utils import get_content_file, write_to_file
from rebasehelper.utils import check_empty_patch
from rebasehelper.archive import Archive


PATCH_PREFIX = '%patch'


def get_source_name(name):
    """
    Function returns a source name from full URL address
    :param name:
    :return:
    """
    new_name = name.split('/')[-1]
    return new_name


def get_rebase_name(name):
    """
    Function returns a name in results directory
    :param name:
    :return: full path to results dir with name
    """
    dir_name = os.path.dirname(name)
    file_name = os.path.basename(name)
    return os.path.join(dir_name, settings.REBASE_HELPER_RESULTS_DIR, file_name)


class SpecFile(object):
    """
    Class who manipulates with SPEC file
    """
    spec_file = ""
    download = False
    spec_content = []
    spc = None
    hdr = None
    sources = None
    source_files = None
    patches = None

    def __init__(self, spec_file, sources=None, download=True):
        self.spec_file = spec_file
        self.download = download
        self._update_data()
        if sources:
            self.new_sources = sources
            self.set_spec_version()

    def _update_data(self):
        """
        Function updates data from given SPEC file
        :return:
        """
        # Load rpm information
        self.spc = rpm.spec(self.spec_file)
        # Content of whole SPEC file
        self.spec_content = self._get_content_spec()
        # HEADER of SPEC file
        self.hdr = self.spc.sourceHeader
        # ALL sources mentioned in SPEC file
        self.sources = self.spc.sources
        # All patches mentioned in SPEC file
        self.patches = [x for x in self.sources if x[2] == 2]
        # All source file mentioned in SPEC file Source[0-9]*
        self.source_files = [x for x in self.sources if x[2] == 0 or x[2] == 1]

    def get_patch_option(self, line):
        """
        Function returns a patch options
        :param line:
        :return: patch options like -p1
        """
        spl = line.strip().split()
        if len(spl) == 1:
            return spl[0], " "
        elif len(spl) == 2:
            return spl[0], spl[1]
        else:
            return spl[0], spl[1]

    def _get_patch_number(self, fields):
        """
        Function returns patch number
        :param line:
        :return: patch_num
        """
        patch_num = fields[0].replace('Patch', '')[:-1]
        return patch_num

    def _get_content_spec(self):
        """
        Function reads a content rebase.spec file
        """
        lines = get_content_file(self.spec_file, "r", method=True)
        lines = [x for x in lines if not x.startswith('#')]
        return lines

    def _get_patches_flags(self):
        """
        For all patches: get flags passed to %patch macro and index of application
        """
        patch_flags = {}
        patches = [x for x in self.spec_content if x.startswith(PATCH_PREFIX)]
        for index, line in enumerate(patches):
            num, option = self.get_patch_option(line)
            num = num.replace(PATCH_PREFIX, '')
            patch_flags[int(num)] = (option, index)
        # {num: (flags, index of application)}
        return patch_flags

    def get_information(self):
        """
        Function creates a dictionary and returns them
        with all information from SPEC file
        :return:
        """
        kwargs = {}
        kwargs[settings.FULL_PATCHES] = self._get_patches()
        kwargs['sources'] = self._get_all_sources()
        kwargs['name'] = self._get_package_name()
        kwargs['version'] = self._get_spec_version()
        kwargs['tarball'] = self.get_tarball()
        return kwargs

    def _get_spec_version(self):
        """
        Function return an old and a new versions
        :return:
        """
        version = self.hdr[rpm.RPMTAG_VERSION]
        if not version:
            return None
        return version

    def _get_package_name(self):
        """
        Function returns a package name
        :return:
        """
        return self.hdr[rpm.RPMTAG_NAME]

    def get_requires(self):
        """
        Function returns a package reuirements
        :return:
        """
        return self.hdr[rpm.RPMTAG_REQUIRES]

    def is_patch_git_generated(self, full_patch_name):
        """
        Return:
          True if patch is generated by git ('git diff' or 'git format-patch')
          False means patch is generated by gendiff or somehow else.
        """
        with open(full_patch_name) as inputfile:
            for line in inputfile:
                if line.startswith("diff "):
                    if line.startswith("diff --git"):
                        return True
                    else:
                        return False
        return False

    def _get_patches(self):
        """
        Function returns a list of patches from a spec file
        """
        patches = {}
        patch_flags = self._get_patches_flags()
        cwd = os.getcwd()
        for source in self.patches:
            filename, num, patch_type = source
            full_patch_name = os.path.join(cwd, filename)
            if not os.path.exists(full_patch_name):
                logger.error('Patch {0} does not exist'.format(filename))
                continue
            if num in patch_flags:
                patches[num] = [full_patch_name, patch_flags[num][0],
                                patch_flags[num][1], self.is_patch_git_generated(full_patch_name)]
        # list of [name, flags, index, git_generated]
        return patches

    def _download_source(self, source_name, download_name):
        """
        Function downloads a source name defined in SPEC file
        """
        if not self.download:
            return
        if not os.path.exists(download_name):
            ret_code = DownloadHelper.download_source(source_name, download_name)

    def _get_all_sources(self):
        """
        Function returns all sources mentioned in specfile
        """
        cwd = os.getcwd()
        sources = []
        remote_files = ['http:', 'https:', 'ftp:']
        for index, src in enumerate(self.source_files):
            new_name = get_source_name(src[0])
            if int(src[1]) == 0:
                sources.append(os.path.join(cwd, new_name))
            else:
                remote = [x for x in remote_files if src[0].startswith(x)]
                if remote:
                    self._download_source(src[0], new_name)
                sources.append(os.path.join(cwd, new_name))
        return sources

    def get_tarball(self):
        """
        Function returns a old sources from specfile
        """
        full_source_name = self._get_full_source_name()
        source_name = get_source_name(full_source_name)
        self._download_source(full_source_name, source_name)
        return source_name

    def _get_full_source_name(self):
        """
        Function returns a source name provided by Source [0]
        List has format [(<name>, <type, 1), (other source)]
        <type> has values:
        - 0 means Source 0
        - 1 means Source > 0
        - 2 means Patches
        """
        source = [src[0] for src in self.source_files if src[1] == 0]
        # We need just a name
        return source[0]

    def _remove_empty_patches(self, lines, patch_num):
        """
        Remove ampty patches from SPEC file
        """
        for num in patch_num:
            for index, line in enumerate(lines):
                if not line.startswith('%patch{0}'.format(num)):
                    continue
                lines[index] = '#' + line

    def _update_spec_version(self, version):
        """
        Function updates a version in SPEC file
        based on self.new_sources variable
        """
        for index, line in enumerate(self.spec_content):
            if not line.startswith('Version'):
                continue
            logger.debug("SpecFile: Updating version in SPEC from '{0}' with '{1}'".format(self._get_spec_version(),
                                                                                           version))
            self.spec_content[index] = line.replace(self._get_spec_version(), version)
        write_to_file(self.spec_file, "w", self.spec_content)
        self._update_data()

    def set_spec_version(self):
        """
        Function updates a version in spec file based on input argument
        """

        archive_ext = None
        for ext in Archive.get_supported_archives():
            if self.new_sources.endswith(ext):
                archive_ext = ext
                break

        if not archive_ext:
            # CLI argument is probably just a version without name and extension
            self._update_spec_version(self.new_sources)
            # We need to reload the spec file
            old_source_name = self._get_full_source_name()
            self.new_sources = get_source_name(old_source_name)
            return self.new_sources
        tarball_name = self.new_sources.replace(archive_ext, '')
        regex = re.compile(r'^\w+-?_?(.*)')
        match = re.search(regex, tarball_name)
        if match:
            new_version = match.group(1)
            logger.debug("SpecFile: Version extracted from archive '{0}'".format(new_version))
            self._update_spec_version(new_version)
        return None

    def write_updated_patches(self, **kwargs):
        """
        Function writes a patches to -rebase.spec file
        """
        new_files = kwargs.get('new', None)
        if not new_files:
            return None
        patches = new_files.get('patches', None)
        if not patches:
            return None

        update_patches = {}
        update_patches['deleted'] = []
        update_patches['modified'] = []

        removed_patches = []
        for index, line in enumerate(self.spec_content):
            if not line.startswith('Patch'):
                continue
            fields = line.strip().split()
            patch_num = self._get_patch_number(fields)
            if int(patch_num) not in patches:
                continue
            patch_name = patches[int(patch_num)][0]
            comment = ""
            if settings.REBASE_HELPER_RESULTS_DIR in patch_name:
                if check_empty_patch(patch_name):
                    comment = '#'
                    removed_patches.append(patch_num)
                    del patches[int(patch_num)]
                    update_patches['deleted'].append(patch_name)
                else:
                    update_patches['modified'].append(patch_name)
            self.spec_content[index] = comment + ' '.join(fields[:-1]) + ' ' + os.path.basename(patch_name) + '\n'
        self._remove_empty_patches(self.spec_content, removed_patches)

        write_to_file(self.spec_file, "w", self.spec_content)
        self._update_data()
        return update_patches
