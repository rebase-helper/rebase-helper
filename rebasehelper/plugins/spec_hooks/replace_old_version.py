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
import re
import urllib.parse
from typing import Any, Dict, List, Pattern, Tuple, Set

from rebasehelper.types import Options
from rebasehelper.plugins.spec_hooks import BaseSpecHook
from rebasehelper.specfile import SpecFile
from rebasehelper.helpers.macro_helper import MacroHelper


class ReplaceOldVersion(BaseSpecHook):
    """SpecHook for replacing occurrences of old version string."""

    OPTIONS: Options = [
        {
            "name": ["--replace-old-version-with-macro"],
            "default": False,
            "switch": True,
            "help": "replace old version string with %%{version} instead of new version string",
        },
    ]

    # taken from lib/rpmte.c in RPM source
    IGNORED_TAGS = [
        # dependency tags could be specified with a version equal to the old version
        # which could break the functionality, ignore them
        'Conflicts',
        'Enhances',
        'Obsoletes',
        'Provides',
        'Recommends',
        'Requires',
        'Suggests',
        # ignore Version tag to avoid mistakes when version format changes
        # e.g. in a rebase from 2.5 to 2.5.1, version would be changed to 2.5.1.1
        'Version',
    ]

    @classmethod
    def _create_possible_replacements(cls, old: str, new: str, use_macro: bool) -> List[Tuple[Pattern[str], str]]:
        """Creates possible subversion replacements.

        Args:
            old: Old version.
            new: New Version.
            use_macro: Whether %{version} macro should be used as a replacement.

        Returns:
            List of tuples containing regex pattern and replacement
            that can be passed to re.sub. The first tuple always
            represents the whole version.

        Example:
            Subversions 1.2, 1.2.3, 1.2.3.4 would be created from version 1.2.3.4.

        """
        version_re = r'([\ /\-\s]){}([/.\-\s]|$)'
        replacement = r'\g<1>{}\g<2>'
        split_version = old.split('.')

        res = [
            (re.compile(version_re.format(re.escape(old))), replacement.format('%{version}' if use_macro else new))
        ]
        # iterate backwards to go from longer to shorter subversions
        for i in reversed(range(2, len(split_version))):
            pattern = re.compile(version_re.format(re.escape('.'.join(split_version[:i]))))
            new_subversion = replacement.format('.'.join(new.split('.')[:i]))
            res.append((pattern, new_subversion))
        return res

    @classmethod
    def run(cls, spec_file: SpecFile, rebase_spec_file: SpecFile, **kwargs: Any):
        old_version = spec_file.header.version
        new_version = rebase_spec_file.header.version
        replace_with_macro = bool(kwargs.get('replace_old_version_with_macro'))

        subversion_patterns = cls._create_possible_replacements(old_version, new_version, replace_with_macro)
        examined_lines: Dict[str, Set[int]] = collections.defaultdict(set)
        for tag in rebase_spec_file.tags.filter():
            examined_lines[tag.section].add(tag.line)
            value = rebase_spec_file.get_raw_tag_value(tag.name, tag.section)
            if not value or tag.name in cls.IGNORED_TAGS:
                continue
            scheme = urllib.parse.urlparse(value).scheme
            if (tag.name.startswith('Patch') or tag.name.startswith('Source')) and not scheme:
                # skip local sources
                continue

            # replace the whole version first
            updated_value = subversion_patterns[0][0].sub(subversion_patterns[0][1], value)
            # replace subversions only for remote sources/patches
            if tag.name.startswith('Patch') or tag.name.startswith('Source'):
                for sub_pattern, repl in subversion_patterns[1:]:
                    updated_value = sub_pattern.sub(repl, updated_value)
            rebase_spec_file.set_raw_tag_value(tag.name, updated_value, tag.section)

        for sec_name, section in rebase_spec_file.spec_content.sections:
            if sec_name.startswith('%changelog'):
                continue
            for index, line in enumerate(section):
                tag_ignored = any(MacroHelper.expand(line, line).startswith(tag) for tag in cls.IGNORED_TAGS)
                if index in examined_lines[sec_name] or tag_ignored:
                    continue
                start, end = spec_file.spec_content.get_comment_span(line, sec_name)
                updated_line = subversion_patterns[0][0].sub(subversion_patterns[0][1], line[:start])
                section[index] = updated_line + line[start:end]

        rebase_spec_file.save()
