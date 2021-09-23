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
import collections
import enum
import itertools
import locale
import logging
import os
import re
import shlex
import shutil
import urllib.parse
from datetime import date
from difflib import SequenceMatcher
from operator import itemgetter
from typing import List, Optional, Pattern, Tuple, Dict, Union, cast

import rpm  # type: ignore

from rebasehelper import constants
from rebasehelper.archive import Archive
from rebasehelper.spec_content import SpecContent
from rebasehelper.tags import Tag, Tags
from rebasehelper.exceptions import RebaseHelperError, DownloadError, ParseError, LookasideCacheError
from rebasehelper.argument_parser import SilentArgumentParser
from rebasehelper.logger import CustomLogger
from rebasehelper.helpers.download_helper import DownloadHelper
from rebasehelper.helpers.macro_helper import MacroHelper
from rebasehelper.helpers.rpm_helper import RpmHelper, RpmHeader
from rebasehelper.helpers.git_helper import GitHelper
from rebasehelper.helpers.lookaside_cache_helper import LookasideCacheHelper


logger: CustomLogger = cast(CustomLogger, logging.getLogger(__name__))


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
        return super().__getitem__(self._get_index_list(item))


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


def saves(func):
    """Decorator for saving the SpecFile after a method is run."""
    def wrapper(spec, *args, **kwargs):
        func(spec, *args, **kwargs)
        spec.save()

    return wrapper


