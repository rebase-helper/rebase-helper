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
import logging
import os
import re
import shlex
import shutil
from typing import Callable, List, Optional, Pattern, Tuple, Dict, cast

from specfile import Specfile
from specfile.exceptions import RPMException
from specfile.macros import MacroLevel
from specfile.sections import Section
from specfile.sources import Source, ListSource, TagSource

from rebasehelper import constants
from rebasehelper.archive import Archive
from rebasehelper.exceptions import RebaseHelperError, DownloadError, ParseError, LookasideCacheError
from rebasehelper.argument_parser import SilentArgumentParser
from rebasehelper.logger import CustomLogger
from rebasehelper.helpers.download_helper import DownloadHelper
from rebasehelper.helpers.git_helper import GitHelper
from rebasehelper.helpers.lookaside_cache_helper import LookasideCacheHelper
from rebasehelper.helpers.rpm_helper import RpmHeader


MACROS_WHITELIST: List[str] = [
    '_bindir',
    '_datadir',
    '_includedir',
    '_infodir',
    '_initdir',
    '_libdir',
    '_libexecdir',
    '_localstatedir',
    '_mandir',
    '_sbindir',
    '_sharedstatedir',
    '_sysconfdir',
    'python2_sitelib',
    'python3_sitelib',
]


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


