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

import collections.abc
import fnmatch
import re
from typing import Iterator, Optional, Tuple, cast

from rebasehelper.spec_content import SpecContent
from rebasehelper.helpers.macro_helper import MacroHelper


class Tag:
    def __init__(self, section: str, line: int, name: str, value_span: Tuple[int, int], valid: bool) -> None:
        self.section: str = section
        self.line: int = line
        self.name: str = name
        self.value_span: Tuple[int, int] = value_span
        self.valid: bool = valid

    def __eq__(self, other):
        return (self.section == other.section and
                self.line == other.line and
                self.name == other.name and
                self.value_span == other.value_span and
                self.valid == other.valid)


class Tags(collections.abc.Sequence):
    def __init__(self, raw_content: SpecContent, parsed_content: SpecContent) -> None:
        self.items: Tuple[Tag] = self._parse(raw_content, parsed_content)

    def __getitem__(self, index):
        return self.items[index]

    def __len__(self):
        return len(self.items)

    @classmethod
    def _parse(cls, raw_content: SpecContent, parsed_content: SpecContent) -> Tuple[Tag]:
        """Parses all tags from provided SPEC content and determines if they are valid.

        A tag is considered valid if it is still present after evaluating all conditions.

        Note that this is not perfect - if the same tag appears in both %if and %else blocks,
        and has the same value in both, it's impossible to tell them apart, so only the latter
        is considered valid, disregarding the actual condition.

        Returns:
              A tuple of all Tag objects.

              Indexed tag names are sanitized, for example 'Source' is replaced with 'Source0'
              and 'Patch007' with 'Patch7'.

              Tag names are capitalized, section names are lowercase.

        """
        def sanitize(name):
            if name.startswith('Source') or name.startswith('Patch'):
                # strip padding zeroes from indexes
                tokens = re.split(r'(\d+)', name, 1)
                if len(tokens) == 1:
                    return '{0}0'.format(tokens[0])
                return '{0}{1}'.format(tokens[0], int(tokens[1]))
            return name.capitalize()
        result = []
        tag_re = re.compile(r'^(?P<prefix>(?P<name>\w+)\s*:\s*)(?P<value>.+)$')
        for section, _ in raw_content.sections:
            section = section.lower()
            if not section.startswith('%package'):
                continue
            parsed = parsed_content.section(section)
            for index, line in enumerate(raw_content.section(section)):
                expanded = MacroHelper.expand(line)
                if not line or not expanded:
                    continue
                valid = bool(parsed and [p for p in parsed if p == expanded.rstrip()])
                m = tag_re.match(line)
                if m:
                    result.append(Tag(section, index, sanitize(m.group('name')), m.span('value'), valid))
                    continue
                m = tag_re.match(expanded)
                if m:
                    start = line.find(m.group('prefix'))
                    if start < 0:
                        # tag is probably defined by a macro, just ignore it
                        continue
                    # conditionalized tag
                    line = line[start:].rstrip('}')  # FIXME: removing trailing braces is not very robust
                    m = tag_re.match(line)
                    if m:
                        span = cast(Tuple[int, int], tuple(x + start for x in m.span('value')))
                        result.append(Tag(section, index, sanitize(m.group('name')), span, valid))
        return cast(Tuple[Tag], tuple(result))

    def filter(self, section: Optional[str] = None, name: Optional[str] = None,
               valid: Optional[bool] = True) -> Iterator[Tag]:
        """Filters tags based on section, name or validity. Defaults to all valid tags in all sections.

        Args:
            section: If specified, includes tags only from this section.
            name: If specified, includes tags matching this name. Wildcards are supported.
            valid: If specified, includes tags of this validity.

        Returns:
            Iterator of matching Tag objects.

        """
        result = iter(self.items)
        if section is not None:
            result = filter(lambda t: t.section == section.lower(), result)  # type: ignore
        if name is not None:
            result = filter(lambda t: fnmatch.fnmatchcase(t.name, name.capitalize()), result)  # type: ignore
        if valid is not None:
            result = filter(lambda t: t.valid == valid, result)
        return result
