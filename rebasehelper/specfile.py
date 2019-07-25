# -*- coding: utf-8 -*-
#
# This tool helps you rebase your package to the latest version
# Copyright (C) 2013-2019 Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
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
# Authors: Petr Hráček <phracek@redhat.com>
#          Tomáš Hozza <thozza@redhat.com>
#          Nikola Forró <nforro@redhat.com>
#          František Nečas <fifinecas@seznam.cz>

import argparse
import enum
import itertools
import os
import re
import shlex
import shutil
import urllib.parse

import rpm  # type: ignore

from datetime import date
from difflib import SequenceMatcher
from operator import itemgetter
from typing import List, Optional, Pattern, Tuple, Dict

from rebasehelper import constants
from rebasehelper.logger import logger
from rebasehelper.archive import Archive
from rebasehelper.exceptions import RebaseHelperError, DownloadError, ParseError, LookasideCacheError
from rebasehelper.argument_parser import SilentArgumentParser
from rebasehelper.helpers.download_helper import DownloadHelper
from rebasehelper.helpers.macro_helper import MacroHelper
from rebasehelper.helpers.rpm_helper import RpmHelper
from rebasehelper.helpers.git_helper import GitHelper
from rebasehelper.helpers.lookaside_cache_helper import LookasideCacheHelper


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
            if x.index == item.index:
                return x

    def __getitem__(self, item):
        return super(PatchList, self).__getitem__(self._get_index_list(item))


class PatchObject:

    """Class represents set of information about patches"""

    def __init__(self, path, index, strip):
        self.path = path
        self.index = index
        self.strip = strip

    def get_patch_name(self):
        return os.path.basename(self.path)


class PackageCategory(enum.Enum):
    python: Pattern[str] = re.compile(r'^python[23]?-')
    perl: Pattern[str] = re.compile(r'^perl-')
    ruby: Pattern[str] = re.compile(r'^rubygem-')
    nodejs: Pattern[str] = re.compile(r'^nodejs-')
    php: Pattern[str] = re.compile(r'^php-')
    haskell: Pattern[str] = re.compile(r'^ghc-')
    R: Pattern[str] = re.compile(r'^R-')
    rust: Pattern[str] = re.compile(r'^rust-')


class SpecContent:
    """Class representing content of a SPEC file."""

    SECTION_HEADERS: List[str] = [
        '%package',
        '%prep',
        '%build',
        '%install',
        '%check',
        '%clean',
        '%prerun',
        '%postrun',
        '%pretrans',
        '%posttrans',
        '%pre',
        '%post',
        '%files',
        '%changelog',
        '%description',
        '%triggerpostun',
        '%triggerprein',
        '%triggerun',
        '%triggerin',
        '%trigger',
        '%verifyscript',
        '%sepolicy',
        '%filetriggerin',
        '%filetrigger',
        '%filetriggerun',
        '%filetriggerpostun',
        '%transfiletriggerin',
        '%transfiletrigger',
        '%transfiletriggerun',
        '%transfiletriggerpostun',
    ]

    # Comments in these sections can only be on a separate line.
    DISALLOW_INLINE_COMMENTS: List[str] = [
        '%package',
        '%patchlist',
        '%sourcelist',
        '%description',
        '%files',
        '%changelog',
    ]

    def __init__(self, content):
        self.sections = self._split_sections(content)

    def __str__(self):
        """Join SPEC file sections back together."""
        content = []
        for header, section in self.sections:
            if header != '%package':
                content.append(header + '\n')
            for line in section:
                content.append(line + '\n')
        return ''.join(content)

    @classmethod
    def get_comment_span(cls, line: str, section: str) -> Tuple[int, int]:
        """Gets span of a comment depending on the section.

        Args:
            line: Line to find the comment in.
            section: Section the line is in.

        Returns:
            Span of the comment. If no comment is found, both tuple elements
            are equal to the length of the line for convenient use in a slice.

        """
        inline_comment_allowed = not any(section.startswith(s) for s in cls.DISALLOW_INLINE_COMMENTS)
        comment = re.search(r" #.*" if inline_comment_allowed else r"^\s*#.*", line)
        return comment.span() if comment else (len(line), len(line))

    def section(self, name):
        """Gets content of a section.

        In case there are multiple sections with the same name, the first one is returned.

        Args:
            name (str): Section name.

        Returns:
            list: Section content as a list of lines.

        """
        for header, section in self.sections:
            if header.lower() == name.lower():
                return section
        return None

    def replace_section(self, name, content):
        """Replaces content of a section.

        In case there are multiple sections with the same name, the first one is replaced.

        Args:
            name (str): Section name.
            content (list): Section content as a list of lines.

        Returns:
            bool: False if section was not found else True.

        """
        for i, (header, _) in enumerate(self.sections):
            if header.lower() == name.lower():
                self.sections[i] = (header, content)
                return True
        return False

    @classmethod
    def _split_sections(cls, content):
        """Splits content of a SPEC file into sections.

        Args:
            content (str): Content of the SPEC file

        """
        lines = content.splitlines()
        section_headers_re = [re.compile(r'^{0}\b.*'.format(re.escape(x)), re.IGNORECASE) for x in cls.SECTION_HEADERS]

        section_beginnings = []
        for i, line in enumerate(lines):
            if line.startswith('%'):
                for header in section_headers_re:
                    if header.match(line):
                        section_beginnings.append(i)
        section_beginnings.append(None)

        sections = [('%package', lines[:section_beginnings[0]])]

        for i in range(len(section_beginnings) - 1):
            start = section_beginnings[i] + 1
            end = section_beginnings[i + 1]
            sections.append((lines[start - 1], lines[start:end]))
        return sections


