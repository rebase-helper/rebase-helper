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
from typing import List, Optional, Tuple


class SpecContent:
    """Class representing content of a SPEC file."""

    # taken from build/parseSpec.c in rpm source code
    SECTION_HEADERS: List[str] = [
        '%package',
        '%prep',
        '%generate_build_requires',
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
        '%end',
        '%patchlist',
        '%sourcelist',
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

    def __init__(self, content: str) -> None:
        self.sections: List[Tuple[str, List[str]]] = self._split_sections(content)

    def __str__(self) -> str:
        """Join SPEC file sections back together."""
        content = []
        for header, section in self.sections:
            if header != '%package':
                content.append(header + '\n')
            for line in section:
                content.append(line + '\n')
        return ''.join(content)

    def __getitem__(self, index: int) -> List[str]:
        return self.sections[index][1]

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

    def section(self, name: str) -> Optional[List[str]]:
        """Gets content of a section.

        In case there are multiple sections with the same name, the first one is returned.

        Args:
            name: Section name.

        Returns:
            Section content as a list of lines.

        """
        for header, section in self.sections:
            if header.lower() == name.lower():
                return section
        return None

    def replace_section(self, name: str, content: List[str]) -> bool:
        """Replaces content of a section.

        In case there are multiple sections with the same name, the first one is replaced.

        Args:
            name: Section name.
            content: Section content as a list of lines.

        Returns:
            False if section was not found else True.

        """
        for i, (header, _) in enumerate(self.sections):
            if header.lower() == name.lower():
                self.sections[i] = (header, content)
                return True
        return False

    @classmethod
    def _split_sections(cls, content: str) -> List[Tuple[str, List[str]]]:
        """Splits content of a SPEC file into sections.

        Args:
            content: Content of the SPEC file

        Returns:
            The split sections represented as a list of tuples (the first element
            is the section name, the second is the content of the section).

        """
        lines = content.splitlines()
        section_headers_re = [re.compile(r'^{0}\b.*'.format(re.escape(x)), re.IGNORECASE) for x in cls.SECTION_HEADERS]

        section_beginnings: List[Optional[int]] = []
        for i, line in enumerate(lines):
            if line.startswith('%'):
                for header in section_headers_re:
                    if header.match(line):
                        section_beginnings.append(i)
        section_beginnings.append(None)

        sections = [('%package', lines[:section_beginnings[0]])]

        for i in range(len(section_beginnings) - 1):
            # Only the last element of section_beginnings is None, section_beginnings[i] can never be None
            # (the last element isn't iterated over), so section_beginnings[i] + 1 is always valid. Ignore the type.
            start = section_beginnings[i] + 1  # type: ignore
            end = section_beginnings[i + 1]
            sections.append((lines[start - 1], lines[start:end]))
        return sections
