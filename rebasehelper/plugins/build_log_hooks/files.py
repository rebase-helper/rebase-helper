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
import os
import re

from typing import Dict, List, Optional

from rebasehelper.plugins.build_log_hooks import BaseBuildLogHook
from rebasehelper.types import PackageCategories
from rebasehelper.helpers.macro_helper import MacroHelper
from rebasehelper.logger import logger


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

    PROHIBITED_KEYWORDS: List[str] = [
        '%if',
        '%else',
        '%endif',
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
            with open(log_path, 'r') as build_log:
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
        for sec_name, sec_content in rebase_spec_file.spec_content.sections:
            if sec_name.startswith('%files'):
                files.append(sec_name)
                for line in sec_content:
                    new_best_match = difflib.get_close_matches(file, [best_match, MacroHelper.expand(line)])
                    if new_best_match:
                        # the new match is a closer match
                        if new_best_match[0] != best_match:
                            best_match = new_best_match[0]
                            best_match_section = sec_name

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
        macros = [m for m in rebase_spec_file.macros if m['name'] in MacroHelper.MACROS_WHITELIST]
        macros = MacroHelper.expand_macros(macros)
        # ensure maximal greediness
        macros.sort(key=lambda k: len(k['value']), reverse=True)

        result = collections.defaultdict(lambda: collections.defaultdict(list))
        for file in files:
            section = cls._get_best_matching_files_section(rebase_spec_file, file)
            if section is None:
                logger.error('The specfile does not contain any %files section, cannot add the missing files')
                break
            substituted_path = cls._sanitize_path(MacroHelper.substitute_path_with_macros(file, macros))
            try:
                index = [i for i, l in enumerate(rebase_spec_file.spec_content.section(section)) if l][-1] + 1
            except IndexError:
                # section is empty
                index = 0
            rebase_spec_file.spec_content.section(section).insert(index, substituted_path)
            result['added'][section].append(substituted_path)
            logger.info("Added %s to '%s' section", substituted_path, section)

        return result

    @classmethod
    def _correct_deleted_files(cls, rebase_spec_file, files):
        """Removes files newly missing in buildroot from %files sections
        of the SPEC file. If a file cannot be removed, the user is informed
        and it is mentioned in the final report.

        """
        result = collections.defaultdict(lambda: collections.defaultdict(list))
        for sec_name, sec_content in rebase_spec_file.spec_content.sections:
            if sec_name.startswith('%files'):
                subpackage = rebase_spec_file.get_subpackage_name(sec_name)
                i = 0
                while i < len(sec_content):
                    original_line = sec_content[i].split()
                    # Expand the whole line to check for occurrences of
                    # special keywords, such as %global and %if blocks.
                    # Macro definitions expand to empty string.
                    expanded = MacroHelper.expand(sec_content[i])
                    if not original_line or not expanded or any(k in expanded for k in cls.PROHIBITED_KEYWORDS):
                        i += 1
                        continue
                    split_line = original_line[:]
                    directives = []
                    prepend_macro = None
                    for element in reversed(split_line):
                        if element in cls.FILES_DIRECTIVES:
                            if cls.FILES_DIRECTIVES[element]:
                                prepend_macro = cls.FILES_DIRECTIVES[element]
                            directives.insert(0, element)
                            split_line.remove(element)

                    if prepend_macro:
                        for j, path in enumerate(split_line):
                            if not os.path.isabs(path):
                                split_line[j] = os.path.join(prepend_macro, subpackage, os.path.basename(path))
                    split_line = [MacroHelper.expand(p) for p in split_line]

                    j = 0
                    while j < len(split_line) and files:
                        file = split_line[j]
                        for deleted_file in reversed(files):
                            if not fnmatch.fnmatch(deleted_file, file):
                                continue

                            original_file = original_line[len(directives) + j]

                            del split_line[j]
                            del original_line[len(directives) + j]
                            files.remove(deleted_file)
                            result['removed'][sec_name].append(original_file)
                            logger.info("Removed %s from '%s' section", original_file, sec_name)
                            break
                        else:
                            j += 1

                    if not split_line:
                        del sec_content[i]
                    else:
                        sec_content[i] = ' '.join(original_line)
                        i += 1

                    if not files:
                        return result

        logger.info('Could not remove the following files:')
        for file in files:
            logger.info('\t%s', file)

        result['unable_to_remove'] = files
        return result

    @classmethod
    def run(cls, spec_file, rebase_spec_file, results_dir, **kwargs):
        if not results_dir:
            return {}, False
        log = os.path.join(results_dir, 'new-build', 'RPM', 'build.log')

        nvr = rebase_spec_file.get_NVR()
        error_type, files = cls._parse_build_log(log, nvr)

        result = {}
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
