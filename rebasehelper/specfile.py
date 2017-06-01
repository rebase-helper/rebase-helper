# -*- coding: utf-8 -*-
#
# This tool helps you to rebase package to the latest version
# Copyright (C) 2013-2014 Red Hat, Inc.
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
#
# Authors: Petr Hracek <phracek@redhat.com>
#          Tomas Hozza <thozza@redhat.com>

from __future__ import print_function
import os
import re
import shutil
import six
import rpm
import argparse
import shlex
import pkg_resources
from datetime import date
from operator import itemgetter
from six.moves import urllib

from rebasehelper.utils import DownloadHelper, DownloadError, MacroHelper
from rebasehelper.utils import LookasideCacheHelper, LookasideCacheError, defenc
from rebasehelper.logger import logger
from rebasehelper import settings
from rebasehelper.archive import Archive
from rebasehelper.exceptions import RebaseHelperError

PATCH_PREFIX = '%patch'


def get_rebase_name(dir_name, name):
    """
    Function returns a name in results directory

    :param dir_name:
    :param name:
    :return: full path to results dir with name
    """
    file_name = os.path.basename(name)
    return os.path.join(dir_name, file_name)


class PatchList(list):
    def _get_index_list(self, item):
        for x in self:
            if x.get_index() == item.get_index():
                return x

    def __getitem__(self, item):
        return super(PatchList, self).__getitem__(self._get_index_list(item))


class PatchObject(object):

    """Class represents set of information about patches"""

    path = ''
    index = ''
    option = ''
    git_generated = ''

    def __init__(self, path, index, option):
        self.path = path
        self.index = index
        self.option = option

    def get_path(self):
        return self.path

    def get_index(self):
        return self.index

    def set_path(self, new_path):
        self.path = new_path

    def get_patch_name(self):
        return os.path.basename(self.path)

    def get_option(self):
        return self.option