class PatchObject:

    """Class represents set of information about patches"""

    def __init__(self, path, number, strip):
        self.path = path
        self.number = number
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
    """Class representing a spec file."""

    def __init__(self, path: str, sources_location: str = '', predefined_macros: Optional[Dict[str, str]] = None,
                 lookaside_cache_preset: str = 'fedpkg'):
        # Initialize attributes
        self.lookaside_cache_preset: str = lookaside_cache_preset
        self.prep_section: str = ''
        self.all_sources: List[Source] = []
        self.sources: List[Source] = []
        self.patches: Dict[str, List[PatchObject]] = {}
        self.removed_patches: List[str] = []
        self.category: Optional[PackageCategory] = None
        self.spec = Specfile(path, sources_location, macros=list((predefined_macros or {}).items()))
        self._update_data()

    def download_remote_sources(self) -> None:
        """Downloads sources specified as URL."""
        try:
            # try to download old sources from Fedora lookaside cache
            LookasideCacheHelper.download(self.lookaside_cache_preset,
                                          os.path.dirname(self.spec.path),
                                          self.spec.expanded_name,
                                          str(self.spec.sourcedir))
        except LookasideCacheError as e:
            logger.verbose("Downloading sources from lookaside cache failed. "
                           "Reason: %s.", str(e))

        for source in self.all_sources:
            if not source.remote:
                continue
            if not source.expanded_filename:
                continue
            logger.verbose("Source '%s' is remote, downloading it.", source.expanded_filename)
            target = self.spec.sourcedir / source.expanded_filename
            if not target.is_file():
                logger.verbose("File '%s' doesn't exist locally, downloading it.", str(target))
                try:
                    DownloadHelper.download_file(source.expanded_location, target)
                except DownloadError as e:
                    raise RebaseHelperError("Failed to download file from URL {}. "
                                            "Reason: '{}'. ".format(source.expanded_location, str(e))) from e

    def update(self) -> None:
        self.spec.reload()
        self._update_data()

    def _update_data(self):
        """
        Function updates data from given SPEC file

        :return:
        """
        def guess_category():
            for pkg in self.spec.rpm_spec.packages:
                header = RpmHeader(pkg.header)
                for category in PackageCategory:
                    if category.value.match(header.name):
                        return category
                    for provide in header.providename:
                        if category.value.match(provide):
                            return category
            return None
        self.category = guess_category()
        self.prep_section = self.spec.rpm_spec.prep
        self.main_source_number = self._identify_main_source(self.spec)
        self.all_sources = [
            s
            for s in self.spec.sources().content + self.spec.patches().content # pylint: disable=no-member
            if s.expanded_location is not None
        ]
        self.sources = [
            s
            for s in self.spec.sources().content # pylint: disable=no-member
            if s.expanded_location is not None
        ]
        self.patches = self._get_initial_patches()

    ###########################
    # SOURCES RELATED METHODS #
    ###########################

    @staticmethod
    def _identify_main_source(spec: Specfile) -> Optional[int]:
        # the lowest number is the main source
        return min((s.number for s in spec.sources().content), default=None) # pylint: disable=no-member

    def _get_raw_source_string(self, source_num: Optional[int]) -> Optional[str]:
        source = next((s for s in self.spec.sources().content if s.number == source_num), None) # pylint: disable=no-member
        if not source:
            return None
        return source.location

    def _get_source_filename(self, source_num: Optional[int]) -> Optional[str]:
        source = next((s for s in self.spec.sources().content if s.number == source_num), None) # pylint: disable=no-member
        if not source:
            return None
        return source.expanded_filename

    def get_raw_main_source(self) -> str:
        return self._get_raw_source_string(self.main_source_number) or ''

    def get_main_source(self) -> str:
        return self._get_source_filename(self.main_source_number) or ''

    def get_other_sources(self) -> List[str]:
        result = sorted((
            s
            for s in self.spec.sources().content # pylint: disable=no-member
            if s.number != self.main_source_number
        ), key=lambda s: s.number)
        return [s.expanded_filename for s in result]

    def get_sources(self) -> List[str]:
        result = sorted((
            s
            for s in self.spec.sources().content # pylint: disable=no-member
        ), key=lambda s: s.number)
        return [str(self.spec.sourcedir / s.expanded_filename) for s in result]

    ###########################
    # PATCHES RELATED METHODS #
    ###########################

    def _get_initial_patches(self) -> Dict[str, List[PatchObject]]:
        """Returns a dict of patches from a spec file"""
        patches_applied = []
        patches_not_used = []
        strip_options = self._get_patch_strip_options()
        for patch in self.spec.patches().content: # pylint: disable=no-member
            if not patch.expanded_filename:
                continue
            patch_path = self.spec.sourcedir / (
                patch.expanded_filename
                if patch.remote
                else patch.expanded_location
            )
            if not patch_path.exists():
                if patch.remote:
                    logger.info('Patch%s is remote, trying to download it', patch.number)
                    try:
                        DownloadHelper.download_file(patch.expanded_location, patch_path)
                    except DownloadError:
                        logger.error('Could not download remote patch %s', patch.expanded_location)
                        continue
                else:
                    logger.error('Patch %s does not exist', patch.expanded_filename)
                    continue
            if patch.number in strip_options:
                patches_applied.append(PatchObject(str(patch_path), patch.number, strip_options[patch.number]))
            else:
                patches_not_used.append(PatchObject(str(patch_path), patch.number, None))
        patches_applied = sorted(patches_applied, key=lambda x: x.number)
        return {"applied": patches_applied, "not_applied": patches_not_used}

    def _get_patch_strip_options(self) -> Dict[int, int]:
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
            numbers = [
                p.number
                for p in self.spec.patches().content # pylint: disable=no-member
                if p.expanded_filename in rest
            ]
            for num in numbers:
                if num not in result or result[num] < ns.p:
                    result[num] = ns.p
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

        with self.spec.sections() as sections:
            if not 'prep' in sections:
                return
            prep = sections.prep

            patch_re = re.compile(r'^%patch(?P<number>\d+)(.*)')

            i = 0
            removed = 0
            while i < len(prep):
                line = prep[i]
                match = patch_re.match(line)
                if match:
                    number = int(match.group('number'))
                    if note and number in annotate and number not in remove:
                        prep.insert(i, '# {}'.format(note))
                        annotate.remove(number)
                        i += 1
                        continue
                    if number in comment_out:
                        prep[i] = '#%{}'.format(line)
                        comment_out.remove(number)
                        removed += 1
                    elif number in remove:
                        del prep[i]
                        remove.remove(number)
                        removed += 1
                        i -= 1
                    # When combining Patch tags and %patchlist, if a Patch is removed, the numbers
                    # of %patchlist patches change and %patch macros need to be modified.
                    elif number in [
                        p.number
                        for p in self.spec.patches().content # pylint: disable=no-member
                        if isinstance(p, ListSource)
                    ]:
                        prep[i] = patch_re.sub(r'%patch{}\2'.format(number - removed), prep[i])
                i += 1

    @saves
    def update_paths_to_sources_and_patches(self) -> None:
        """Fixes paths of patches and sources to make them usable in SPEC file location"""
        rebased_sources_path = os.path.join(constants.RESULTS_DIR, constants.REBASED_SOURCES_DIR)
        with self.spec.sources() as sources:
            for source in sources:
                if not source.remote:
                    source.location = source.location.replace(rebased_sources_path + os.path.sep, '')
        with self.spec.patches() as patches:
            for patch in patches:
                if not patch.remote:
                    patch.location = patch.location.replace(rebased_sources_path + os.path.sep, '')

    @saves
    def write_updated_patches(self, patches_dict: Dict[str, List[str]], disable_inapplicable: bool) -> None:
        """Updates SPEC file according to rebased patches.

        Args:
            patches: Dict of lists of modified, deleted or inapplicable patches.
            disable_inapplicable: Whether to comment out inapplicable patches.
        """
        if not patches_dict:
            return None
        removed_patches = []
        inapplicable_patches = []
        modified_patches = []
        for patch in self.spec.patches().content: # pylint: disable=no-member
            if 'deleted' in patches_dict:
                patch_removed = [x for x in patches_dict['deleted'] if patch.expanded_filename in x]
            else:
                patch_removed = []
            if 'inapplicable' in patches_dict:
                patch_inapplicable = [x for x in patches_dict['inapplicable'] if patch.expanded_filename in x]
            else:
                patch_inapplicable = []
            if patch_removed:
                self.removed_patches.append(patch.expanded_filename)
                removed_patches.append(patch.number)
                continue
            if patch_inapplicable:
                inapplicable_patches.append(patch.number)
            if 'modified' in patches_dict:
                patch_modified = [x for x in patches_dict['modified'] if patch.expanded_filename in x]
            else:
                patch_modified = []
            if patch_modified:
                patch.location = os.path.join(constants.RESULTS_DIR,
                                              constants.REBASED_SOURCES_DIR,
                                              patch.expanded_filename)
                modified_patches.append(patch.number)
        self.process_patch_macros(comment_out=inapplicable_patches if disable_inapplicable else None,
                                  remove=removed_patches, annotate=inapplicable_patches,
                                  note='The following patch contains conflicts')
        with self.spec.patches() as patches:
            for number in removed_patches:
                patches.remove_numbered(number)
            if disable_inapplicable:
                for number in inapplicable_patches:
                    patch = next(p for p in patches if p.number == number)
                    # comment out line if the patch was not applied
                    # XXX: this is rather hackish
                    if isinstance(patch, TagSource):
                        patch._tag.name = '#' + patch._tag.name # pylint: disable=protected-access
                    else:
                        patch._source.location = '#' + patch._source.location # pylint: disable=protected-access

    ###################################
    # PACKAGE VERSION RELATED METHODS #
    ###################################

    def get_NVR(self) -> str:
        # there seems to be a bug in astroid 2.12.13 inference
        # pylint: disable=not-callable
        return self.spec.expand('%{name}-%{version}-%{release}')

    def get_release(self) -> str:
        """Returns release string without %dist"""
        return self.spec.expanded_release

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
        # there seems to be a bug in astroid 2.12.13 inference
        # pylint: disable=not-callable
        logger.verbose('Updating version in SPEC from %s to %s', self.spec.expand('%{version}'), version)
        if preserve_macros:
            self.spec.update_tag('Version', version)
        else:
            self.spec.version = version
        self.spec.save()

    def set_release(self, release: str, preserve_macros: bool = True) -> None:
        logger.verbose('Changing release to %s', release)
        if preserve_macros:
            self.spec.update_tag('Release', '{}%{{?dist}}'.format(release))
        else:
            self.spec.release = release
        self.spec.save()

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

    def extract_version_from_archive_name(self, archive_path: str, main_source: str) -> str:
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
        regex = self.expand(regex, regex)
        regex = re.escape(regex).replace('PLACEHOLDER', r'(.+)')
        if regex == re.escape(self.expand(source, source)):
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
        return next(
            (
                s.id
                for s in self.spec.sections().content # pylint: disable=no-member
                if s.normalized_id.startswith("files")
                and self.get_subpackage_name(s.id) == "%{name}"
            ),
            None,
        )

    #############################################
    # SPEC CONTENT MANIPULATION RELATED METHODS #
    #############################################

    def copy(self, new_path):
        """Creates a copy of the current object and copies the SPEC file
        to a new location.

        Args:
            new_path (str): Path to copy the new SPEC file to.

        Returns:
            SpecFile: The created SpecFile instance.

        """
        shutil.copy(self.spec.path, new_path)
        new_object = SpecFile(new_path, self.spec.sourcedir, self.spec.macros,
                              self.lookaside_cache_preset)
        return new_object

    def reload(self):
        """Reloads the whole Spec file."""
        self.update()

    def save(self) -> None:
        """Saves changes made to SpecContent and updates the internal state."""
        self.spec.save()
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
        sections = self.spec.sections().content # pylint: disable=no-member
        if 'check' not in sections:
            return False
        # Remove commented lines
        check_section = [x.strip() for x in sections.check if not x.strip().startswith('#')]
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
        # there seems to be a bug in astroid 2.12.13 inference
        # pylint: disable=not-callable
        with self.spec.sections() as sections:
            if 'changelog' not in sections:
                sections.append(Section('changelog'))
        self.spec.add_changelog_entry(
            self.spec.expand(changelog_entry),
            author=GitHelper.get_user(),
            email=GitHelper.get_email(),
        )

    def get_setup_dirname(self):
        """
        Get dirname from %setup or %autosetup macro arguments

        :return: dirname
        """
        for macro in self.spec.prep().content.macros: # pylint: disable=no-member
            if not macro.name.endswith('setup'):
                continue
            if not macro.options.T or macro.options.a == 0 or macro.options.b == 0:
                return macro.options.n
        return None

    @saves
    def update_setup_dirname(self, dirname):
        """
        Update %setup or %autosetup dirname argument if needed

        :param dirname: new dirname to be used
        """
        # there seems to be a bug in astroid 2.12.13 inference
        # pylint: disable=not-callable
        with self.spec.prep() as prep:
            for macro in prep.macros:
                if not macro.name.endswith('setup'):
                    continue
                # check if this macro instance is extracting Source0
                if macro.options.T and macro.options.a != 0 and macro.options.b != 0:
                    continue
                # check if modification is really necessary
                if dirname != self.spec.expand(macro.options.n):
                    macro.options.n = self.substitute_path_with_macros(
                        dirname,
                        lambda m: not m.options
                            and len(m.body) > 1
                            and (
                                m.level == MacroLevel.SPEC
                                and m.name in ("name", "version")
                                or m.level == MacroLevel.GLOBAL
                            ),
                    )

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
        builddir = self.expand('%{_builddir}', '')
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
                    elif cmd == 'rpmuncompress':
                        parser = None
                        target = '.'
                    else:
                        continue
                    if parser:
                        try:
                            ns, _ = parser.parse_known_args(args)
                        except ParseError:
                            continue
                        else:
                            target = ns.target
                    basedir = os.path.relpath(basedir, builddir)
                    return os.path.normpath(os.path.join(basedir, target))
        return None

    def expand(self, s: str, default: str = '') -> str:
        try:
            # there seems to be a bug in astroid 2.12.13 inference
            # pylint: disable=not-callable
            return self.spec.expand(s)
        except RPMException:
            return default

    def substitute_path_with_macros(self, path: str, condition: Optional[Callable] = None):
        """Substitutes parts of a path with macros.

        Args:
            path: Path to be changed.
            condition: Condition determining if that particular active macro
              is a suitable substitution.

        Returns:
            Path expressed using macros.
        """
        # there seems to be a bug in astroid 2.12.13 inference
        # pylint: disable=not-callable
        if condition is None:
            condition = lambda m: m.name in MACROS_WHITELIST
        macros = [m for m in self.spec.get_active_macros() if condition(m)]
        for macro in macros:
            macro.body = self.spec.expand(macro.body)
        # ensure maximal greediness
        macros.sort(key=lambda m: len(m.body), reverse=True)
        for macro in macros:
            if macro.body and macro.body in path:
                path = path.replace(macro.body, '%{{{}}}'.format(macro.name))
        return path

    @classmethod
    def get_comment_span(cls, line: str, script_section: bool) -> Tuple[int, int]:
        """Gets span of a comment depending on the section.

        Args:
            line: Line to find the comment in.
            script_section: Whether the section the line is in is a shell script.

        Returns:
            Span of the comment. If no comment is found, both tuple elements
            are equal to the length of the line for convenient use in a slice.

        """
        comment = re.search(r" #.*" if script_section else r"^\s*#.*", line)
        return comment.span() if comment else (len(line), len(line))
