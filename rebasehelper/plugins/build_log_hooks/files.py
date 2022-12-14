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

import collections
import difflib
import fnmatch
import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple, Union, cast

from specfile.macros import MacroLevel
from specfile.sections import Section

from rebasehelper.logger import CustomLogger
from rebasehelper.plugins.build_log_hooks import BaseBuildLogHook
from rebasehelper.types import PackageCategories
from rebasehelper.constants import NEW_BUILD_DIR, ENCODING
from rebasehelper.specfile import SpecFile, MACROS_WHITELIST


logger: CustomLogger = cast(CustomLogger, logging.getLogger(__name__))

AddedFiles = Dict[str, List[str]]
RemovedFromSections = Dict[str, List[str]]
RemainingFiles = List[str]
RemovedFiles = Union[RemainingFiles, RemovedFromSections]


class Files(BaseBuildLogHook):
    CATEGORIES: PackageCategories = []

    # taken from build/files.c in RPM source
    FILES_DIRECTIVES: Dict[str, Optional[str]] = {
        '%artifact': None,
        '%attr': None,
        '%caps': None,
        '%config': None,
        '%defattr': None,
        '%dev': None,
        '%dir': None,
        '%doc': '%{_defaultdocdir}',
        '%docdir': None,
        '%dverify': None,
        '%exclude': None,
        '%ghost': None,
        '%lang': None,
        '%license': '%{_defaultlicensedir}',
        '%missingok': None,
        '%pubkey': None,
        '%readme': None,
        '%verify': None,
    }

    # taken from build/rpmbuild_internal.h in rpm source code
    PROHIBITED_KEYWORDS: List[str] = [
        '%if',
        '%ifarch',
        '%ifnarch',
        '%ifos',
        '%ifnos',
        '%else',
        '%endif',
        '%elif',
        '%elifarch',
        '%elifos',
    ]

    @classmethod
    def format(cls, data):
        output = []
        for file_type, related_files in data.items():
            output.append(' - {}'.format(file_type))
            if isinstance(related_files, list):
                for file in related_files:
                    output.append('\t- {}'.format(file))
            else:
                for section, files in related_files.items():
                    output.append('\t- {}'.format(section))
                    for file in files:
                        output.append('\t\t- {}'.format(file))

        return output

    @classmethod
    def merge_two_results(cls, old, new):
        for file_type, related_files in new.items():
            if file_type not in old:
                old[file_type] = related_files
                continue

            if isinstance(related_files, list):
                old[file_type].extend(related_files)
                continue

            for section, files in related_files.items():
                if section not in old[file_type]:
                    old[file_type][section] = files
                    continue
                old[file_type][section].extend(files)

        return old

    @classmethod
    def _parse_build_log(cls, log_path, nvr):
        """Parses a build log.

        Args:
            log_path (str): Path to the RPM build log.

        Returns:
            tuple: The first element is the type of error that was found
                in the log (missing or deleted). The second element is
                a list of problematic files.

        """
        try:
            with open(log_path, 'r', encoding=ENCODING) as build_log:
                lines = build_log.read().splitlines()
        except IOError:
            logger.error('There was an error opening %s', log_path)
            return None, None

        error_type = None
        # Use set to avoid duplicate files.
        files = set()

        # Two types of error can occur. The file is either in the SPEC file but missing in sources
        # or the other way around. Example lines of the first case:
        # File not found: /root/rpmbuild/BUILDROOT/pello-0.1.1-1.fc27.x86_64/should/not/be/here
        # File not found: /root/rpmbuild/BUILDROOT/pello-0.1.1-1.fc27.x86_64/should/not/be/here2
        # Example lines of the second case:
        # Installed (but unpackaged) file(s) found:
        #   /usr/bin/pello
        error_re = re.compile(
            r'''
            ^
            (BUILDSTDERR:)?
            \s*
            (
                (?P<missing>File\s+not\s+found:\s*)|
                (?P<unpackaged>Installed\s+\(but\s+unpackaged\)\s+file\(s\)\s+found:)
            )?
            (/.*/{}\.\w+)?
            (?P<path>/.*)?
            $
            '''.format(re.escape(nvr)), re.VERBOSE
        )

        for line in lines:
            match = error_re.match(line)
            if match:
                if match.group('missing'):
                    error_type = 'deleted'
                    files.add(match.group('path'))
                elif match.group('unpackaged'):
                    error_type = 'missing'
                elif error_type == 'missing' and match.group('path'):
                    # Ignore debug information
                    if not match.group('path').startswith('/usr/lib/debug'):
                        files.add(match.group('path'))
                elif error_type and not match.group('path'):
                    break

        return error_type, list(files)

    @classmethod
    def _get_best_matching_files_section(cls, rebase_spec_file, file):
        """Finds a %files section with a file that has the closest match with
        the specified file. If the best match cannot be determined, the main
        %files section is returned. If no main section is found, return the
        first %files section if possible, None otherwise.

        Args:
            rebase_spec_file (specfile.SpecFile): Rebased SpecFile object.
            file (str): Path to the file to be classified.

        Returns:
            str: Name of the section containing the closest matching file.
                None if no %files section can be found.

        """
        best_match = ''
        best_match_section = ''
        files = []
        for section in rebase_spec_file.spec.sections().content: # pylint: disable=no-member
            if section.normalized_id.startswith('files'):
                files.append(section.id)
                for line in section:
                    new_best_match = difflib.get_close_matches(file, [best_match, rebase_spec_file.spec.expand(line)])
                    if new_best_match:
                        # the new match is a closer match
                        if new_best_match[0] != best_match:
                            best_match = str(new_best_match[0])
                            best_match_section = section.id

        return best_match_section or rebase_spec_file.get_main_files_section() or (files[0] if files else None)

    @classmethod
    def _sanitize_path(cls, path):
        """Changes the path to follow Fedora Packaging Guidelines."""
        if path.startswith('%{_mandir}'):
            # substitute compression extension with *
            directory, name = os.path.split(path)
            name = '{0}.{1}*'.format(*name.split('.')[:2])
            path = os.path.join(directory, name)
        return path

    @classmethod
    def _correct_missing_files(cls, rebase_spec_file, files):
        """Adds files found in buildroot which are missing in %files
        sections in the SPEC file. Each file is added to a %files section
        with the closest matching path.

        """
        result: Dict[str, AddedFiles] = collections.defaultdict(lambda: collections.defaultdict(list))
        for file in files:
            section_name = cls._get_best_matching_files_section(rebase_spec_file, file)
            if section_name is None:
                logger.error('The specfile does not contain any %files section, cannot add the missing files')
                break
            substituted_path = cls._sanitize_path(
                rebase_spec_file.substitute_path_with_macros(
                    file,
                    lambda m: m.level == MacroLevel.SPEC
                    and m.name == "name"
                    or m.name in MACROS_WHITELIST,
                )
            )
            with rebase_spec_file.spec.sections() as sections:
                section = getattr(sections, section_name)
                try:
                    index = [i for i, l in enumerate(section) if l][-1] + 1
                except IndexError:
                    # section is empty
                    index = 0
                section.insert(index, substituted_path)
            result['added']['%' + section_name].append(substituted_path)
            logger.info("Added %s to '%s' section", substituted_path, '%' + section_name)

        return result

    @classmethod
    def _get_line_directives(cls, split_line) -> Tuple[List[str], Optional[str]]:
        """Gathers directives present in the line.

        Args:
            split_line: Line split at whitespaces. Each element must either be
                a directive or a file path.

        Returns:
            A tuple of 2 elements. The first is a list of used directives.
            The second is a directive which influences the subsequent paths
            (e. g. %doc). Will be None if no such directive is present.
        """
        directives: List[str] = []
        prepended_directive = None
        for element in reversed(split_line):
            if element in cls.FILES_DIRECTIVES:
                if cls.FILES_DIRECTIVES[element]:
                    prepended_directive = element
                directives.insert(0, element)
                split_line.remove(element)
        return directives, prepended_directive

    @classmethod
    def _correct_one_section(
        cls,
        spec: SpecFile,
        subpackage: str,
        sec_name: str,
        sec_content: Section,
        files: List[str],
        result: Dict[str, RemovedFromSections],
    ) -> None:
        """Removes deleted files from one %files section.

        Args:
            spec: SPEC file to remove the files from.
            subpackage: Name of the subpackage which the section relates to.
            sec_name: Name of the %files section
            sec_content: Content of the %files section
            files: Files that still need to be removed
            result: Dict summarizing the changes done to the SPEC file.

        """
        i = 0
        while i < len(sec_content):
            original_line = sec_content[i].split()
            # Expand the whole line to check for occurrences of special
            # keywords, such as %global and %if blocks. Macro definitions
            # expand to empty string.
            expanded = spec.spec.expand(sec_content[i])
            if not original_line or not expanded or any(k in expanded for k in cls.PROHIBITED_KEYWORDS):
                i += 1
                continue
            split_line = original_line[:]
            # Keep track of files which could possibly be renamed but not
            # detected by the hook. %doc and %license files are the 2 examples
            # of this. If %doc README is renamed to README.md, the hook will
            # simply remove it but README.md won't be added (it is installed
            # by the directive). We want to warn the user about this.
            possible_rename = [False for _ in split_line]
            directives, prepended_directive = cls._get_line_directives(split_line)
            # Determine absolute paths
            if prepended_directive:
                for j, path in enumerate(split_line):
                    if not os.path.isabs(path):
                        prepend_macro = cls.FILES_DIRECTIVES[prepended_directive] or ''
                        split_line[j] = os.path.join(prepend_macro, subpackage, os.path.basename(path))
                        possible_rename[j] = True
            split_line = [spec.spec.expand(p) for p in split_line]

            j = 0
            while j < len(split_line) and files:
                file = split_line[j]
                warn_about_rename = possible_rename[j]
                for deleted_file in reversed(files):
                    if not fnmatch.fnmatch(deleted_file, file):
                        continue

                    original_file = original_line[len(directives) + j]

                    del possible_rename[j]
                    del split_line[j]
                    del original_line[len(directives) + j]
                    files.remove(deleted_file)
                    result['removed']['%' + sec_name].append(original_file)
                    logger.info("Removed %s from '%s' section", original_file, '%' + sec_name)
                    if warn_about_rename:
                        logger.warning("The installation of %s was handled by %s directive and the file has now been "
                                       "removed. The file may have been renamed and rebase-helper cannot automatically "
                                       "detect it. A common example of this is renaming README to README.md. It might "
                                       "be necessary to re-add such renamed file to the rebased SPEC file manually.",
                                       original_file, prepended_directive)
                    break
                else:
                    j += 1

            if not split_line:
                del sec_content[i]
            else:
                sec_content[i] = ' '.join(original_line)
                i += 1

    @classmethod
    def _correct_deleted_files(cls, rebase_spec_file: SpecFile, files: List[str]) -> Dict[str, RemovedFiles]:
        """Removes files newly missing in buildroot from %files sections
        of the SPEC file. If a file cannot be removed, the user is informed
        and it is mentioned in the final report.

        Args:
            rebase_spec_file: SPEC file to remove the files from.
            files: List of files to remove.

        Returns:
            Dict summarizing the changes done to the SPEC file.

        """
        result: Dict[str, RemovedFromSections] = collections.defaultdict(lambda: collections.defaultdict(list))
        with rebase_spec_file.spec.sections() as sections:
            for section in sections:
                if section.normalized_id.startswith('files'):
                    subpackage = rebase_spec_file.get_subpackage_name(section.id)
                    cls._correct_one_section(rebase_spec_file, subpackage, section.id, section, files, result)
                    if not files:
                        # Nothing more to be done
                        return cast(Dict[str, RemovedFiles], result)

        result_with_irremovable: Dict[str, RemovedFiles] = cast(Dict[str, RemovedFiles], result)
        logger.info('Could not remove the following files:')
        for file in files:
            logger.info('\t%s', file)

        result_with_irremovable['unable_to_remove'] = files
        return result_with_irremovable

    @classmethod
    def run(cls, spec_file: SpecFile, rebase_spec_file: SpecFile, results_dir: str,
            **kwargs: Any) -> Tuple[Dict[str, Union[RemovedFiles, AddedFiles]], bool]:
        if not results_dir:
            return {}, False
        log = os.path.join(results_dir, NEW_BUILD_DIR, 'RPM', 'build.log')

        nvr = rebase_spec_file.get_NVR()
        error_type, files = cls._parse_build_log(log, nvr)

        result: Dict[str, Union[AddedFiles, RemovedFiles]] = {}
        if error_type == 'deleted':
            logger.info('The following files are absent in sources but are in the SPEC file, trying to remove them:')
            for file in files:
                logger.info('\t%s', file)
            result = cls._correct_deleted_files(rebase_spec_file, files)
        elif error_type == 'missing':
            logger.info('The following files are in the sources but are missing in the SPEC file, trying to add them:')
            for file in files:
                logger.info('\t%s', file)
            result = cls._correct_missing_files(rebase_spec_file, files)
        rebase_spec_file.save()
        return result, 'added' in result or 'removed' in result