class SpecFile(object):

    """Class representing a SPEC file"""

    path = ''
    download = False
    spec_content = []
    spc = None
    hdr = None
    extra_version = None
    sources = None
    patches = None
    rpm_sections = {}
    prep_section = []
    removed_patches = []

    defined_sections = ['%package',
                        '%description',
                        '%prep',
                        '%build',
                        '%install',
                        '%check',
                        '%files',
                        '%changelog']

    def __init__(self, path, sources_location='', download=True):
        self.path = path
        self.download = download
        self.sources_location = sources_location
        #  Read the content of the whole SPEC file
        rpm.addMacro("_sourcedir", self.sources_location)
        self._read_spec_content()
        # Load rpm information
        self.set_extra_version_separator('')
        self._update_data()

    def download_remote_sources(self):
        """
        Method that iterates over all sources and downloads ones, which contain URL instead of just a file.

        :return: None
        """
        try:
            # try to download old sources from Fedora lookaside cache
            LookasideCacheHelper.download('fedpkg', os.path.dirname(self.path), self.get_package_name())
        except LookasideCacheError as e:
            logger.debug("Downloading sources from lookaside cache failed. "
                         "Reason: '{}'.".format(str(e)))

        # filter out only sources with URL
        remote_files = [source for source in self.sources if bool(urllib.parse.urlparse(source).scheme)]
        # download any sources that are not yet downloaded
        for remote_file in remote_files:
            local_file = os.path.join(self.sources_location, os.path.basename(remote_file))
            if not os.path.isfile(local_file):
                logger.debug("File '%s' doesn't exist locally, downloading it.", local_file)
                try:
                    DownloadHelper.download_file(remote_file, local_file)
                except DownloadError as e:
                    raise RebaseHelperError("Failed to download file from URL {}. "
                                            "Reason: '{}'. ".format(remote_file, str(e)))

    def _update_data(self):
        """
        Function updates data from given SPEC file

        :return: 
        """
        # Load rpm information
        try:
            self.spc = rpm.spec(self.path)
        except ValueError:
            raise RebaseHelperError("Problem with parsing SPEC file '%s'" % self.path)
        self.sources = self._get_spec_sources_list(self.spc)
        self.prep_section = self.spc.prep
        # HEADER of SPEC file
        self.hdr = self.spc.sourceHeader
        self.rpm_sections = self._split_sections()
        # determine the extra_version
        logger.debug("Updating the extra version")
        _, self.extra_version, separator = SpecFile.extract_version_from_archive_name(
            self.get_archive(),
            self._get_raw_source_string(0))
        self.set_extra_version_separator(separator)

        self.patches = self._get_initial_patches_list()
        self.macros = MacroHelper.dump()

    ###########################
    # SOURCES RELATED METHODS #
    ###########################

    @staticmethod
    def _get_spec_sources_list(spec_object):
        """
        Method uses RPM API to get list of Sources from the SPEC file and returns the list of sources. If the Source
        contains URL, the URL will be included in the list. This means no modifications of Sources are done at this
        point.

        :param spec_object: instance of rpm.spec object
        :type spec_object: rpm.spec
        :return: list of Sources in SPEC file in the exact order as they are listed in SPEC file.
        :rtype: list
        """
        # the sources list returned by RPM API contains list of items (path, index, source_type).
        # source type "1" is a regular source
        regular_sources = [source[:2] for source in spec_object.sources if source[2] == 1]
        regular_sources = [source[0] for source in sorted(regular_sources, key=itemgetter(1))]
        return regular_sources

    def get_sources(self):
        """
        Method returns dictionary with local sources list.

        :return: list of Sources with absolute path
        :rtype: list of str
        """
        return [os.path.join(self.sources_location, os.path.basename(source)) for source in self.sources]

    def get_archive(self):
        """
        Method returns the basename of first Source in SPEC file a.k.a. Source0

        :return: basename of first Source in SPEC file
        :rtype: str
        """
        return os.path.basename(self.get_sources()[0])

    def _get_raw_source_string(self, source_num):
        """
        Method returns raw string, possibly with RPM macros, of a Source with passed number.

        :param source_num: number of the source of which to get the raw string
        :return: string of the source or None if there is no such source
        """
        source_re_str = '^Source0?:[ \t]*(.*?)$' if source_num == 0 else '^Source{0}:[ \t]*(.*?)$'.format(source_num)
        source_re = re.compile(source_re_str)

        for line in self.spec_content:
            match = source_re.search(line)
            if match:
                return match.group(1)

    ###########################
    # PATCHES RELATED METHODS #
    ###########################

    def _get_initial_patches_list(self):
        """Method returns a list of patches from a spec file"""
        patches_applied = []
        patches_not_used = []
        patches_list = [p for p in self.spc.sources if p[2] == 2]
        patch_flags = self._get_patches_flags()

        for filename, num, patch_type in patches_list:
            patch_path = os.path.join(self.sources_location, filename)
            if not os.path.exists(patch_path):
                logger.error('Patch %s does not exist', filename)
                continue
            patch_num = num
            if patch_flags:
                if num in patch_flags:
                    patch_num, patch_option = patch_flags[num]
                    patches_applied.append(PatchObject(patch_path, patch_num, patch_option))
                else:
                    patches_not_used.append(PatchObject(patch_path, patch_num, None))
            else:
                patches_applied.append(PatchObject(patch_path, patch_num, None))
        patches_applied = sorted(patches_applied, key=lambda x: x.get_index())
        return {"applied": patches_applied, "not_applied": patches_not_used}

    def get_patch_option(self, line):
        """
        Function returns a patch options

        :param line:
        :return: patch options like -p1
        """
        spl = line.strip().split()
        if len(spl) == 1:
            return spl[0], ''
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

    def _get_patches_flags(self):
        """For all patches: get flags passed to %patch macro and index of application"""
        patch_flags = {}
        patches = [x for x in self.spec_content if x.startswith(PATCH_PREFIX)]
        if not patches:
            return None
        for index, line in enumerate(patches):
            num, option = self.get_patch_option(line)
            num = num.replace(PATCH_PREFIX, '')
            try:
                patch_flags[int(num)] = (index, option)
            except ValueError:
                patch_flags[0] = (index, option)
        # {num: index of application}
        return patch_flags

    def get_patches(self):
        """
        Method returns list of all applied and not applied patches

        :return: list of PatchObject
        """
        return self.get_applied_patches() + self.get_not_used_patches()

    def get_applied_patches(self):
        """
        Method returns list of all applied patches.

        :return: list of PatchObject
        """
        return self.patches['applied']

    def get_not_used_patches(self):
        """
        Method returns list of all unpplied patches.

        :return: list of PatchObject
        """
        return self.patches['not_applied']

    def _comment_out_patches(self, patch_num):
        """
        Comment out patches from SPEC file

        :var patch_num: list with patch numbers to comment out
        """
        for index, line in enumerate(self.spec_content):
            #  if patch is applied on the line, try to check if it should be commented out
            if line.startswith('%patch'):
                #  check patch numbers
                for num in patch_num:
                    #  if the line should be commented out
                    if line.startswith('%patch{0}'.format(num)):
                        self.spec_content[index] = '#%' + line
                        #  remove the patch number from list
                        patch_num.remove(num)
                        break

    def update_paths_to_patches(self):
        # Fix paths in rebase_spec_file to patches to current directory
        for index, line in enumerate(self.spec_content):
            if line.startswith('Patch'):
                mod_line = re.sub(settings.REBASE_HELPER_REBASED_SOURCES_DIR + '/', '', line)
                self.spec_content[index] = mod_line
        self.save()

    def _correct_rebased_patches(self, patch_num):
        """
        Comment out patches from SPEC file

        :var patch_num: list with patch numbers to update
        """
        for index, line in enumerate(self.spec_content):
            #  if patch is applied on the line, try to check if it should be commented out
            if line.startswith('%patch'):
                #  check patch numbers
                for num in patch_num:
                    #  if the line should be commented out
                    if line.startswith('%patch{0}'.format(num)):
                        patch_fields = line.strip().split()
                        patch_fields = [x for x in patch_fields if not x.startswith('-p')]
                        self.spec_content[index] = '{begin}\n#{line}{new_line}\n{end}\n'.format(
                            begin=settings.BEGIN_COMMENT,
                            line=line,
                            new_line=' '.join(patch_fields) + ' -p1',
                            end=settings.END_COMMENT,
                        )
                        #  remove the patch number from list
                        patch_num.remove(num)
                        break

    def write_updated_patches(self, patches):
        """Function writes the patches to -rebase.spec file"""
        #  TODO: this method should not take whole kwargs as argument, take only what it needs.
        if not patches:
            return None
        # If some patches are not applied then commented out
        removed_patches = []
        modified_patches = []

        for index, line in enumerate(self.spec_content):
            if line.startswith('Patch'):
                fields = line.strip().split()
                patch_name = fields[1]
                patch_num = self._get_patch_number(fields)
                # We check if patch is mentioned in SPEC file but not used.
                # We are comment out the patch
                check_not_applied = [x for x in self.get_not_used_patches() if
                                     int(x.get_index()) == int(patch_num)]
                if 'deleted' in patches:
                    patch_removed = [x for x in patches['deleted'] if patch_name in x]
                else:
                    patch_removed = None
                if check_not_applied or patch_removed:
                    self.spec_content[index] = '#{0} {1}\n'.format(' '.join(fields[:-1]),
                                                                   os.path.basename(patch_name))
                    if patch_removed:
                        self.removed_patches.append(patch_name)
                        removed_patches.append(patch_num)
                if 'modified' in patches:
                    patch = [x for x in patches['modified'] if patch_name in x]
                else:
                    patch = None
                if patch:
                    fields[1] = os.path.join(settings.REBASE_HELPER_REBASED_SOURCES_DIR, patch_name)
                    self.spec_content[index] = ' '.join(fields) + '\n'
                    modified_patches.append(patch_num)

        self._comment_out_patches(removed_patches)
        self._correct_rebased_patches(modified_patches)
        #  save changes
        self.save()

    ###################################
    # PACKAGE VERSION RELATED METHODS #
    ###################################

    def get_epoch_number(self):
        """
        Method for getting epoch of the package

        :return:
        """
        return self.hdr[rpm.RPMTAG_EPOCHNUM]

    def get_release(self):
        """
        Method for getting full release string of the package

        :return:
        """
        return self.hdr[rpm.RPMTAG_RELEASE].decode(defenc) if six.PY3 else self.hdr[rpm.RPMTAG_RELEASE]

    def get_release_number(self):
        """
        Method for getting the release of the package

        :return:
        """
        for line in self.spec_content:
            # https://regexper.com/#%5ERelease%3A%5Cs*(%5B0-9%5D*%5C.%3F%5B0-9%5D%2B)(.%2B)%3F%25%7B%5C%3Fdist%7D%5Cs*
            match = re.search(r'^Release:\s*([0-9]*\.?[0-9]+)(.+)?%{\?dist}\s*', line)
            if match:
                return match.group(1)

    def get_version(self):
        """
        Method returns the version

        :return:
        """
        return self.hdr[rpm.RPMTAG_VERSION].decode(defenc) if six.PY3 else self.hdr[rpm.RPMTAG_VERSION]

    def get_extra_version(self):
        """
        Returns an extra version of the package - like b1, rc2, ...

        :return: String
        """
        return self.extra_version

    def get_extra_version_separator(self):
        """
        Returns the separator between version and extra version as used by upstream. If there is not separator or
        extra version, it returns an empty string.

        :return: String with the separator between version as extra version as used by upstream.
        :rtype: str
        """
        return self.extra_version_separator

    def get_full_version(self):
        """
        Returns the full version string, which is a combination of version, separator and extra version.

        :return: String with full version, including the extra version part.
        :rtype: str
        """
        return '{0}{1}{2}'.format(self.get_version(), self.get_extra_version_separator(), self.get_extra_version())

    def set_release_number(self, release):
        """
        Method to set release number

        :param release:
        :return:
        """
        for index, line in enumerate(self.spec_content):
            if line.startswith('Release:'):
                new_release_line = re.sub(r'(Release:\s*)[0-9.]+(.*%{\?dist}\s*)', r'\g<1>{0}\2'.format(release),
                                          line)
                logger.debug("Changing release line to '%s'", new_release_line.strip())
                self.spec_content[index] = new_release_line
                self.save()
                break

    def redefine_release_with_macro(self, macro):
        """
        Method redefines the Release: line to include passed macro and comments out the old line

        :param macro:
        :return:
        """
        for index, line in enumerate(self.spec_content):
            if line.startswith('Release:'):
                new_release_line = re.sub(r'(Release:\s*[0-9.]*[0-9]+).*(%{\?dist}\s*)', r'\g<1>.{0}\2'.format(macro),
                                          line)
                logger.debug("Commenting out original Release line '%s'", line.strip())
                self.spec_content[index] = '#{0}'.format(line)
                logger.debug("Inserting new Release line '%s'", new_release_line.strip())
                self.spec_content.insert(index + 1, new_release_line)
                self.save()
                break

    def revert_redefine_release_with_macro(self, macro):
        """
        Method removes the redefined the Release: line with given macro and uncomments the old Release line.

        :param macro:
        :return:
        """
        search_re = re.compile(r'^Release:\s*[0-9.]*[0-9]+\.{0}%{{\?dist}}\s*'.format(macro))

        for index, line in enumerate(self.spec_content):
            match = search_re.search(line)
            if match:
                # We will uncomment old line, so sanity check first
                if not self.spec_content[index - 1].startswith('#Release:'):
                    raise RebaseHelperError("Redefined Release line in SPEC is not 'commented out' "
                                            "old line: '{0}'".format(self.spec_content[index - 1].strip()))
                logger.debug("Uncommenting original Release line "
                             "'%s'", self.spec_content[index - 1].strip())
                self.spec_content[index - 1] = self.spec_content[index - 1].lstrip('#')
                logger.debug("Removing redefined Release line '%s'", line.strip())
                self.spec_content.pop(index)
                self.save()
                break

    def set_extra_version(self, extra_version):
        """
        Method to update the extra version in the SPEC file. Redefined Source0 if needed and also changes
        Release accordingly.

        :param extra_version: the extra version string, if any (e.g. 'b1', 'rc2', ...)
        :return: None
        """
        extra_version_def = '%global REBASE_EXTRA_VER'
        extra_version_macro = '%{?REBASE_EXTRA_VER}'
        extra_version_re = re.compile('^{0}.*$'.format(extra_version_def))
        extra_version_line_index = None
        rebase_extra_version_def = '%global REBASE_VER %{version}' + \
                                   self.extra_version_separator + \
                                   '%{REBASE_EXTRA_VER}\n'
        new_extra_version_line = '%global REBASE_EXTRA_VER {0}\n'.format(extra_version)

        logger.debug("Updating extra version in SPEC to '%s'", extra_version)

        #  try to find existing extra version definition
        for index, line in enumerate(self.spec_content):
            match = extra_version_re.search(line)
            if match:
                extra_version_line_index = index
                break

        if extra_version:
            #  just update the existing extra version
            if extra_version_line_index is not None:
                self.spec_content[extra_version_line_index] = new_extra_version_line
            # we need to create the extra version definition
            else:
                # insert the REBASE_VER and REBASE_EXTRA_VER definitions
                logger.debug("Adding new line to spec: %s", rebase_extra_version_def.strip())
                self.spec_content.insert(0, rebase_extra_version_def)
                logger.debug("Adding new line to spec: %s", new_extra_version_line.strip())
                self.spec_content.insert(0, new_extra_version_line)

                # change Release to 0.1 and append the extra version macro
                self.set_release_number('0.1')
                self.redefine_release_with_macro(extra_version_macro)

                # change the Source0 definition
                source0_re = re.compile(r'^Source0?:.+')
                for index, line in enumerate(self.spec_content):
                    if source0_re.search(line):
                        # comment out the original Source0 line
                        logger.debug("Commenting out original Source0 line '%s'", line.strip())
                        self.spec_content[index] = '#{0}'.format(line)
                        # construct new Source0 line. The idea is that we use the expanded archive name to create
                        # new Source0. We used raw original Source0 before, but it didn't work reliably.
                        source0_raw = line
                        basename_expanded = self.get_archive()
                        # construct the original version in archive name so that we can replace it
                        original_version = '{0}{2}{1}'.format(*self.extract_version_from_archive_name(
                            basename_expanded,
                            source0_raw)
                                                              )
                        # replace the version with macro
                        new_basename_with_macro = basename_expanded.replace(original_version, '%{REBASE_VER}')
                        # replace the name with macro to be cool :)
                        new_basename_with_macro = new_basename_with_macro.replace(self.get_package_name(),
                                                                                  '%{name}')
                        # replace the archive name in old Source0 with new one
                        new_source0_line = source0_raw.replace(os.path.basename(source0_raw),
                                                               new_basename_with_macro)
                        logger.debug("Inserting new Source0 line '%s'", new_source0_line)
                        self.spec_content.insert(index + 1, new_source0_line + '\n')
                        break
        else:
            # set the Release to 1 and revert the redefined Release with macro if needed
            self.set_release_number('1')
            self.revert_redefine_release_with_macro(extra_version_macro)
            # TODO: handle empty extra_version as removal of the definitions!

        # save changes
        self.save()

    def set_extra_version_separator(self, separator):
        """
        Set the string that separates the version and extra version

        :param separator:
        :return:
        """
        self.extra_version_separator = separator

    def set_version_using_archive(self, archive_path):
        """
        Method to update the version in the SPEC file using a archive path. The version
        is extracted from the archive name.

        :param archive_path:
        :return:
        """
        version, extra_version, separator = SpecFile.extract_version_from_archive_name(archive_path,
                                                                                       self._get_raw_source_string(
                                                                                           0))

        if not version:
            # can't continue without version
            raise RebaseHelperError('Failed to extract version from archive name')

        self.set_version(version)
        self.set_extra_version_separator(separator)
        self.set_extra_version(extra_version)

    def set_version(self, version):
        """
        Method to update the version in the SPEC file

        :param version: string with new version
        :return: None
        """
        version_re = re.compile(r'^Version:\s*(.+)')
        for index, line in enumerate(self.spec_content):
            match = version_re.search(line)
            if match:
                logger.debug("Updating version in SPEC from '%s' with '%s'", self.get_version(), version)

                # search for used macros in spec file scope
                for m in MacroHelper.filter(self.macros, level=-1, used=True):
                    if m['name'] in match.group(1):
                        # redefine the macro, don't touch Version tag
                        self._set_macro(m['name'], version)
                        return

                self.spec_content[index] = line.replace(match.group(1), version)
                break
        #  save changes to the disc
        self.save()

    @staticmethod
    def split_version_string(version_string=''):
        """
        Method splits version string into version and possibly extra string as 'rc1' or 'b1', ...

        :param version_string: version string such as '1.1.1' or '1.2.3b1', ...
        :return: tuple of strings with (extracted version, extra version, separator) or (None, None, None)
                 if extraction failed
        """
        version_split_regex_str = r'([0-9]+[.0-9]*)([_-]?)(\w*)'
        version_split_regex = re.compile(version_split_regex_str)
        logger.debug("Splitting string '%s'", version_string)
        match = version_split_regex.search(version_string)
        if match:
            version = match.group(1)
            separator = match.group(2)
            extra_version = match.group(3)
            logger.debug("Divided version '%s' and extra string '%s' separated by '%s'",
                         version,
                         extra_version,
                         separator)
            return version, extra_version, separator
        else:
            return None, None, None

    @staticmethod
    def extract_version_from_archive_name(archive_path, source_string=''):
        """
        Method extracts the version from archive name based on the source string from SPEC file.
        It extracts also an extra version such as 'b1', 'rc1', ...

        :param archive_path: archive name or path with archive name from which to extract the version
        :param source_string: Source string from SPEC file used to construct version extraction regex
        :return: tuple of strings with (extracted version, extra version) or (None, None) if extraction failed
        """
        # https://regexper.com/#(%5B.0-9%5D%2B%5B-_%5D%3F%5Cw*)
        version_regex_str = r'([.0-9]+[-_]?\w*)'
        fallback_regex_str = r'^\w+[-_]?v?{0}({1})'.format(version_regex_str,
                                                          '|'.join(Archive.get_supported_archives()))
        # match = re.search(regex, tarball_name)
        name = os.path.basename(archive_path)
        url_base = os.path.basename(source_string).strip()

        logger.debug("Extracting version from '%s' using '%s'", name, url_base)
        # expect that the version macro can be followed by another macros
        regex_str = re.sub(r'%{version}(%{.+})?', version_regex_str, url_base, flags=re.IGNORECASE)

        # if no substitution was made, use the fallback regex
        if regex_str == url_base:
            logger.debug('Using fallback regex to extract version from archive name.')
            regex_str = fallback_regex_str
        else:
            regex_str = rpm.expandMacro(regex_str)

        logger.debug("Extracting version using regex '%s'", regex_str)
        regex = re.compile(regex_str)
        match = regex.search(name)
        if match:
            version = match.group(1)
            logger.debug("Extracted version '%s'", version)
            return SpecFile.split_version_string(version)
        else:
            logger.debug('Failed to extract version from archive name!')
            #  TODO: look at this if it could be rewritten in a better way!
            #  try fallback regex if not used this time
            if regex_str != fallback_regex_str:
                logger.debug("Trying to extracting version using fallback regex '%s'", fallback_regex_str)
                regex = re.compile(fallback_regex_str)
                match = regex.search(name)
                if match:
                    version = match.group(1)
                    logger.debug("Extracted version '%s'", version)
                    return SpecFile.split_version_string(version)
                else:
                    logger.debug('Failed to extract version from archive name using fallback regex!')
            return SpecFile.split_version_string('')

    #################################
    # SPEC SECTIONS RELATED METHODS #
    #################################

    def _create_spec_from_sections(self):
        """
        Spec file has defined order
        First we write a header
        """
        new_spec_file = []

        try:
            for key, value in sorted(six.iteritems(self.rpm_sections)):
                sec_name, section = value
                if '%header' in sec_name:
                    new_spec_file.extend(section)
                else:
                    new_spec_file.append(sec_name + '\n')
                    new_spec_file.extend(section)
        except KeyError:
            raise RebaseHelperError("Unable to find a specific section in SPEC file")

        return new_spec_file

    def _split_sections(self):
        """
        Function split spec file to well known SPEC sections

        :return: position and content of section in format like
            [0, (%files, [list of all rows within %files section],
             1, (%files debug, [list of all rows within %files debug section]]
        """
        # rpm-python does not provide any directive for getting %files section
        # Therefore we should do that workaround
        section_headers_re = [re.compile('^{0}.*'.format(x)) for x in self.defined_sections]

        section_starts = []
        # First of all we need to find beginning of all sections
        for line_num, line in enumerate(self.spec_content):
            # it might be a section
            if line.startswith('%'):
                # check all possible section headers
                for section_header in section_headers_re:
                    if section_header.search(line):
                        section_starts.append(line_num)

        # determine the SPEC header
        # it is everything until the beginning the first section
        header_end = section_starts[0] if section_starts else len(self.spec_content)
        sections = {0: ('%header', self.spec_content[:header_end])}

        # now determine all previously found sections
        for i in range(len(section_starts)):
            # We cut a relevant section to field
            if i + 1 < len(section_starts):
                curr_section = self.spec_content[section_starts[i]:section_starts[i+1]]
            else:
                curr_section = self.spec_content[section_starts[i]:]
            sections[i+1] = (curr_section[0].strip(), curr_section[1:])

        return sections

    def get_spec_section(self, section_name):
        """
        Returns the section of selected name

        :param section_name: section name to get
        :return: list of lines contained in the selected section
        """
        for sec_name, section in six.itervalues(self.rpm_sections):
            if sec_name == section_name:
                return section

    def set_spec_section(self, section_name, new_section):
        """
        Returns the section of selected name

        :param section_name: section name to get
        :return: list of lines contained in the selected section
        """
        for key, val in six.iteritems(self.rpm_sections):
            if section_name in val[0]:
                if isinstance(new_section, str):
                    self.rpm_sections[key] = (section_name, new_section.split('\n'))
                else:
                    self.rpm_sections[key] = (section_name, new_section)

    def get_prep_section(self, complete=False):
        """Function returns whole prep section"""
        prep_section = []
        start_prep_section = complete
        for line in self.prep_section.split('\n'):
            if start_prep_section:
                prep_section.append(line)
                continue
            if line.startswith('/usr/bin/chmod -Rf a+rX') and not complete:
                start_prep_section = True
                continue

        return prep_section

    #############################################
    # SPEC CONTENT MANIPULATION RELATED METHODS #
    #############################################

    def _read_spec_content(self):
        """Method reads the content SPEC file and updates internal variables."""
        try:
            with open(self.path) as f:
                lines = f.readlines()
        except IOError:
            raise RebaseHelperError("Unable to open and read SPEC file '%s'", self.path)
        #  Complete SPEC file content
        self.spec_content = lines

    def _write_spec_file_to_disc(self):
        """Write the current SPEC file to the disc"""
        logger.debug("Writing SPEC file '%s' to the disc", self.path)
        try:
            with open(self.path, "w") as f:
                f.writelines(self.spec_content)
        except IOError:
            raise RebaseHelperError("Unable to write updated data to SPEC file '%s'", self.path)

    def copy(self, new_path=None):
        """
        Create a copy of the current object and copy the SPEC file the new object
        represents to a new location.

        :param new_path: new path to which to copy the SPEC file
        :return: copy of the current object
        """
        if new_path:
            shutil.copy(self.path, new_path)
        new_object = SpecFile(new_path, self.sources_location, self.download)
        return new_object

    def save(self):
        """Save changes made to the spec_content to the disc and update internal variables"""
        # TODO: Create a decorator from this method
        #  Write changes to the disc
        self._write_spec_file_to_disc()
        #  Update internal variables
        self._update_data()

    ####################
    # UNSORTED METHODS #
    ####################

    def get_path(self):
        """
        Return only spec file path

        :return: 
        """
        return self.path

    def is_test_suite_enabled(self):
        """
        Returns whether test suite is enabled during the build time

        :return: True if enabled or False if not
        """
        check_section = self.get_spec_section('%check')
        if not check_section:
            return False
        # Remove commented lines
        check_section = [x.strip() for x in check_section if not x.strip().startswith('#')]
        # If there is at least one line with some command in %check we assume test suite is run
        if check_section:
            return True
        else:
            return False

    def get_package_name(self):
        """
        Function returns a package name

        :return: 
        """
        return self.hdr[rpm.RPMTAG_NAME].decode(defenc) if six.PY3 else self.hdr[rpm.RPMTAG_NAME]

    def get_requires(self):
        """
        Function returns a package requirements

        :return: 
        """
        return [r.decode(defenc) if six.PY3 else r for r in self.hdr[rpm.RPMTAG_REQUIRES]]

    @staticmethod
    def get_paths_with_rpm_macros(files):
        """
        Method modifies paths in passed list to use RPM macros

        :param files: list of absolute paths
        :return: modified list of paths with RPM macros
        """
        # TODO: move this to RpmHelper?
        macro_mapping = {'/usr/lib64': '%{_libdir}',
                         '/usr/libexec': '%{_libexecdir}',
                         '/usr/lib/systemd/system': '%{_unitdir}',
                         '/usr/lib': '%{_libdir}',
                         '/usr/bin': '%{_bindir}',
                         '/usr/sbin': '%{_sbindir}',
                         '/usr/include': '%{_includedir}',
                         '/usr/share/man': '%{_mandir}',
                         '/usr/share/info': '%{_infodir}',
                         '/usr/share/doc': '%{_docdir}',
                         '/usr/share': '%{_datarootdir}',
                         '/var/lib': '%{_sharedstatedir}',
                         '/var/tmp': '%{_tmppath}',
                         '/var': '%{_localstatedir}',
                         }
        for index, filename in enumerate(files):
            for abs_path, macro in sorted(six.iteritems(macro_mapping), reverse=True):
                if filename.startswith(abs_path):
                    files[index] = filename.replace(abs_path, macro)
                    break
        return files

    @staticmethod
    def construct_string_with_comment(lines):
        """
        Wraps the line in a rebase-helper specific comments

        :param lines: line (or list of lines) to be wrapped
        :return: list with lines
        """
        sec = '\n'
        comm_lines = [settings.BEGIN_COMMENT + sec]
        for l in lines if not isinstance(lines, six.string_types) else [lines]:
            comm_lines.append(l + sec)
        comm_lines.append(settings.END_COMMENT + sec)
        return comm_lines

    def _correct_missing_files(self, missing):
        sep = '\n'
        for key, value in six.iteritems(self.rpm_sections):
            sec_name, sec_content = value
            match = re.search(r'^%files\s*$', sec_name)
            if match:
                if settings.BEGIN_COMMENT in sec_content:
                    # We need only files which are not included yet.
                    upd_files = [f for f in missing if f not in sec_content]
                    regex = re.compile(r'(' + settings.BEGIN_COMMENT + r'\s*)')
                    sec_content = regex.sub('\\1' + '\n'.join(upd_files) + sep,
                                            sec_content)
                else:
                    # This code adds begin_comment, files and end_comment
                    # with separator
                    sec_content = SpecFile.construct_string_with_comment(missing) + sec_content
                self.rpm_sections[key] = (sec_name, sec_content)
                break

    def _correct_removed_files(self, sources):
        for key, value in six.iteritems(self.rpm_sections):
            sec_name, sec_content = value
            # Only sections %files are interesting
            match = re.search(r'^%files', sec_name)
            if match:
                # Check what files are in section
                # and comment only relevant
                f_exists = [f for f in sources for sec in sec_content if os.path.basename(f) in sec]
                if not f_exists:
                    continue
                for f in f_exists:
                    index = 0
                    for index, row in enumerate(sec_content):
                        if f in row:
                            break
                    sec_content[index: index+1] = SpecFile.construct_string_with_comment('#' + row)
                self.rpm_sections[key] = (sec_name, sec_content)

    def modify_spec_files_section(self, files):
        """
        Function repairs spec file according to new sources.

        :param files: 
        :return: 
        """
        # Files which are missing in SPEC file.
        try:
            if files['missing']:
                upd_files = SpecFile.get_paths_with_rpm_macros(files['missing'])
                self._correct_missing_files(upd_files)
        except KeyError:
            pass

        # Files which does not exist in SOURCES.
        # Should be removed from SPEC file.
        try:
            if files['deleted']:
                upd_files = SpecFile.get_paths_with_rpm_macros(files['deleted'])
                self._correct_removed_files(upd_files)
        except KeyError:
            pass

        self.spec_content = self._create_spec_from_sections()
        self.save()

    def _set_macro(self, macro, value):

        """
        (Re)defines given macro value in the SPEC file

        :param macro: macro name
        :param value: macro value
        """
        macro_re = re.compile(r'(%global|%define)\s+(\w+)(\(.+?\))?\s+(.+)')
        defined = False

        for index, line in enumerate(self.spec_content):
            match = macro_re.search(line)
            if match:
                if match.group(2) != macro:
                    continue

                if match.group(3):
                    line = line.replace(match.group(3), '')

                self.spec_content[index] = line.replace(match.group(4), value)
                defined = True

        if not defined:
            self.spec_content.insert(0, '%global {} {}'.format(macro, value))

        self.save()

    def get_new_log(self, git_helper):
        new_record = []
        today = date.today()
        git_name = git_helper.command_config('--get', 'user.name')
        git_email = git_helper.command_config('--get', 'user.email')
        evr = '{epoch}:{ver}-{rel}'.format(epoch=self.get_epoch_number(),
                                           ver=self.get_version(),
                                           rel=self.get_release_number())
        evr = evr[2:] if evr.startswith('0:') else evr
        new_record.append('* {day} {name} <{email}> - {evr}\n'.format(day=today.strftime('%a %b %d %Y'),
                                                                      name=git_name,
                                                                      email=git_email,
                                                                      evr=evr))
        new_record.append('- New upstream release {rel}\n'.format(rel=self.get_version()))
        new_record.append('\n')
        return new_record

    def insert_changelog(self, new_log):
        changelog = '%changelog'
        new_log.extend(self.get_spec_section(changelog))
        self.set_spec_section(changelog, new_log)

    def update_changelog(self, new_log):
        """Function updates changelog with new version"""
        self.insert_changelog(new_log)
        self.spec_content = self._create_spec_from_sections()
        self.save()

    def _get_setup_parser(self):
        """
        Construct ArgumentParser for parsing %(auto)setup macro arguments

        :return: constructed ArgumentParser
        """
        parser = argparse.ArgumentParser()
        parser.add_argument('-n', default=rpm.expandMacro('%{name}-%{version}'))
        parser.add_argument('-a', type=int, default=-1)
        parser.add_argument('-b', type=int, default=-1)
        parser.add_argument('-T', action='store_true')
        return parser

    def get_setup_dirname(self):
        """
        Get dirname from %setup or %autosetup macro arguments

        :return: dirname
        """
        parser = self._get_setup_parser()

        for index, line in enumerate(self.spec_content):
            if line.startswith('%setup') or line.startswith('%autosetup'):
                line = rpm.expandMacro(line)

                # parse macro arguments
                ns, _ = parser.parse_known_args(shlex.split(line)[1:])

                # check if this macro instance is extracting Source0
                if not ns.T or ns.a == 0 or ns.b == 0:
                    return ns.n

        return None

    def update_setup_dirname(self, dirname):
        """
        Update %setup or %autosetup dirname argument if needed

        :param dirname: new dirname to be used
        """
        parser = self._get_setup_parser()

        for index, line in enumerate(self.spec_content):
            if line.startswith('%setup') or line.startswith('%autosetup'):
                line = rpm.expandMacro(line)

                args = shlex.split(line)
                macro = args[0]

                # parse macro arguments
                ns, unknown = parser.parse_known_args(args[1:])

                # check if this macro instance is extracting Source0
                if ns.T and ns.a != 0 and ns.b != 0:
                    continue

                # check if modification is really necessary
                if dirname != ns.n:
                    new_dirname = dirname

                    # get %{name} and %{version} macros
                    macros = [m for m in MacroHelper.filter(self.macros, level=-3) if m['name'] in ('name', 'version')]
                    # add all macros from spec file scope
                    macros.extend(MacroHelper.filter(self.macros, level=-1))
                    # ensure maximal greediness
                    macros.sort(key=lambda k: len(k['value']), reverse=True)

                    # substitute tokens with macros
                    for m in macros:
                        if m['value'] and m['value'] in dirname:
                            new_dirname = new_dirname.replace(m['value'], '%{{{}}}'.format(m['name']))

                    args = [macro]
                    args.extend(['-n', new_dirname])
                    if ns.a != -1:
                        args.extend(['-a', str(ns.a)])
                    if ns.b != -1:
                        args.extend(['-b', str(ns.b)])
                    if ns.T:
                        args.append('-T')
                    args.extend(unknown)

                    self.spec_content[index] = '#{0}'.format(line)
                    self.spec_content.insert(index + 1, ' '.join(args) + '\n')
                    self.save()

    def find_archive_target_in_prep(self, archive):
        """
        Tries to find a command that is used to extract the specified archive
        and attempts to determine target path from it.
        'tar' and 'unzip' commands are supported so far.

        :param archive: Path to archive
        :return: Target path relative to builddir or None if not determined
        """
        cd_parser = argparse.ArgumentParser()
        cd_parser.add_argument('dir', default=os.environ.get('HOME', ''))
        tar_parser = argparse.ArgumentParser()
        tar_parser.add_argument('-C', default='.', dest='target')
        unzip_parser = argparse.ArgumentParser()
        unzip_parser.add_argument('-d', default='.', dest='target')
        prep = self.get_prep_section(complete=True)
        archive = os.path.basename(archive)
        builddir = rpm.expandMacro('%{_builddir}')
        basedir = builddir
        for line in prep:
            tokens = shlex.split(line, comments=True)
            if not tokens:
                continue
            cmd, args = os.path.basename(tokens[0]), tokens[1:]
            if cmd == 'cd':
                # keep track of current directory
                ns, _ = cd_parser.parse_known_args(args)
                basedir = ns.dir if os.path.isabs(ns.dir) else os.path.join(basedir, ns.dir)
            if archive in line:
                if cmd == 'tar':
                    parser = tar_parser
                elif cmd == 'unzip':
                    parser = unzip_parser
                else:
                    continue
                ns, _ = parser.parse_known_args(args)
                basedir = os.path.relpath(basedir, builddir)
                return os.path.normpath(os.path.join(basedir, ns.target))
        return None


