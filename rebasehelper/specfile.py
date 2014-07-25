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
import shutil
import re
from rebasehelper.utils import ProcessHelper, DownloadHelper
from rebasehelper.logger import logger
from rebasehelper import settings
from rebasehelper.utils import get_content_file,  write_to_file
from rebasehelper.utils import check_empty_patch
from rebasehelper.archive import Archive


def get_source_name(name):
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
    values = []

    def __init__(self, specfile, new_sources, download=True):
        self.spec_file = specfile
        self.download = download
        self.rebased_spec = get_rebase_name(specfile)
        shutil.copy(self.spec_file, self.rebased_spec)
        self.old_spc = None
        self.new_spc = None
        self.spc = None
        self.new_sources = new_sources

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

    def get_rebased_spec(self):
        """
        Function returns rebase.spec file
        """
        return self.rebased_spec

    def get_patch_number(self, line):
        """
        Function returns patch number
        :param line:
        :return: patch_num
        """
        fields = line.strip().split()
        patch_num = fields[0].replace('Patch', '')[:-1]
        return patch_num

    def get_content_rebase(self):
        """
        Function reads a content rebase.spec file
        """
        lines = get_content_file(self.get_rebased_spec(), "r", method=True)
        lines = [x for x in lines if not x.startswith('#')]
        return lines

    def _get_patches_flags(self):
        """
        For all patches: get flags passed to %patch macro and index of application
        """
        patch_flags = {}
        lines = self.get_content_rebase()
        lines = [x for x in lines if x.startswith(settings.PATCH_PREFIX)]
        for index, line in enumerate(lines):
            num, option = self.get_patch_option(line)
            num = num.replace(settings.PATCH_PREFIX, '')
            patch_flags[int(num)] = (option, index)
        # {num: (flags, index of application)}
        return patch_flags

    def _get_spec_information(self, version):
        kwargs = {}
        kwargs[settings.FULL_PATCHES] = self._get_patches()
        kwargs['sources'] = self._get_all_sources()
        kwargs['name'] = self._get_package_name(self.spc)
        kwargs['version'] = self._get_spec_versions(version)
        return kwargs

    def get_old_information(self):
        kwargs = {}
        self.spc = rpm.spec(self.spec_file)
        kwargs = self._get_spec_information('old')
        kwargs['tarball'] = self._get_old_tarball()
        return kwargs

    def get_new_information(self):
        kwargs = {}
        self.spc = rpm.spec(self.rebased_spec)
        kwargs = self._get_spec_information('new')
        kwargs['tarball'] = self._get_new_tarball()

        return kwargs

    def _get_version_from_spec(self, spec_file):
        hdr = spec_file.sourceHeader
        version = hdr[rpm.RPMTAG_VERSION]
        if not version:
            return None
        return version

    def _get_spec_versions(self, version):
        """
        Function return an old and a new versions
        :return:
        """
        if version == 'old':
            spec = rpm.spec(self.spec_file)
        else:
            spec = rpm.spec(self.rebased_spec)
        version = self._get_version_from_spec(spec)
        return version

    def _get_package_name(self, spec_file):
        hdr = spec_file.sourceHeader
        return hdr[rpm.RPMTAG_NAME]

    def get_requires(self):
        return self.spc.sourceHeader[rpm.RPMTAG_REQUIRES]

    def is_patch_git_generated(self, full_patch_name):
        """
        Return:
          True if patch is generated by git ('git diff' or 'git format-patch')
          False means patch is generated by gendiff or somehow else.
        """
        with open(full_patch_name) as f:
            for line in f:
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
        sources = [x for x in self.spc.sources if x[2] == 2]
        for source in sources:
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

    def _get_sources(self):
        """
        Function returns a all sources
        """
        sources = [x for x in self.spc.sources if x[2] == 0 or x[2] == 1]
        return sources

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
        sources = self._get_sources()
        remote_files = ['http:', 'https:', 'ftp:']
        for index, src in enumerate(sources):
            new_name = get_source_name(src[0])
            if int(src[1]) == 0:
                sources[index] = os.path.join(cwd, new_name)
            else:
                remote = [x for x in remote_files if src[0].startswith(x)]
                if remote:
                    self._download_source(src[0], new_name)
                sources[index] = os.path.join(cwd, new_name)
        return sources

    def _get_old_tarball(self):
        """
        Function returns a old sources from specfile
        """
        self.spc = rpm.spec(self.spec_file)
        old_source_name = self._get_full_source_name()
        source_name = get_source_name(old_source_name)
        self._download_source(old_source_name, source_name)
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
        sources = self._get_sources()
        source = [src[0] for src in sources if src[1] == 0]
        return source[0]

    def _get_new_tarball(self):
        """
        Function gets a new tarball if it does not exist.
        """
        self.spc = rpm.spec(self.rebased_spec)
        new_source_name = self._get_full_source_name()
        url_path = new_source_name.split('/')[:-1]
        url_path.append(self.new_sources)
        if not os.path.exists(self.new_sources):
            self._download_source('/'.join(url_path), self.new_sources)
        return self.new_sources

    def get_tarballs(self):
        old_sources = self._get_old_tarball()
        new_sources = self._update_new_version()
        self._get_new_tarball()
        return old_sources, new_sources

    def _remove_empty_patches(self, lines, patch_num):
        """
        Remove ampty patches from SPEC file
        """
        for num in patch_num:
            for index, line in enumerate(lines):
                if not line.startswith('%patch{0}'.format(num)):
                    continue
                lines[index] = '#' + line

    def _update_spec_version(self, lines, version):
        for index, line in enumerate(lines):
            if not line.startswith('Version'):
                continue
            lines[index] = line.replace(self._get_spec_versions('old'), version)
        write_to_file(self.get_rebased_spec(), "w", lines)

    def _update_new_version(self):
        """
        Function updates a version in spec file based on input argument
        """
        lines = get_content_file(self.get_rebased_spec(), "r", method=True)
        self.spc = rpm.spec(self.rebased_spec)

        tarball_ext = None
        for ext in Archive.get_supported_archives():
            if self.new_sources.endswith(ext):
                tarball_ext = ext
                break

        if not tarball_ext:
            # CLI argument is probably just a version without name and extension
            self._update_spec_version(lines, self.new_sources)
            # We need to reload the spec file
            self.spc = rpm.spec(self.rebased_spec)
            old_source_name = self._get_full_source_name()
            self.new_sources = get_source_name(old_source_name)
            return self.new_sources
        tarball_name = self.new_sources.replace(tarball_ext, '')
        regex = re.compile(r'^\w+-?_?(.*)')
        match = re.search(regex, tarball_name)
        if match:
            self._update_spec_version(lines, match.group(1))
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

        lines = self.get_content_rebase()
        removed_patches = []
        for index, line in enumerate(lines):
            if not line.startswith('Patch'):
                continue
            fields = line.strip().split()
            patch_num = self.get_patch_number(line)
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
            lines[index] = comment + ' '.join(fields[:-1]) + ' ' + os.path.basename(patch_name) + '\n'
        self._remove_empty_patches(lines, removed_patches)

        write_to_file(self.get_rebased_spec(), "w", lines)
        return update_patches
