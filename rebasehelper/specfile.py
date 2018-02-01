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
import rpm
import argparse
import shlex
import itertools

import pkg_resources

import six

from datetime import date
from difflib import SequenceMatcher
from operator import itemgetter

from six.moves import urllib

from rebasehelper.utils import DownloadHelper, DownloadError, MacroHelper, GitHelper, RpmHelper
from rebasehelper.utils import LookasideCacheHelper, LookasideCacheError, defenc
from rebasehelper.logger import logger
from rebasehelper import settings
from rebasehelper.archive import Archive
from rebasehelper.exceptions import RebaseHelperError


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
    strip = ''
    git_generated = ''

    def __init__(self, path, index, strip):
        self.path = path
        self.index = index
        self.strip = strip

    def get_path(self):
        return self.path

    def get_index(self):
        return self.index

    def set_path(self, new_path):
        self.path = new_path

    def get_patch_name(self):
        return os.path.basename(self.path)

    def get_strip(self):
        return self.strip


class SpecFile(object):

    """Class representing a SPEC file"""

    path = ''
    download = False
    spec_content = []
    spc = None
    hdr = None
    extra_version = None
    category = None
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

    def __init__(self, path, changelog_entry, sources_location='', download=True):
        self.path = path
        self.download = download
        self.sources_location = sources_location
        self.changelog_entry = changelog_entry
        #  Read the content of the whole SPEC file
        self._read_spec_content()
        # Load rpm information
        self.set_extra_version_separator('')
        self.removed_patches = []
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

    def _guess_category(self):
        def _decode(s):
            if six.PY3:
                return s.decode(defenc)
            return s
        categories = {
            'python': re.compile(r'^python[23]?-'),
            'perl': re.compile(r'^perl-'),
            'ruby': re.compile(r'^rubygem-'),
            'nodejs': re.compile(r'^nodejs-'),
            'php': re.compile(r'^php-'),
        }
        for pkg in self.spc.packages:
            for category, regexp in six.iteritems(categories):
                if regexp.match(_decode(pkg.header[rpm.RPMTAG_NAME])):
                    return category
                for provide in pkg.header[rpm.RPMTAG_PROVIDENAME]:
                    if regexp.match(_decode(provide)):
                        return category
        return None

    def _update_data(self):
        """
        Function updates data from given SPEC file

        :return:
        """
        def replace_macro(macro, value):
            m = '%{{{}}}'.format(macro)
            while MacroHelper.expand(m, m) != m:
                rpm.delMacro(macro)
            rpm.addMacro(macro, value)
        # ensure that %{_sourcedir} macro is set to proper location
        replace_macro('_sourcedir', self.sources_location)
        # explicitly discard old instance to prevent rpm from destroying
        # "sources" and "patches" lua tables after new instance is created
        self.spc = None
        # load rpm information
        try:
            self.spc = RpmHelper.parse_spec(self.path, flags=rpm.RPMSPEC_ANYARCH)
        except ValueError:
            try:
                # try again with RPMSPEC_FORCE flag (the default)
                self.spc = RpmHelper.parse_spec(self.path)
            except ValueError:
                raise RebaseHelperError("Problem with parsing SPEC file '%s'" % self.path)
        self.category = self._guess_category()
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
        source_re_str = '^Source0?\s*:\s*(.*?)$' if source_num == 0 else '^Source{0}\s*:\s*(.*?)$'.format(source_num)
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
        strip_options = self._get_patch_strip_options(patches_list)

        for filename, num, _ in patches_list:
            patch_path = os.path.join(self.sources_location, filename)
            if not os.path.exists(patch_path):
                logger.error('Patch %s does not exist', filename)
                continue
            patch_num = num
            if patch_num in strip_options:
                patches_applied.append(PatchObject(patch_path, patch_num, strip_options[patch_num]))
            else:
                patches_not_used.append(PatchObject(patch_path, patch_num, None))
        patches_applied = sorted(patches_applied, key=lambda x: x.get_index())
        return {"applied": patches_applied, "not_applied": patches_not_used}

    def _get_patch_strip_options(self, patches):
        """
        Gets value of strip option of each used patch

        This should work reliably in most cases except when a list of patches
        is read from a file (netcf, libvirt).
        """
        parser = argparse.ArgumentParser()
        parser.add_argument('-p', type=int, default=0)
        result = {}
        for line in self.get_prep_section():
            tokens = shlex.split(line, comments=True)
            if not tokens:
                continue
            args = tokens[1:]
            ns, rest = parser.parse_known_args(args)
            rest = [os.path.basename(a) for a in rest]
            indexes = [p[1] for p in patches if p[0] in rest]
            for idx in indexes:
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

        for index, line in enumerate(self.spec_content):
            #  if patch is applied on the line, try to check if it should be commented out
            if line.startswith('%patch'):
                #  check patch numbers
                for num in comment_out:
                    #  if the line should be commented out
                    if line.startswith('%patch{0}'.format(num)):
                        comment = '# Following patch contains conflicts\n'
                        if disable_inapplicable_patches:
                            self.spec_content[index] = '{}#%{}'.format(comment, line)
                        else:
                            self.spec_content[index] = '{}{}'.format(comment, line)
                        #  remove the patch number from list
                        comment_out.remove(num)
                        break
                for num in remove_patches:
                    #  if the line should be removed
                    if line.startswith('%patch{0}'.format(num)):
                        self.spec_content[index] = ''
                        #  remove the patch number from list
                        remove_patches.remove(num)
                        break

    def update_paths_to_patches(self):
        # Fix paths in rebase_spec_file to patches to current directory
        for index, line in enumerate(self.spec_content):
            if line.startswith('Patch'):
                mod_line = re.sub(settings.REBASE_HELPER_REBASED_SOURCES_DIR + '/', '', line)
                self.spec_content[index] = mod_line
        self.save()

    def write_updated_patches(self, patches, disable_inapplicable):
        """Function writes the patches to -rebase.spec file"""
        if not patches:
            return None
        # If some patches are not applied then comment out or remove
        removed_patches = []
        inapplicable_patches = []
        modified_patches = []

        for index, line in enumerate(self.spec_content):
            if line.startswith('Patch'):
                fields = line.strip().split()
                patch_name = fields[1]
                patch_num = self._get_patch_number(fields)
                # We check if patch is mentioned in SPEC file but not used.
                # We comment out the patch
                check_not_applied = [x for x in self.get_not_used_patches() if
                                     int(x.get_index()) == int(patch_num)]

                if 'deleted' in patches:
                    patch_removed = [x for x in patches['deleted'] if patch_name in x]
                else:
                    patch_removed = None
                if 'inapplicable' in patches:
                    patch_inapplicable = [x for x in patches['inapplicable'] if patch_name in x]
                else:
                    patch_inapplicable = None

                if patch_removed or check_not_applied:
                    # remove the line of the patch that was removed
                    self.removed_patches.append(patch_name)
                    removed_patches.append(patch_num)
                    self.spec_content[index] = ''

                if patch_inapplicable:
                    if disable_inapplicable:
                        # comment out line if the patch was not applied
                        self.spec_content[index] = '#{0} {1}\n'.format(' '.join(fields[:-1]),
                                                                       os.path.basename(patch_name))
                    inapplicable_patches.append(patch_num)

                if 'modified' in patches:
                    patch = [x for x in patches['modified'] if patch_name in x]
                else:
                    patch = None
                if patch:
                    fields[1] = os.path.join(settings.REBASE_HELPER_REBASED_SOURCES_DIR, patch_name)
                    self.spec_content[index] = ' '.join(fields) + '\n'
                    modified_patches.append(patch_num)

        self._process_patches(inapplicable_patches, removed_patches, disable_inapplicable)

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
        release = self.get_release()
        dist = MacroHelper.expand('%{dist}')
        if dist:
            release = release.replace(dist, '')
        return re.sub(r'([0-9.]*[0-9]+).*', r'\1', release)

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
        logger.debug("Changing release number to '%s'", release)
        self.set_tag('Release', '{}%{{?dist}}'.format(release), preserve_macros=True)

    def redefine_release_with_macro(self, macro):
        """
        Method redefines the Release: line to include passed macro and comments out the old line

        :param macro:
        :return:
        """
        release = '{}.{}%{{?dist}}'.format(self.get_release_number(), macro)
        for index, line in enumerate(self.spec_content):
            if line.startswith('Release:'):
                logger.debug("Commenting out original Release line '%s'", line.strip())
                self.spec_content[index] = '#{0}'.format(line)
                line = 'Release: {}\n'.format(release)
                logger.debug("Inserting new Release line '%s'", line)
                self.spec_content.insert(index + 1, line)
                self.save()
                break

    def revert_redefine_release_with_macro(self, macro):
        """
        Method removes the redefined the Release: line with given macro and uncomments the old Release line.

        :param macro:
        :return:
        """
        search_re = re.compile(r'^Release\s*:\s*[0-9.]*[0-9]+\.{0}%{{\?dist}}\s*'.format(macro))

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
                source0_re = re.compile(r'^Source0?\s*:.+')
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
            (?P<value>.+)
            (?(cond)})
            $
            ''',
            re.VERBOSE)

        def _get_macro_value(macro):
            """Returns raw value of a macro"""
            for line in self.spec_content:
                match = macro_def_re.match(line)
                if not match:
                    continue
                if match.group('name') == macro:
                    return match.group('value')
            return None

        def _redefine_macro(macro, value):
            """Replaces value of an existing macro"""
            for index, line in enumerate(self.spec_content):
                match = macro_def_re.match(line)
                if not match:
                    continue
                if match.group('name') != macro:
                    continue
                line = line[:match.start('value')] + value + line[match.end('value'):]
                if match.group('options'):
                    line = line[:match.start('options')] + line[match.end('options'):]
                self.spec_content[index] = line
                break
            self.save()

        def _find_macros(s):
            """Returns all redefinable macros present in a string"""
            macro_re = re.compile(r'%(?P<brace>{\??)?(?P<name>\w+)(?(brace)})')
            macros = []
            for line in self.spec_content:
                match = macro_def_re.match(line)
                if not match:
                    continue
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
                        else:
                            if text:
                                tree.append(('t', text))
                                text = ''
                            while inp and (c.isalnum() or c == '_'):
                                c = inp.pop(0)
                                macro += c
                            tree.append(('m', macro))
                            macro = ''
                    elif c == '}':
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
                return result

            inp = list(s)
            tree = parse(inp)
            return traverse(tree)

        def _sync_macros(s):
            """Makes all macros present in a string up-to-date in rpm context"""
            macros = set([m for m, _ in _find_macros(s)])
            macros.update([m for m, _ in _find_macros(_expand_macros(s))])
            for macro in macros:
                m = '%{{{}}}'.format(macro)
                while MacroHelper.expand(m, m) != m:
                    rpm.delMacro(macro)
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
        for index, line in enumerate(self.spec_content):
            match = tag_re.match(line)
            if not match:
                continue
            if match.group('name') != tag:
                continue
            if preserve_macros:
                value = _process_value(match.group('value'), value)
            self.spec_content[index] = line[:match.start('value')] + value + line[match.end('value'):]
            break
        self.save()

    def set_version(self, version):
        """
        Method to update the version in the SPEC file

        :param version: string with new version
        :return: None
        """
        logger.debug("Updating version in SPEC from '%s' with '%s'", self.get_version(), version)
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
        regex_str = re.escape(regex_str).replace('PLACEHOLDER', version_regex_str)

        # if no substitution was made, use the fallback regex
        if regex_str == re.escape(url_base):
            logger.debug('Using fallback regex to extract version from archive name.')
            regex_str = fallback_regex_str
        else:
            regex_str = MacroHelper.expand(regex_str, regex_str)

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
            for _, value in sorted(six.iteritems(self.rpm_sections)):
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
        section_headers_re = [re.compile('^{0}.*'.format(x), re.IGNORECASE) for x in self.defined_sections]

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
            if sec_name.lower() == section_name.lower():
                return section

    def set_spec_section(self, section_name, new_section):
        """
        Returns the section of selected name

        :param section_name: section name to get
        :return: list of lines contained in the selected section
        """
        for key, val in six.iteritems(self.rpm_sections):
            if section_name.lower() in val[0].lower():
                if isinstance(new_section, str):
                    self.rpm_sections[key] = (section_name, new_section.split('\n'))
                else:
                    self.rpm_sections[key] = (section_name, new_section)

    def get_prep_section(self):
        """Function returns whole prep section"""
        prep = self.prep_section.split('\n')
        # join lines split by backslash
        result = []
        while prep:
            if result and result[-1].endswith('\\'):
                result[-1] = result[-1][:-1] + prep.pop(0)
            else:
                result.append(prep.pop(0))
        return result

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
        new_object = SpecFile(new_path, self.changelog_entry, self.sources_location, self.download)
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

    def get_new_log(self):
        new_record = []
        today = date.today()
        evr = '{epoch}:{ver}-{rel}'.format(epoch=self.get_epoch_number(),
                                           ver=self.get_version(),
                                           rel=self.get_release_number())
        evr = evr[2:] if evr.startswith('0:') else evr
        new_record.append('* {day} {name} <{email}> - {evr}\n'.format(day=today.strftime('%a %b %d %Y'),
                                                                      name=GitHelper.get_user(),
                                                                      email=GitHelper.get_email(),
                                                                      evr=evr))
        self._update_data()
        new_record.append(MacroHelper.expand(self.changelog_entry, self.changelog_entry) + '\n')
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

        for line in self.spec_content:
            if line.startswith('%setup') or line.startswith('%autosetup'):
                line = MacroHelper.expand(line, '')

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
                line = MacroHelper.expand(line, '')

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
    def get_categories(cls):
        """Returns list of categories of a spec hook"""
        raise NotImplementedError()

    @classmethod
    def run(cls, spec_file, rebase_spec_file, **kwargs):
        """
        Runs a spec hook.

        :param spec_file: Original spec file object
        :param rebase_spec_file: Rebased spec file object
        :param kwargs: Keyword arguments from Application instance
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

    def get_available_spec_hooks(self):
        """Returns a list of all available spec hooks"""
        return [v.__name__ for v in six.itervalues(self.spec_hooks)]

    def run_spec_hooks(self, spec_file, rebase_spec_file, **kwargs):
        """
        Runs all spec hooks.

        :param spec_file: Original spec file object
        :param rebase_spec_file: Rebased spec file object
        :param kwargs: Keyword arguments from Application instance
        """
        blacklist = kwargs.get("spec_hook_blacklist", [])

        for name, spec_hook in six.iteritems(self.spec_hooks):
            if spec_hook.__name__ in blacklist:
                continue
            categories = spec_hook.get_categories()
            if not categories or spec_file.category in categories:
                logger.info("Running '%s' spec hook", name)
                spec_hook.run(spec_file, rebase_spec_file, **kwargs)


# Global instance of SpecHooksRunner. It is enough to load it once per application run.
spec_hooks_runner = SpecHooksRunner()