class BaseSpecHook(object):
    """Base class for a spec hook"""

    @classmethod
    def get_name(cls):
        """Returns the name of a spec hook"""
        raise NotImplementedError()

    @classmethod
    def run(cls, spec_file, rebase_spec_file):
        """
        Runs a spec hook.

        :param spec_file: Original spec file object
        :param rebase_spec_file: Rebased spec file object
        """
        raise NotImplementedError()


class SpecHooksRunner(object):
    """
    Class representing the process of running various spec file hooks.
    """

    def __init__(self):
        """
        Constructor of SpecHooksRunner class.
        """
        self.spec_hooks = {}
        for entrypoint in pkg_resources.iter_entry_points('rebasehelper.spec_hooks'):
            try:
                spec_hook = entrypoint.load()
            except ImportError:
                # silently skip broken plugin
                continue
            try:
                self.spec_hooks[spec_hook.get_name()] = spec_hook
            except (AttributeError, NotImplementedError):
                # silently skip broken plugin
                continue

    def run_spec_hooks(self, spec_file, rebase_spec_file):
        """
        Runs all spec hooks.

        :param spec_file: Original spec file object
        :param rebase_spec_file: Rebased spec file object
        """
        for name, spec_hook in six.iteritems(self.spec_hooks):
            logger.info("Running '%s' spec hook", name)
            spec_hook.run(spec_file, rebase_spec_file)


# Global instance of SpecHooksRunner. It is enough to load it once per application run.
spec_hooks_runner = SpecHooksRunner()
