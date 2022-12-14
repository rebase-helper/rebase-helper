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

import re
from typing import Any, List, Pattern, Tuple

from specfile.sources import TagSource

from rebasehelper.exceptions import RebaseHelperError
from rebasehelper.types import Options
from rebasehelper.plugins.spec_hooks import BaseSpecHook
from rebasehelper.specfile import SpecFile


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
    def _create_possible_replacements(cls, spec_file: SpecFile, rebase_spec_file: SpecFile,
                                      use_macro: bool) -> List[Tuple[Pattern[str], str]]:
        """Creates possible subversion replacements.

        Args:
            spec_file: Old SpecFile.
            rebase_spec_file: New SpecFile.
            use_macro: Whether %{version} macro should be used as a replacement.

        Returns:
            List of tuples containing regex pattern and replacement
            that can be passed to re.sub. The first tuple always
            represents the whole version.

        Example:
            Subversions 1.2, 1.2.3, 1.2.3.4 would be created from version 1.2.3.4.

        """
        old = spec_file.spec.expanded_version
        new = rebase_spec_file.spec.expanded_version
        version_re = r'([\ /\-\s]){}([/.\-\s]|$)'
        # Allow any character after whole version to replace strings such as
        # 1.0.1bc1
        full_version_re = r'([\ /\-\s]){}(.*)'
        replacement = r'\g<1>{}\g<2>'
        split_version = old.split('.')

        res = [
            (re.compile(full_version_re.format(re.escape(old))), replacement.format('%{version}' if use_macro else new))
        ]
        # iterate backwards to go from longer to shorter subversions
        for i in reversed(range(2, len(split_version))):
            pattern = re.compile(version_re.format(re.escape('.'.join(split_version[:i]))))
            new_subversion = replacement.format('.'.join(new.split('.')[:i]))
            res.append((pattern, new_subversion))
        # add hardcoded extra version replacement
        try:
            old_extra = spec_file.parse_release()[2]
            if old_extra:
                new_extra = rebase_spec_file.parse_release()[2] or ''
                # allow extraversion to immediately follow version
                extraversion = re.compile(r'([\ /\-\s\d\}])' + re.escape(old_extra) + r'([/.\-\s]|$)')
                res.append((extraversion, replacement.format(new_extra)))
        except RebaseHelperError:
            # silently skip unparsable release
            pass
        return res

    @classmethod
    def run(cls, spec_file: SpecFile, rebase_spec_file: SpecFile, **kwargs: Any):
        replace_with_macro = bool(kwargs.get('replace_old_version_with_macro'))

        subversion_patterns = cls._create_possible_replacements(spec_file, rebase_spec_file, replace_with_macro)
        with rebase_spec_file.spec.sections() as sections:
            for section in sections:
                if section.normalized_id.startswith('changelog'):
                    continue
                elif section.normalized_id.startswith('package'):
                    with rebase_spec_file.spec.tags(section) as tags:
                        for tag in tags:
                            for index, line in enumerate(tag.comments._preceding_lines): # pylint: disable=protected-access
                                start, end = spec_file.get_comment_span(line, section.is_script)
                                updated_line = subversion_patterns[0][0].sub(subversion_patterns[0][1], line[:start])
                                tag.comments._preceding_lines[index] = updated_line + line[start:end] # pylint: disable=protected-access
                            if not tag.value or tag.normalized_name in cls.IGNORED_TAGS:
                                continue
                            if (
                                tag.normalized_name.startswith("Source")
                                or tag.normalized_name.startswith("Patch")
                            ) and not TagSource(tag).remote:
                                # skip local sources
                                continue
                            # replace the whole version first
                            updated_value = subversion_patterns[0][0].sub(subversion_patterns[0][1], tag.value)
                            # replace subversions only for remote sources/patches
                            if tag.normalized_name.startswith('Source') or tag.normalized_name.startswith('Patch'):
                                for sub_pattern, repl in subversion_patterns[1:]:
                                    updated_value = sub_pattern.sub(repl, updated_value)
                            tag.value = updated_value
                    continue
                for index, line in enumerate(section):
                    start, end = spec_file.get_comment_span(line, section.is_script)
                    updated_line = subversion_patterns[0][0].sub(subversion_patterns[0][1], line[:start])
                    section[index] = updated_line + line[start:end]
            rebase_spec_file.save()