class SpecFile:

    """Class representing a SPEC file. Be aware that using SpecFile
    modifies RPM macros in global context."""

    def __init__(self, path: str, sources_location: str = '', predefined_macros: Optional[Dict[str, str]] = None,
                 lookaside_cache_preset: str = 'fedpkg', keep_comments: bool = False):
        # Initialize attributes
        self.path: str = path
        self.sources_location: str = sources_location
        self.predefined_macros: Dict[str, str] = predefined_macros or {}
        self.lookaside_cache_preset: str = lookaside_cache_preset
        self.keep_comments: bool = keep_comments
        self.prep_section: str = ''
        self.sources: List[str] = []
        self.patches: Dict[str, List[PatchObject]] = {}
        self.removed_patches: List[str] = []
        self.category: Optional[PackageCategory] = None
        self.spc: rpm.spec = RpmHelper.get_rpm_spec(self.path, self.sources_location, self.predefined_macros)
        self.header: RpmHeader = RpmHeader(self.spc.sourceHeader)
        self.spec_content: SpecContent = self._read_spec_content()
        self.tags: Tags = Tags(self.spec_content, SpecContent(self.spc.parsed))

        # Load rpm information
        self._update_data()

    def __del__(self):
        # make sure there are no leftover macros
        rpm.reloadConfig()

    def download_remote_sources(self):
        """
        Method that iterates over all sources and downloads ones, which contain URL instead of just a file.

        :return: None
        """
        try:
            # try to download old sources from Fedora lookaside cache
            LookasideCacheHelper.download(self.lookaside_cache_preset, os.path.dirname(self.path), self.header.name,
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
                                            "Reason: '{}'. ".format(remote_file, str(e))) from e

    def update(self) -> None:
        # explicitly discard old instance to prevent rpm from destroying
        # "sources" and "patches" lua tables after new instance is created
        self.spc = None
        self.spc = RpmHelper.get_rpm_spec(self.path, self.sources_location, self.predefined_macros)
        self.header = RpmHeader(self.spc.sourceHeader)
        self.spec_content = self._read_spec_content()
        self.tags = Tags(self.spec_content, SpecContent(self.spc.parsed))
        self._update_data()

    def _update_data(self):
        """
        Function updates data from given SPEC file

        :return:
        """
        def guess_category():
            for pkg in self.spc.packages:
                header = RpmHeader(pkg.header)
                for category in PackageCategory:
                    if category.value.match(header.name):
                        return category
                    for provide in header.providename:
                        if category.value.match(provide):
                            return category
            return None
        self.category = guess_category()
        self.sources = self._get_spec_sources_list(self.spc)
        self.prep_section = self.spc.prep
        self.main_source_index = self._identify_main_source(self.spc)
        self.patches = self._get_initial_patches()
        self.macros = MacroHelper.dump()

    ######################
    # TAG HELPER METHODS #
    ######################

    def tag(self, name: str, section: Optional[Union[str, int]] = None) -> Optional[Tag]:
        """Returns the first non-unique tag."""
        if isinstance(section, str):
            tags = self.tags.filter(section_name=section, name=name)
        else:
            tags = self.tags.filter(section_index=section, name=name)
        return next(tags, None)

    def get_raw_tag_value(self, tag_name: str, section: Optional[Union[str, int]] = None) -> Optional[str]:
        tag = self.tag(tag_name, section)
        if not tag:
            return None
        return self.spec_content[tag.section_index][tag.line][slice(*tag.value_span)]

    def set_raw_tag_value(self, tag_name: str, value: str, section: Optional[Union[str, int]] = None) -> None:
        tag = self.tag(tag_name, section)
        if not tag:
            return
        sec = self.spec_content[tag.section_index]
        line = sec[tag.line]
        sec[tag.line] = line[:tag.value_span[0]] + value + line[tag.value_span[1]:]
        # update span
        tag.value_span = (tag.value_span[0], tag.value_span[0] + len(value))

    ###########################
    # SOURCES RELATED METHODS #
    ###########################

    @staticmethod
    def _identify_main_source(spec: rpm.spec) -> Optional[int]:
        # a spec file does not need to have sources
        if not spec.sources:
            return None
        # lowest index is the main source
        return min([s[1] for s in spec.sources if s[2] == 1])

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

    def get_sources(self) -> List[str]:
        """Gets a list of local sources."""
        return [os.path.join(self.sources_location, os.path.basename(source)) for source in self.sources]

    def get_archive(self):
        """
        Method returns the basename of first Source in SPEC file a.k.a. Source0

        :return: basename of first Source in SPEC file
        :rtype: str
        """
        return os.path.basename(self.get_sources()[0])

    def _get_raw_source_string(self, source_num: Optional[int]) -> Optional[str]:
        if source_num is None:
            return None
        tag = 'Source{0}'.format(source_num)
        return self.get_raw_tag_value(tag)

    def get_main_source(self) -> str:
        """Provide the main source, returns empty string if there are no sources"""
        return self._get_raw_source_string(self.main_source_index) or ''

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

    def _get_patch_strip_options(self, patches: List[Tuple[str, int, int]]):
        """
        Gets value of strip option of each used patch

        This should work reliably in most cases except when a list of patches
        is read from a file (netcf, libvirt).
        """
        parser = SilentArgumentParser()
        parser.add_argument('-p', type=int, default=1)
        result: Dict[int, int] = {}
        for line in self.get_prep_section():
            try:
                tokens = shlex.split(line, comments=True)
            except ValueError:
                continue
            if not tokens:
                continue
            args = tokens[1:]
            try:
                ns, rest = parser.parse_known_args(args)
            except ParseError:
                continue
            rest = [os.path.basename(a) for a in rest]
            indexes = [p[1] for p in patches if os.path.basename(p[0]) in rest]
            for idx in indexes:
                if idx not in result or result[idx] < ns.p:
                    result[idx] = ns.p
        return result

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

    def process_patch_macros(self, comment_out: Optional[List[int]] = None, remove: Optional[List[int]] = None,
                             annotate: Optional[List[int]] = None, note: Optional[str] = None) -> None:
        """Processes %patch macros in %prep section.

        Args:
            comment_out: List of patch numbers to comment out.
            remove: List of patch numbers to remove.
            annotate: List of patch numbers to annotate.
            note: Message to annotate patches with.
        """
        comment_out = list(comment_out or [])
        remove = list(remove or [])
        annotate = list(annotate or [])

        prep = self.spec_content.section('%prep')
        if not prep:
            return

        patch_re = re.compile(r'^%patch(?P<index>\d+)(.*)')

        i = 0
        removed = 0
        while i < len(prep):
            line = prep[i]
            match = patch_re.match(line)
            if match:
                index = int(match.group('index'))
                if note and index in annotate and index not in remove:
                    prep.insert(i, '# {}'.format(note))
                    annotate.remove(index)
                    i += 1
                    continue
                if index in comment_out:
                    prep[i] = '#%{}'.format(line)
                    comment_out.remove(index)
                    removed += 1
                elif index in remove:
                    del prep[i]
                    remove.remove(index)
                    removed += 1
                    i -= 1
                # When combining Patch tags and %patchlist, if a Patch is removed, the indexes
                # of %patchlist patches change and %patch macros need to be modified.
                else:
                    tag = self.tag('Patch{}'.format(index))
                    if tag and tag.section_name.startswith('%patchlist'):
                        prep[i] = patch_re.sub(r'%patch{}\2'.format(index - removed), prep[i])
            i += 1

    @saves
    def update_paths_to_sources_and_patches(self) -> None:
        """Fixes paths of patches and sources to make them usable in SPEC file location"""
        rebased_sources_path = os.path.join(constants.RESULTS_DIR, constants.REBASED_SOURCES_DIR)
        for tag_type in ('Patch', 'Source'):
            for tag in self.tags.filter(name='{}*'.format(tag_type)):
                value = self.get_raw_tag_value(tag.name)
                if value and not urllib.parse.urlparse(value).scheme:
                    self.set_raw_tag_value(tag.name, value.replace(rebased_sources_path + os.path.sep, ''))

    @saves
    def write_updated_patches(self, patches: Dict[str, List[str]], disable_inapplicable: bool) -> None:
        """Updates SPEC file according to rebased patches.

        Args:
            patches: Dict of lists of modified, deleted or inapplicable patches.
            disable_inapplicable: Whether to comment out inapplicable patches.
        """
        def is_comment(line):
            if re.match(r'^#(Patch|Source)[0-9]*\s*:(?!//)', line, re.IGNORECASE):
                # ignore commented-out tag
                return False
            return line.startswith('#')

        def is_empty(line):
            return not line or line.isspace()
        if not patches:
            return None
        removed_patches = []
        inapplicable_patches = []
        modified_patches = []
        remove_lines: Dict[int, List[Tuple[int, int]]] = collections.defaultdict(list)
        for tag in self.tags.filter(name='Patch*'):
            section = self.spec_content[tag.section_index]
            if section is None:
                continue
            patch_name = os.path.basename(self.get_raw_tag_value(tag.name) or '')
            if 'deleted' in patches:
                patch_removed = [x for x in patches['deleted'] if patch_name in x]
            else:
                patch_removed = []
            if 'inapplicable' in patches:
                patch_inapplicable = [x for x in patches['inapplicable'] if patch_name in x]
            else:
                patch_inapplicable = []
            if patch_removed:
                # remove the line of the patch that was removed
                self.removed_patches.append(patch_name)
                if tag.index:
                    removed_patches.append(tag.index)
                # find associated comments
                i = tag.line
                if not self.keep_comments:
                    # if the tag is followed by an empty line remove empty lines
                    # in front of the tag to avoid unnecessary blank lines in the spec.
                    blank_follows = i + 1 < len(section) and is_empty(section[i + 1])
                    while i > 0 and (is_comment(section[i - 1]) or blank_follows and is_empty(section[i - 1])):
                        i -= 1
                remove_lines[tag.section_index].append((i, tag.line + 1))
                continue
            if patch_inapplicable:
                if disable_inapplicable:
                    # comment out line if the patch was not applied
                    section[tag.line] = '#' + section[tag.line]
                if tag.index:
                    inapplicable_patches.append(tag.index)
            if 'modified' in patches:
                patch = [x for x in patches['modified'] if patch_name in x]
            else:
                patch = []
            if patch:
                name = os.path.join(constants.RESULTS_DIR, constants.REBASED_SOURCES_DIR, patch_name)
                self.set_raw_tag_value(tag.name, name)
                if tag.index:
                    modified_patches.append(tag.index)
        for section_index, remove in remove_lines.items():
            content = self.spec_content[section_index]
            for span in sorted(remove, key=lambda s: s[0], reverse=True):
                del content[slice(*span)]
        self.process_patch_macros(comment_out=inapplicable_patches if disable_inapplicable else None,
                                  remove=removed_patches, annotate=inapplicable_patches,
                                  note='The following patch contains conflicts')

    ###################################
    # PACKAGE VERSION RELATED METHODS #
    ###################################

    def get_NVR(self) -> str:
        return '{0.name}-{0.version}-{0.release}'.format(self.header)

    def get_version(self) -> str:
        # deprecated, kept for backward compatibility
        return self.header.version

    def get_release(self) -> str:
        """Returns release string without %dist"""
        release = self.header.release
        dist = MacroHelper.expand('%{dist}')
        if dist and release.endswith(dist):
            release = release[:-len(dist)]
        return release

    def parse_release(self) -> Tuple[bool, int, Optional[str]]:
        """Parses release string.

        Returns:
            Tuple of is_prerelease, release_number and extra_version.

        Raises:
            RebaseHelperError in case release string is not valid.

        """
        release = self.get_release()
        m = re.match(r'^(0\.)?(\d+)(?:\.(.+))?$', release)
        if not m:
            raise RebaseHelperError('Invalid release string: {}'.format(release))
        return bool(m.group(1)), int(m.group(2)), m.group(3)

    def set_version(self, version: str, preserve_macros: bool = True) -> None:
        logger.verbose('Updating version in SPEC from %s to %s', self.header.version, version)
        self.set_tag('Version', version, preserve_macros=preserve_macros)

    def set_release(self, release: str, preserve_macros: bool = True) -> None:
        logger.verbose('Changing release to %s', release)
        self.set_tag('Release', '{}%{{?dist}}'.format(release), preserve_macros=preserve_macros)

    def set_release_number(self, release: str) -> None:
        # deprecated, kept for backward compatibility
        self.set_release(release)

    def set_extra_version(self, extra_version: Optional[str], version_changed: bool) -> None:
        """Updates SPEC file with the specified extra version.

        Args:
            extra_version: Extra version string or None.
            version_changed: Whether version (the value of Version tag) changed.

        """
        logger.verbose('Setting extra version in SPEC to %s', extra_version)
        relnum = self.parse_release()[1]
        relnum = 1 if version_changed else relnum + 1
        release = str(relnum)
        if extra_version:
            release += '.' + extra_version
            if re.match(r'^(a(lpha)?|b(eta)?|cr|rc)\d*$', extra_version, re.IGNORECASE):
                release = '0.' + release
        self.set_release(release)
        # TODO: in some cases it might be necessary to modify Source0

    @saves
    def set_tag(self, tag: str, value: str, preserve_macros: bool = False) -> None:
        """Sets value of a tag while trying to preserve macros if requested.

        Note that this method is not intended to be used with non-unique tags, it will only affect the first instance.

        Args:
            tag: Tag name.
            value: Tag value.
            preserve_macros: Whether to attempt to preserve macros in the current tag value.

        """
        macro_def_re = re.compile(
            r'''
            ^
            (?P<cond>%{!?\?\w+:\s*)?          # conditional macro, keep track of the opening brace
            (?(cond)%global|%(global|define)) # only global can be conditional, not define
            \s+
            (?P<name>\w+)                     # macro name
            (?P<options>\(.+?\))?             # optional macro arguments
            \s+
            (?P<value>
                (                             # the value consists of multiple macros and/or other text
                    %(?![{(]) |               # match % but we don't want to consume macros or shell, ignore %( and %{
                    [^%] |                    # other regular text, do not match %, force the line above to match it
                    (%((?P<b>{)|(?P<s>\()))?  # macro or shell, track the parenthesis type
                    [\s\S]+?                  # macro and shell may be multiline, match ASAP using non-greedy matching
                    (?(b)})(?(s)\))           # parenthesis must be closed if it was used
                )+?
            )
            (?(cond)})                        # conditional macros must have closing brace
            $
            ''',
            re.VERBOSE | re.MULTILINE)

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
            """Expands all redefinable macros containing redefinable macros.

            Keeps track of all expanded macros. Returns the expanded string and a set of expanded
            macro names.
            """
            replace = []
            macros = set()
            for macro, span in _find_macros(s):
                value = _get_macro_value(macro)
                if not value:
                    continue
                macros.add(macro)
                rep, new_macros = _expand_macros(value)
                macros |= new_macros
                if _find_macros(rep):
                    replace.append((rep, span))
            for rep, span in reversed(replace):
                s = s[:span[0]] + rep + s[span[1]:]
            return s, macros

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
                        # split text nodes on usual separators
                        result.extend([t for t in re.split(r'(\.|-|_)', node[1]) if t])
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
            _, macros = _expand_macros(s)
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
            value, _ = _expand_macros(curval)
            _sync_macros(curval + newval)
            tokens = _tokenize(value)
            values = [None] * len(tokens)
            sm = SequenceMatcher(a=newval)
            i = 0
            # split newval to match tokens
            for index, token in enumerate(tokens):
                if token[0] == '%':
                    # for macros, try both literal and expanded value
                    for v in [token, MacroHelper.expand(token, token)]:
                        sm.set_seq2(v)
                        m = sm.find_longest_match(i, len(newval), 0, len(v))
                        valid = m.size == len(v)  # only full match is valid
                        if valid:
                            break
                else:
                    sm.set_seq2(token)
                    m = sm.find_longest_match(i, len(newval), 0, len(token))
                    valid = m.size > 0
                if not valid:
                    continue
                if token == sm.b:
                    tokens[index] = token[m.b:m.b+m.size]
                if index > 0:
                    values[index] = newval[m.a:m.a+m.size]
                    if not values[index - 1]:
                        values[index - 1] = newval[i:m.a]
                    else:
                        values[index - 1] += newval[i:m.a]
                else:
                    values[index] = newval[i:m.a+m.size]
                i = m.a + m.size
            if newval[i:] and values:
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

        if preserve_macros:
            value = _process_value(self.get_raw_tag_value(tag) or '', value)
        self.set_raw_tag_value(tag, value)

    @staticmethod
    def extract_version_from_archive_name(archive_path: str, main_source: str) -> str:
        """Extracts version string from source archive name.

        Args:
            archive_path: Path to the main sources archive.
            main_source: Value of Source0 tag.

        Returns:
            Extracted version string.

        Raises:
            RebaseHelperError in case version can't be determined.

        """
        fallback_regex = r'\w*[-_]?v?([.\d]+.*)({0})'.format(
            '|'.join([re.escape(a) for a in Archive.get_supported_archives()]))
        source = os.path.basename(main_source)
        regex = re.sub(r'%({)?version(?(1)})(.*%(\w+|{.+}))?', 'PLACEHOLDER', source, flags=re.IGNORECASE)
        regex = MacroHelper.expand(regex, regex)
        regex = re.escape(regex).replace('PLACEHOLDER', r'(.+)')
        if regex == re.escape(MacroHelper.expand(source, source)):
            # no substitution was made, use the fallback regex
            regex = fallback_regex
        logger.debug('Extracting version from archive name using %s', regex)
        archive_name = os.path.basename(archive_path)
        m = re.match(regex, archive_name)
        if m:
            logger.debug('Extracted version %s', m.group(1))
            return m.group(1)
        if regex != fallback_regex:
            m = re.match(fallback_regex, archive_name)
            if m:
                logger.debug('Extracted version %s', m.group(1))
                return m.group(1)
        raise RebaseHelperError('Unable to extract version from archive name')

    @staticmethod
    def split_version_string(version_string: str, current_version: str) -> Tuple[str, Optional[str]]:
        """Splits version string into version and extra version.

        Args:
            version_string: Complete version string.
            current_version: Current version (the value of Version tag).

        Returns:
            Tuple of version and extra_version.

        Raises:
            RebaseHelperError in case passed version string is not valid.

        """
        version_re = re.compile(r'^(\d+[.\d]*\d+|\d+)(\.|-|_|\+|~)?(\w+)?$')
        m = version_re.match(version_string)
        if not m:
            raise RebaseHelperError('Invalid version string: {}'.format(version_string))
        version, separator, extra = m.groups()
        m = version_re.match(current_version)
        if not m:
            raise RebaseHelperError('Invalid version string: {}'.format(current_version))
        if m.group(3):
            # if current version contains non-numeric characters, the new version should too
            version += (separator or '') + (extra or '')
            extra = None  # type: ignore  # the type is actually Optional[str], but is defined as str in typeshed
        logger.debug('Split version string %s into %s and %s', version_string, version, extra)
        return version, extra

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
            with open(self.path, encoding=constants.ENCODING) as f:
                content = f.read()
        except IOError as e:
            raise RebaseHelperError("Unable to open and read SPEC file '{}'".format(self.path)) from e
        return SpecContent(content)

    def _write_spec_content(self):
        """Writes the current state of SpecContent into a file."""
        logger.verbose("Writing SPEC file '%s' to the disc", self.path)
        try:
            with open(self.path, "w", encoding=constants.ENCODING) as f:
                f.write(str(self.spec_content))
        except IOError as e:
            raise RebaseHelperError("Unable to write updated data to SPEC file '{}'".format(self.path)) from e

    def copy(self, new_path):
        """Creates a copy of the current object and copies the SPEC file
        to a new location.

        Args:
            new_path (str): Path to copy the new SPEC file to.

        Returns:
            SpecFile: The created SpecFile instance.

        """
        shutil.copy(self.path, new_path)
        new_object = SpecFile(new_path, self.sources_location, self.predefined_macros,
                              self.lookaside_cache_preset, self.keep_comments)
        return new_object

    def reload(self):
        """Reloads the whole Spec file."""
        self.update()

    def save(self) -> None:
        """Saves changes made to SpecContent and updates the internal state."""
        self._write_spec_content()
        #  Update internal variables
        self.update()

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

    @saves
    def update_changelog(self, changelog_entry: str) -> None:
        """Inserts a new entry into the changelog and saves the SpecFile.

        Args:
            changelog_entry: Message to use in the entry.

        """
        new_entry = self.get_new_log(changelog_entry)
        changelog = self.spec_content.section('%changelog')
        if changelog is None:
            changelog = []
            self.spec_content.replace_section('%changelog', changelog)
        changelog[0:0] = new_entry

    def get_new_log(self, changelog_entry):
        """Constructs a new changelog entry.

        Args:
            changelog_entry (str): Message to use in the entry.

        Returns:
            list: List of lines of the new entry.

        """
        new_record = []
        today = date.today()
        evr = '{epoch}:{ver}-{rel}'.format(epoch=self.header.epochnum,
                                           ver=self.header.version,
                                           rel=self.get_release())
        evr = evr[2:] if evr.startswith('0:') else evr
        # %changelog entries are always in the C locale
        old_locale = locale.getlocale(locale.LC_TIME)
        try:
            locale.setlocale(locale.LC_TIME, "C")
            day=today.strftime('%a %b %d %Y')
        finally:
            try:
                locale.setlocale(locale.LC_TIME, old_locale)
            except locale.Error:
                # we can't really do anything reasonable here, just keep the C locale
                pass
        new_record.append('* {day} {name} <{email}> - {evr}'.format(day=day,
                                                                    name=GitHelper.get_user(),
                                                                    email=GitHelper.get_email(),
                                                                    evr=evr))
        self.update()
        # FIXME: ugly workaround for mysterious rpm bug causing macros to disappear
        self.update()
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
                    # omit short macros
                    macros = [m for m in macros if len(m['value']) > 1]
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

                    prep[index] = ' '.join(args)

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
