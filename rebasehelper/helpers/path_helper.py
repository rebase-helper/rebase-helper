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

import fnmatch
import os
import tempfile


class PathHelper:

    """Class for performing path related tasks."""

    @staticmethod
    def find_first_dir_with_file(top_path, pattern):
        """Recursively searches for a directory containing a file that matches the given pattern.

        Args:
            top_path (str): Directory where to start the search.
            pattern (str): Filename pattern.

        Returns:
            str: Full path to the directory containing the first occurence of the searched file.
            None if there is no file matching the pattern.

        """
        for root, dirs, files in os.walk(top_path):
            dirs.sort()
            for f in files:
                if fnmatch.fnmatch(f, pattern):
                    return os.path.abspath(root)
        return None

    @staticmethod
    def find_first_file(top_path, pattern, recursion_level=None):
        """Recursively searches for a file that matches the given pattern.

        Args:
            top_path (str): Directory where to start the search.
            pattern (str): Filename pattern.
            recursion_level (int): How deep in the directory tree the search can go.

        Returns:
            str: Path to the file matching the pattern or None if there is no file matching the pattern.

        """
        for loop, (root, dirs, files) in enumerate(os.walk(top_path)):
            dirs.sort()
            for f in files:
                if fnmatch.fnmatch(f, pattern):
                    return os.path.join(os.path.abspath(root), f)
            if recursion_level is not None:
                if loop == recursion_level:
                    break
        return None

    @staticmethod
    def find_all_files(top_path, pattern):
        """Recursively searches for all files matching the given pattern.

        Args:
            top_path (str): Directory where to start the search.
            pattern (str): Filename pattern.

        Returns:
            list: List containing absolute paths to all found files.

        """
        files_list = []
        for root, dirs, files in os.walk(top_path):
            dirs.sort()
            for f in files:
                if fnmatch.fnmatch(f, pattern):
                    files_list.append(os.path.join(os.path.abspath(root), f))
        return files_list

    @staticmethod
    def find_all_files_current_dir(top_path, pattern):
        """Searches for all files that match the given pattern inside a directory.

        Args:
            top_path (str): Directory where to start the search.
            pattern (str): Filename pattern.

        Returns:
            list: List containing absolute paths to all found files.

        """
        files_list = []
        for files in os.listdir(top_path):
            if fnmatch.fnmatch(files, pattern):
                files_list.append(os.path.join(os.path.abspath(top_path), files))
        return files_list

    @staticmethod
    def get_temp_dir():
        """Creates a new temporary directory.

        Return:
            str: Path to the created directory.

        """
        return tempfile.mkdtemp(prefix='rebase-helper-')

    @staticmethod
    def file_available(filename):
        """Checks if the given file exists.

        Args:
            filename (str): Path to the file.

        Returns:
            bool: Whether the file exists.

        """
        if os.path.exists(filename) and os.path.getsize(filename) != 0:
            return True
        else:
            return False