def saves(func):
    """Decorator for saving the SpecFile after a method is run."""
    def wrapper(spec, *args, **kwargs):
        func(spec, *args, **kwargs)
        spec.save()

    return wrapper


class SpecFile:

    """Class representing a SPEC file"""

    def __init__(self, path: str, sources_location: str = ''):
        # Initialize attributes
        self.path: str = path
        self.removed_patches: List[str] = []
        self.sources_location: str = sources_location
        self.prep_section: str = ''
        self.patches: Dict[str, List[PatchObject]] = {}
        self.sources: List[str] = []
        self.extra_version: str = ''
        self.extra_version_separator: str = ''
        self.category: Optional[PackageCategory] = None
        self.spc: rpm.spec = RpmHelper.get_rpm_spec(self.path)
        self.spec_content: SpecContent = self._read_spec_content()

        # Load rpm information
        self._update_data()

    def download_remote_sources(self):
        """
        Method that iterates over all sources and downloads ones, which contain URL instead of just a file.

        :return: None
        """
        try:
            # try to download old sources from Fedora lookaside cache
            LookasideCacheHelper.download('fedpkg', os.path.dirname(self.path), self.get_package_name(),
                                          self.sources_location)
        except LookasideCacheError as e:
            logger.verbose("Downloading sources from lookaside cache failed. "
                           "Reason: %s.", str(e))

        # filter out only sources with URL
        remote_files = [source for source in self.sources if bool(urllib.parse.urlparse(source).scheme)]
        # download any sources that are not yet downloaded
        for remote_file in remote_files:
            local_file = os.path.join(self.sources_location, os.path.basename(remote_file))
            if not os.path.isfile(local_file):
                logger.verbose("File '%s' doesn't exist locally, downloading it.", local_file)
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
        def guess_category():
            for pkg in self.spc.packages:
                for category in PackageCategory:
                    if category.value.match(RpmHelper.decode(pkg.header[rpm.RPMTAG_NAME])):
                        return category
                    for provide in pkg.header[rpm.RPMTAG_PROVIDENAME]:
                        if category.value.match(RpmHelper.decode(provide)):
                            return category
            return None
        # reset all macros and settings
        rpm.reloadConfig()
        # ensure that %{_sourcedir} macro is set to proper location
        MacroHelper.purge_macro('_sourcedir')
        rpm.addMacro('_sourcedir', self.sources_location)
        # explicitly discard old instance to prevent rpm from destroying
        # "sources" and "patches" lua tables after new instance is created
        self.spc = None
        self.spc = RpmHelper.get_rpm_spec(self.path)
        self.category = guess_category()
        self.sources = self._get_spec_sources_list(self.spc)
        self.prep_section = self.spc.prep
        # determine the extra_version
        logger.debug("Updating the extra version")
        _, self.extra_version, separator = SpecFile.extract_version_from_archive_name(
            self.get_archive(),
            self._get_raw_source_string(0))
        self.extra_version_separator = separator

        self.patches = self._get_initial_patches()
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
        source_re_str = r'^Source0?\s*:\s*(.*?)$' if source_num == 0 else r'^Source{0}\s*:\s*(.*?)$'.format(source_num)
        source_re = re.compile(source_re_str)

        for line in self.spec_content.section('%package'):
            match = source_re.search(line)
            if match:
                return match.group(1)

    ###########################
    # PATCHES RELATED METHODS #
    ###########################

    def _get_initial_patches(self) -> Dict[str, List[PatchObject]]:
        """Returns a dict of patches from a spec file"""
        patches_applied = []
        patches_not_used = []
        patches_list = [p for p in self.spc.sources if p[2] == 2]
        strip_options = self._get_patch_strip_options(patches_list)

        for patch, num, _ in patches_list:
            is_url = bool(urllib.parse.urlparse(patch).scheme)
            filename = os.path.basename(patch) if is_url else patch
            patch_path = os.path.join(self.sources_location, filename)
            if not os.path.exists(patch_path):
                if is_url:
                    logger.info('Patch%s is remote, trying to download the patch', num)
                    try:
                        DownloadHelper.download_file(patch, filename)
                    except DownloadError:
                        logger.error('Could not download remote patch %s', patch)
                        continue
                else:
                    logger.error('Patch %s does not exist', filename)
                    continue
            patch_num = num
            if patch_num in strip_options:
                patches_applied.append(PatchObject(patch_path, patch_num, strip_options[patch_num]))
            else:
                patches_not_used.append(PatchObject(patch_path, patch_num, None))
        patches_applied = sorted(patches_applied, key=lambda x: x.index)
        return {"applied": patches_applied, "not_applied": patches_not_used}

    def _get_patch_strip_options(self, patches):
        """
        Gets value of strip option of each used patch

        This should work reliably in most cases except when a list of patches
        is read from a file (netcf, libvirt).
        """
        parser = SilentArgumentParser()
        parser.add_argument('-p', type=int, default=0)
        result = {}
        for line in self.get_prep_section():
            tokens = shlex.split(line, comments=True)
            if not tokens:
                continue
            args = tokens[1:]
            try:
                ns, rest = parser.parse_known_args(args)
            except ParseError:
                continue
            rest = [os.path.basename(a) for a in rest]
            indexes = [p[1] for p in patches if p[0] in rest]
            for idx in indexes:
                if idx not in result or result[idx] < ns.p:
                    result[idx] = ns.p
        return result

    def _get_patch_number(self, fields):
        """
        Function returns patch number

        :param line:
        :return: patch_num
        """
        patch_num = fields[0].replace('Patch', '')[:-1]
        return patch_num

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

    def _process_patches(self, comment_out=None, remove_patches=None, disable_inapplicable_patches=None):
        """
        Comment out and delete patches from SPEC file

        :var comment_out: list with patch numbers to comment out
        :var remove_patches: list with patch numbers to delete
        :var disable_inapplicable_patches: boolean value deciding if the inapplicable patches should be commented out
        """
        if comment_out is None:
            comment_out = []
        if remove_patches is None:
            remove_patches = []

        prep = self.spec_content.section('%prep')
        if not prep:
            return

        i = 0
        while i < len(prep):
            line = prep[i]
            if line.startswith('%patch'):
                for num in reversed(comment_out):
                    if line.startswith('%patch{}'.format(num)):
                        if disable_inapplicable_patches:
                            prep[i] = '#%{}'.format(line)
                        prep.insert(i, '# The following patch contains conflicts')
                        comment_out.remove(num)
                        i += 1
                        break
                for num in reversed(remove_patches):
                    if line.startswith('%patch{}'.format(num)):
                        del prep[i]
                        remove_patches.remove(num)
                        i -= 1
                        break
            i += 1

    @saves
    def update_paths_to_patches(self):
        # Fix paths in rebase_spec_file to patches to current directory
        rebased_sources_path = os.path.join(constants.RESULTS_DIR, constants.REBASED_SOURCES_DIR)
        for index, line in enumerate(self.spec_content.section('%package')):
            if line.startswith('Patch'):
                mod_line = re.sub(rebased_sources_path + os.path.sep, '', line)
                self.spec_content.section('%package')[index] = mod_line

    @saves
    def write_updated_patches(self, patches, disable_inapplicable):
        """Function writes the patches to -rebase.spec file"""
        def is_comment(line):
            if re.match(r'^#\s*[A-Za-z][A-Za-z0-9]+:', line):
                # ignore commented-out tag
                return False
            return line.startswith('#')
        if not patches:
            return None
        # If some patches are not applied then comment out or remove
        removed_patches = []
        inapplicable_patches = []
        modified_patches = []

        preamble = self.spec_content.section('%package')

        i = 0
        while i < len(preamble):
            line = preamble[i]
            if line.startswith('Patch'):
                fields = line.strip().split()
                patch_name = fields[1]
                patch_num = self._get_patch_number(fields)

                if 'deleted' in patches:
                    patch_removed = [x for x in patches['deleted'] if patch_name in x]
                else:
                    patch_removed = None
                if 'inapplicable' in patches:
                    patch_inapplicable = [x for x in patches['inapplicable'] if patch_name in x]
                else:
                    patch_inapplicable = None

                if patch_removed:
                    # remove the line of the patch that was removed
                    self.removed_patches.append(patch_name)
                    removed_patches.append(patch_num)
                    # find associated comments
                    j = i
                    while j > 0 and is_comment(preamble[j - 1]):
                        j -= 1
                    del preamble[j: i+1]
                    i = j
                    continue

                if patch_inapplicable:
                    if disable_inapplicable:
                        # comment out line if the patch was not applied
                        preamble[i] = '#{0} {1}'.format(' '.join(fields[:-1]), os.path.basename(patch_name))
                    inapplicable_patches.append(patch_num)

                if 'modified' in patches:
                    patch = [x for x in patches['modified'] if patch_name in x]
                else:
                    patch = None
                if patch:
                    fields[1] = os.path.join(constants.RESULTS_DIR, constants.REBASED_SOURCES_DIR, patch_name)
                    preamble[i] = ' '.join(fields)
                    modified_patches.append(patch_num)
            i += 1

        self._process_patches(inapplicable_patches, removed_patches, disable_inapplicable)

    ###################################
    # PACKAGE VERSION RELATED METHODS #
    ###################################

    def get_NVR(self):
        return '{}-{}-{}'.format(self.get_package_name(), self.get_version(), self.get_release())

    def get_epoch_number(self) -> str:
        """Returns Epoch of the package."""
        return self.spc.sourceHeader[rpm.RPMTAG_EPOCHNUM]

    def get_release(self) -> str:
        """Returns the whole release string of the package."""
        return RpmHelper.decode(self.spc.sourceHeader[rpm.RPMTAG_RELEASE])

    def get_release_number(self):
        """
        Method for getting the release of the package

        :return:
        """
        release = self.get_release()
        dist = MacroHelper.expand('%{dist}')
        if dist:
            release = release.replace(dist, '')
        return re.sub(r'([0-9.]*[0-9]+).*', r'\1', release)

    def get_version(self) -> str:
        """Returns the package version."""
        return RpmHelper.decode(self.spc.sourceHeader[rpm.RPMTAG_VERSION])

    def get_extra_version(self):
        """
        Returns an extra version of the package - like b1, rc2, ...

        :return: String
        """
        return self.extra_version

    def set_release_number(self, release):
        """
        Method to set release number

        :param release:
        :return:
        """
        logger.verbose("Changing release number to '%s'", release)
        self.set_tag('Release', '{}%{{?dist}}'.format(release), preserve_macros=True)

    @saves
    def redefine_release_with_macro(self, macro):
        """
        Method redefines the Release: line to include passed macro and comments out the old line

        :param macro:
        :return:
        """
        release = '{}.{}%{{?dist}}'.format(self.get_release_number(), macro)
        preamble = self.spec_content.section('%package')
        for index, line in enumerate(preamble):
            if line.startswith('Release:'):
                logger.verbose("Commenting out original Release line '%s'", line.strip())
                preamble[index] = '#{0}'.format(line)
                line = 'Release: {}'.format(release)
                logger.verbose("Inserting new Release line '%s'", line)
                preamble.insert(index + 1, line)
                break

    @saves
    def revert_redefine_release_with_macro(self, macro):
        """
        Method removes the redefined the Release: line with given macro and uncomments the old Release line.

        :param macro:
        :return:
        """
        search_re = re.compile(r'^Release\s*:\s*[0-9.]*[0-9]+\.{0}%{{\?dist}}\s*'.format(macro))

        preamble = self.spec_content.section('%package')

        for index, line in enumerate(preamble):
            match = search_re.search(line)
            if match:
                # We will uncomment old line, so sanity check first
                if not preamble[index - 1].startswith('#Release:'):
                    raise RebaseHelperError("Redefined Release line in SPEC is not 'commented out' "
                                            "old line: '{0}'"
                                            .format(preamble[index - 1].strip()))
                logger.verbose("Uncommenting original Release line '%s'", preamble[index - 1].strip())
                preamble[index - 1] = preamble[index - 1].lstrip('#')
                logger.verbose("Removing redefined Release line '%s'", line.strip())
                preamble.pop(index)
                break

    @saves
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
                                   '%{REBASE_EXTRA_VER}'
        new_extra_version_line = '%global REBASE_EXTRA_VER {0}'.format(extra_version)

        logger.verbose("Updating extra version in SPEC to '%s'", extra_version)

        preamble = self.spec_content.section('%package')

        #  try to find existing extra version definition
        for index, line in enumerate(preamble):
            match = extra_version_re.search(line)
            if match:
                extra_version_line_index = index
                break

        if extra_version:
            #  just update the existing extra version
            if extra_version_line_index is not None:
                preamble[extra_version_line_index] = new_extra_version_line
            # we need to create the extra version definition
            else:
                # insert the REBASE_VER and REBASE_EXTRA_VER definitions
                logger.verbose("Adding new line to spec: %s", rebase_extra_version_def.strip())
                preamble.insert(0, rebase_extra_version_def)
                logger.verbose("Adding new line to spec: %s", new_extra_version_line.strip())
                preamble.insert(0, new_extra_version_line)

                # change Release to 0.1 and append the extra version macro
                self.set_release_number('0.1')
                self.redefine_release_with_macro(extra_version_macro)

                preamble = self.spec_content.section('%package')

                # change the Source0 definition
                source0_re = re.compile(r'^Source0?\s*:.+')
                for index, line in enumerate(preamble):
                    if source0_re.search(line):
                        # comment out the original Source0 line
                        logger.verbose("Commenting out original Source0 line '%s'", line.strip())
                        preamble[index] = '#{0}'.format(line)
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
                        logger.verbose("Inserting new Source0 line '%s'", new_source0_line)
                        preamble.insert(index + 1, new_source0_line)
                        break
        else:
            # set the Release to 1 and revert the redefined Release with macro if needed
            self.set_release_number('1')
            self.revert_redefine_release_with_macro(extra_version_macro)
            # TODO: handle empty extra_version as removal of the definitions!

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
        self.extra_version_separator = separator
        self.set_extra_version(extra_version)

    @saves
    def set_tag(self, tag, value, preserve_macros=False):
        """Sets value of a tag while trying to preserve macros if requested"""
        macro_def_re = re.compile(
            r'''
            ^
            (?P<cond>%{!?\?\w+:\s*)?
            (?(cond)%global|%(global|define))
            \s+
            (?P<name>\w+)
            (?P<options>\(.+?\))?
            \s+
            (?P<value>
                (%((?P<b>{)|(?P<s>\()))?
                .+?
                (?(b)})(?(s)\))
            )
            (?(cond)})
            $
            ''',
            re.VERBOSE | re.MULTILINE | re.DOTALL)

        def _get_macro_value(macro):
            """Returns raw value of a macro"""
            for match in macro_def_re.finditer('\n'.join(self.spec_content.section('%package'))):
                if match.group('name') == macro:
                    return match.group('value')
            return None

        def _redefine_macro(macro, value):
            """Replaces value of an existing macro"""
            content = '\n'.join(self.spec_content.section('%package'))
            for match in macro_def_re.finditer(content):
                if match.group('name') != macro:
                    continue
                content = content[:match.start('value')] + value + content[match.end('value'):]
                if match.group('options'):
                    content = content[:match.start('options')] + content[match.end('options'):]
                break
            self.spec_content.replace_section('%package', content.split('\n'))
            self.save()

        def _find_macros(s):
            """Returns all redefinable macros present in a string"""
            macro_re = re.compile(r'%(?P<brace>{\??)?(?P<name>\w+)(?(brace)})')
            macros = []
            for match in macro_def_re.finditer('\n'.join(self.spec_content.section('%package'))):
                macros.append(match.group('name'))
            result = []
            for match in macro_re.finditer(s):
                if not match:
                    continue
                if match.group('name') not in macros:
                    continue
                result.append((match.group('name'), match.span()))
            return result

        def _expand_macros(s):
            """Expands all redefinable macros containing redefinable macros"""
            replace = []
            for macro, span in _find_macros(s):
                value = _get_macro_value(macro)
                if not value:
                    continue
                rep = _expand_macros(value)
                if _find_macros(rep):
                    replace.append((rep, span))
            for rep, span in reversed(replace):
                s = s[:span[0]] + rep + s[span[1]:]
            return s

        def _tokenize(s):
            """Removes conditional macros and splits string on macro boundaries"""
            def parse(inp):
                tree = []
                text = ''
                macro = ''
                buf = ''
                escape = False
                while inp:
                    c = inp.pop(0)
                    if c == '%':
                        c = inp.pop(0)
                        if c == '%':
                            text += c
                        elif c == '{':
                            if text:
                                tree.append(('t', text))
                                text = ''
                            while inp and c not in ':}':
                                c = inp.pop(0)
                                buf += c
                            if c == ':':
                                tree.append(('c', buf[:-1], parse(inp)))
                                buf = ''
                            elif c == '}':
                                tree.append(('m', buf[:-1]))
                                buf = ''
                        elif c == '(':
                            if text:
                                tree.append(('t', text))
                                text = ''
                            tree.append(('s', None, parse(inp)))
                        else:
                            if text:
                                tree.append(('t', text))
                                text = ''
                            while inp and (c.isalnum() or c == '_'):
                                c = inp.pop(0)
                                macro += c
                            tree.append(('m', macro))
                            macro = ''
                    elif c == '$':
                        text += c
                        c = inp.pop(0)
                        if c == '{':
                            text += c
                            escape = True
                    elif c == '}':
                        if escape:
                            text += c
                            escape = False
                        else:
                            if text:
                                tree.append(('t', text))
                            inp.append(c)
                            return tree
                    elif c == ')':
                        if text:
                            tree.append(('t', text))
                        inp.append(c)
                        return tree
                    else:
                        text += c
                if text:
                    tree.append(('t', text))
                return tree

            def traverse(tree):
                result = []
                for node in tree:
                    if node[0] == 't':
                        result.append(node[1])
                    elif node[0] == 'm':
                        m = '%{{{}}}'.format(node[1])
                        if MacroHelper.expand(m):
                            result.append(m)
                    elif node[0] == 'c':
                        if MacroHelper.expand('%{{{}:1}}'.format(node[1])):
                            result.extend(traverse(node[2]))
                    elif node[0] == 's':
                        # ignore shell expansions, push nonsensical value
                        result.append('@')
                return result

            inp = list(s)
            tree = parse(inp)
            return traverse(tree)

        def _sync_macros(s):
            """Makes all macros present in a string up-to-date in rpm context"""
            macros = {m for m, _ in _find_macros(s)}
            macros.update(m for m, _ in _find_macros(_expand_macros(s)))
            for macro in macros:
                MacroHelper.purge_macro(macro)
                value = _get_macro_value(macro)
                if value and MacroHelper.expand(value):
                    rpm.addMacro(macro, value)

        def _process_value(curval, newval):
            """
            Replaces non-redefinable-macro parts of curval with matching parts from newval
            and redefines values of macros accordingly
            """
            value = _expand_macros(curval)
            _sync_macros(curval + newval)
            tokens = _tokenize(value)
            values = [None] * len(tokens)
            sm = SequenceMatcher(a=newval)
            i = 0
            # split newval to match tokens
            for index, token in enumerate(tokens):
                sm.set_seq2(token)
                m = sm.find_longest_match(i, len(newval), 0, len(token))
                # only full match in case of macro
                if m.size and token[0] != '%' or m.size == len(token):
                    tokens[index] = token[m.b:m.b+m.size]
                    if index > 0:
                        values[index] = newval[m.a:m.a+m.size]
                        if not values[index - 1]:
                            values[index - 1] = newval[i:m.a]
                    else:
                        values[index] = newval[i:m.a+m.size]
                    i = m.a + m.size
            if newval[i:]:
                if not values[-1]:
                    values[-1] = newval[i:]
                else:
                    values[-1] += newval[i:]
            # try to fill empty macros
            for index, token in enumerate(tokens):
                if token[0] == '%':
                    continue
                if token == values[index]:
                    continue
                for i in range(index - 1, 0, -1):
                    if tokens[i][0] == '%' and not values[i]:
                        values[i] = values[index]
                        values[index] = None
                        break
            # try to make values of identical macros equal
            for index, token in enumerate(tokens):
                if token[0] != '%':
                    continue
                for i in range(index - 1, 0, -1):
                    if tokens[i] == token:
                        idx = values[index].find(values[i])
                        if idx >= 0:
                            prefix = values[index][:idx]
                            for j in range(index - 1, i + 1, -1):
                                # first non-macro token
                                if tokens[j][0] != '%':
                                    if prefix.endswith(values[j]):
                                        # move token from the end of prefix to the beginning
                                        prefix = values[j] + prefix[:prefix.find(values[j])]
                                    else:
                                        # no match with prefix, cannot continue
                                        break
                                else:
                                    # remove prefix from the original value and append it to the value of this macro
                                    values[index] = values[index][idx:]
                                    values[j] += prefix
                                    break
                        break
            # redefine macros and update tokens
            for index, token in enumerate(tokens):
                if token == values[index]:
                    continue
                if not values[index]:
                    values[index] = '%{nil}' if token[0] == '%' else ''
                macros = _find_macros(token)
                if macros:
                    _redefine_macro(macros[0][0], values[index])
                else:
                    tokens[index] = values[index]
            result = ''.join(tokens)
            _sync_macros(curval + result)
            # only change value if necessary
            if MacroHelper.expand(curval) == MacroHelper.expand(result):
                return curval
            return result

        tag_re = re.compile(r'^(?P<name>\w+)\s*:\s*(?P<value>.+)$')
        for index, line in enumerate(self.spec_content.section('%package')):
            match = tag_re.match(line)
            if not match:
                continue
            if match.group('name') != tag:
                continue
            if preserve_macros:
                value = _process_value(match.group('value'), value)
            new_line = line[:match.start('value')] + value + line[match.end('value'):]
            self.spec_content.section('%package')[index] = new_line
            break

    def set_version(self, version):
        """
        Method to update the version in the SPEC file

        :param version: string with new version
        :return: None
        """
        logger.verbose("Updating version in SPEC from '%s' with '%s'", self.get_version(), version)
        self.set_tag('Version', version, preserve_macros=True)

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
        regex_str = re.sub(r'%{version}(%{.+})?', 'PLACEHOLDER', url_base, flags=re.IGNORECASE)
        regex_str = MacroHelper.expand(regex_str, regex_str)
        regex_str = re.escape(regex_str).replace('PLACEHOLDER', version_regex_str)

        # if no substitution was made, use the fallback regex
        if regex_str == re.escape(MacroHelper.expand(url_base, url_base)):
            logger.debug('Using fallback regex to extract version from archive name.')
            regex_str = fallback_regex_str

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

    def get_prep_section(self):
        """Function returns whole prep section"""
        def unmatched_quotation(s):
            try:
                shlex.split(s, comments=True)
            except ValueError:
                return True
            return False
        if not self.prep_section:
            return []
        prep = self.prep_section.split('\n')
        # join lines split by backslash or ending with pipe
        result = [prep.pop(0)]
        while prep:
            if result[-1].rstrip().endswith('\\'):
                result[-1] = result[-1][:-1] + prep.pop(0)
            elif result[-1].rstrip().endswith('|') or unmatched_quotation(result[-1]):
                result[-1] = result[-1] + prep.pop(0)
            else:
                result.append(prep.pop(0))
        return result

    @staticmethod
    def get_subpackage_name(files_section):
        """Gets subpackage name based on the %files section."""
        parser = SilentArgumentParser()
        parser.add_argument('-n', default=None)
        parser.add_argument('-f')
        parser.add_argument('subpackage', nargs='?', default=None)
        ns, _ = parser.parse_known_args(shlex.split(files_section)[1:])
        if ns.n:
            return ns.n
        elif ns.subpackage:
            return '%{{name}}-{}'.format(ns.subpackage)
        else:
            return '%{name}'

    def get_main_files_section(self):
        """Finds the exact name of the main %files section.

        Returns:
            str: Name of the main files section.

        """
        for sec_name, _ in self.spec_content.sections:
            if sec_name.startswith('%files'):
                if self.get_subpackage_name(sec_name) == '%{name}':
                    return sec_name

    #############################################
    # SPEC CONTENT MANIPULATION RELATED METHODS #
    #############################################

    def _read_spec_content(self) -> SpecContent:
        """Reads the content of the Spec file.

        Returns:
            The created SpecContent instance.

        Raises:
            RebaseHelperError: If the Spec file cannot be read.

        """
        try:
            with open(self.path) as f:
                content = f.read()
        except IOError:
            raise RebaseHelperError("Unable to open and read SPEC file '{}'".format(self.path))
        return SpecContent(content)

    def _write_spec_content(self):
        """Writes the current state of SpecContent into a file."""
        logger.verbose("Writing SPEC file '%s' to the disc", self.path)
        try:
            with open(self.path, "w") as f:
                f.write(str(self.spec_content))
        except IOError:
            raise RebaseHelperError("Unable to write updated data to SPEC file '{}'".format(self.path))

    def copy(self, new_path):
        """Creates a copy of the current object and copies the SPEC file
        to a new location.

        Args:
            new_path (str): Path to copy the new SPEC file to.

        Returns:
            SpecFile: The created SpecFile instance.

        """
        shutil.copy(self.path, new_path)
        new_object = SpecFile(new_path, self.sources_location)
        return new_object

    def reload(self):
        """Reloads the whole Spec file."""
        self._read_spec_content()
        self._update_data()

    def save(self):
        """Saves changes made to SpecContent and updates the internal state."""
        self._write_spec_content()
        #  Update internal variables
        self._update_data()

    ####################
    # UNSORTED METHODS #
    ####################

    def is_test_suite_enabled(self):
        """
        Returns whether test suite is enabled during the build time

        :return: True if enabled or False if not
        """
        check_section = self.spec_content.section('%check')
        if not check_section:
            return False
        # Remove commented lines
        check_section = [x.strip() for x in check_section if not x.strip().startswith('#')]
        # If there is at least one line with some command in %check we assume test suite is run
        if check_section:
            return True
        else:
            return False

    def get_package_name(self) -> str:
        """Returns name of the package."""
        return RpmHelper.decode(self.spc.sourceHeader[rpm.RPMTAG_NAME])

    def get_requires(self) -> List[str]:
        """Returns package requirements."""
        return [RpmHelper.decode(r) for r in self.spc.sourceHeader[rpm.RPMTAG_REQUIRES]]

    @saves
    def update_changelog(self, changelog_entry):
        """Inserts a new entry into the changelog and saves the SpecFile.

        Args:
            changelog_entry (str): Message to use in the entry.

        """
        new_entry = self.get_new_log(changelog_entry)
        self.spec_content.section('%changelog')[0:0] = new_entry

    def get_new_log(self, changelog_entry):
        """Constructs a new changelog entry.

        Args:
            changelog_entry (str): Message to use in the entry.

        Returns:
            list: List of lines of the new entry.

        """
        new_record = []
        today = date.today()
        evr = '{epoch}:{ver}-{rel}'.format(epoch=self.get_epoch_number(),
                                           ver=self.get_version(),
                                           rel=self.get_release_number())
        evr = evr[2:] if evr.startswith('0:') else evr
        new_record.append('* {day} {name} <{email}> - {evr}'.format(day=today.strftime('%a %b %d %Y'),
                                                                    name=GitHelper.get_user(),
                                                                    email=GitHelper.get_email(),
                                                                    evr=evr))
        self._update_data()
        new_record.append(MacroHelper.expand(changelog_entry, changelog_entry))
        new_record.append('')
        return new_record

    def _get_setup_parser(self):
        """
        Construct ArgumentParser for parsing %(auto)setup macro arguments

        :return: constructed ArgumentParser
        """
        parser = SilentArgumentParser()
        parser.add_argument('-n', default=MacroHelper.expand('%{name}-%{version}', '%{name}-%{version}'))
        parser.add_argument('-a', type=int, default=-1)
        parser.add_argument('-b', type=int, default=-1)
        parser.add_argument('-T', action='store_true')
        parser.add_argument('-q', action='store_true')
        parser.add_argument('-c', action='store_true')
        parser.add_argument('-D', action='store_true')
        parser.add_argument('-v', action='store_true')
        parser.add_argument('-N', action='store_true')
        parser.add_argument('-p', type=int, default=-1)
        parser.add_argument('-S', default='')
        return parser

    def get_setup_dirname(self):
        """
        Get dirname from %setup or %autosetup macro arguments

        :return: dirname
        """
        parser = self._get_setup_parser()

        prep = self.spec_content.section('%prep')
        if not prep:
            return None

        for line in prep:
            if line.startswith('%setup') or line.startswith('%autosetup'):
                args = shlex.split(line)
                args = [MacroHelper.expand(a, '') for a in args[1:]]

                # parse macro arguments
                try:
                    ns, _ = parser.parse_known_args(args)
                except ParseError:
                    continue

                # check if this macro instance is extracting Source0
                if not ns.T or ns.a == 0 or ns.b == 0:
                    return ns.n

        return None

    @saves
    def update_setup_dirname(self, dirname):
        """
        Update %setup or %autosetup dirname argument if needed

        :param dirname: new dirname to be used
        """
        parser = self._get_setup_parser()

        prep = self.spec_content.section('%prep')
        if not prep:
            return

        for index, line in enumerate(prep):
            if line.startswith('%setup') or line.startswith('%autosetup'):
                args = shlex.split(line)
                macro = args[0]
                args = [MacroHelper.expand(a, '') for a in args[1:]]

                # parse macro arguments
                try:
                    ns, unknown = parser.parse_known_args(args)
                except ParseError:
                    continue

                # check if this macro instance is extracting Source0
                if ns.T and ns.a != 0 and ns.b != 0:
                    continue

                # check if modification is really necessary
                if dirname != ns.n:
                    new_dirname = dirname

                    # get %{name} and %{version} macros
                    macros = [m for m in MacroHelper.filter(self.macros, level=-3) if m['name'] in ('name', 'version')]
                    # add all macros from spec file scope
                    macros.extend(MacroHelper.filter(self.macros, level=0))
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
                    if ns.q:
                        args.append('-q')
                    if ns.c:
                        args.append('-c')
                    if ns.D:
                        args.append('-D')
                    if ns.v:
                        args.append('-v')
                    if ns.N:
                        args.append('-N')
                    if ns.p != -1:
                        args.extend(['-p', str(ns.p)])
                    if ns.S != '':
                        args.extend(['-S', ns.S])
                    args.extend(unknown)

                    prep[index] = '#{0}'.format(line)
                    prep.insert(index + 1, ' '.join(args))

    def find_archive_target_in_prep(self, archive):
        """
        Tries to find a command that is used to extract the specified archive
        and attempts to determine target path from it.
        'tar' and 'unzip' commands are supported so far.

        :param archive: Path to archive
        :return: Target path relative to builddir or None if not determined
        """
        cd_parser = SilentArgumentParser()
        cd_parser.add_argument('dir', default=os.environ.get('HOME', ''))
        tar_parser = argparse.ArgumentParser()
        tar_parser.add_argument('-C', default='.', dest='target')
        unzip_parser = argparse.ArgumentParser()
        unzip_parser.add_argument('-d', default='.', dest='target')
        archive = os.path.basename(archive)
        builddir = MacroHelper.expand('%{_builddir}', '')
        basedir = builddir
        for line in self.get_prep_section():
            tokens = shlex.split(line, comments=True)
            if not tokens:
                continue
            # split tokens by pipe
            for tokens in [list(group) for k, group in itertools.groupby(tokens, lambda t: t == '|') if not k]:
                cmd, args = os.path.basename(tokens[0]), tokens[1:]
                if cmd == 'cd':
                    # keep track of current directory
                    try:
                        ns, _ = cd_parser.parse_known_args(args)
                    except ParseError:
                        pass
                    else:
                        basedir = ns.dir if os.path.isabs(ns.dir) else os.path.join(basedir, ns.dir)
                if archive in line:
                    if cmd == 'tar':
                        parser = tar_parser
                    elif cmd == 'unzip':
                        parser = unzip_parser
                    else:
                        continue
                    try:
                        ns, _ = parser.parse_known_args(args)
                    except ParseError:
                        continue
                    basedir = os.path.relpath(basedir, builddir)
                    return os.path.normpath(os.path.join(basedir, ns.target))
        return None
